"""把一批影片的刮削 / 整理结果攒成一条汇总, 在批次结束后发到钉钉.

"一批" = 任务队列从有活干到清空. 监听 ``EventBus`` 的任务完成 / 失败事件, 不改动任何任务处理器.
"""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING

import structlog

from ..db.models import TaskStatus, TaskType
from ..events import Event, EventType
from ..handlers.models import OrganizePayload, OrganizeResult, ScrapePayload
from ..scheduler.worker import CANCEL_ERROR
from .dingtalk import send_markdown
from .summary import FilmOutcome, build_summary

if TYPE_CHECKING:
    from ..config import HotSettings, NotifyConfig
    from ..db.models import Task
    from ..db.repository import Repository
    from ..net.http import WebClient

logger = structlog.get_logger()

POLL_SECONDS = 5.0
"""批次开着时检查「是否该发」的间隔."""

_FINISHED = frozenset({EventType.TASK_COMPLETED, EventType.TASK_FAILED})


class BatchNotifier:
    """按影片统计: 每个 SCRAPE 任务算一部; 自动整理失败或冲突会把该片从成功改记为失败.

    发送条件 (满足其一): 队列已空且静默满 ``quiet_seconds``; 或批次已开满 ``max_wait_minutes``.
    批次状态只在内存里, 进程重启会丢掉尚未发送的那一批.
    """

    def __init__(
        self,
        repo: Repository,
        get_hot: Callable[[], HotSettings],
        get_client: Callable[[], WebClient],
    ) -> None:
        self._repo = repo
        self._get_hot = get_hot
        # 改配置会重建 WebClient, 所以每次发送时现取.
        self._get_client = get_client
        self._films: dict[str, FilmOutcome] = {}
        self._file_keys: dict[int, str] = {}
        """MediaFile.id → 影片键, 用于把整理结果对回影片."""
        self._started: float | None = None
        self._last_event = 0.0
        self._runner: asyncio.Task[None] | None = None

    @staticmethod
    def _active(cfg: NotifyConfig) -> bool:
        return cfg.dingtalk_enabled and bool(cfg.dingtalk_webhook)

    async def on_event(self, event: Event) -> None:
        """EventBus 监听器: 只记账, 不做慢操作."""
        if event.type not in _FINISHED:
            return
        if not self._active(self._get_hot().notify):
            return
        task_id = event.data.get("task_id")
        if not isinstance(task_id, int):
            return
        raw_error = event.data.get("error")
        failed = event.type is EventType.TASK_FAILED
        error = (raw_error if isinstance(raw_error, str) and raw_error else "未知错误") if failed else None
        if error == CANCEL_ERROR:
            return
        task = await self._repo.get_task(task_id)
        if task is None:
            return
        try:
            match task.type:
                case TaskType.SCRAPE:
                    recorded = self._record_scrape(task, error)
                case TaskType.ORGANIZE:
                    recorded = self._record_organize(task, error)
                case _:
                    return
        except ValueError:
            # 存量任务的 payload / result 读不出来: 这一条不计入, 不影响其它.
            logger.warning("notify skipped unreadable task", task_id=task_id, task_type=str(task.type))
            return
        if recorded:
            self._touch()

    def _record_scrape(self, task: Task, error: str | None) -> bool:
        """记下这部影片的结果; 恒为 True."""
        payload = ScrapePayload.model_validate(task.payload)
        key = payload.number.upper()
        self._films[key] = FilmOutcome(payload.number, error)
        if payload.media_file_id is not None:
            self._file_keys[payload.media_file_id] = key
        return True

    def _record_organize(self, task: Task, error: str | None) -> bool:
        """整理出了问题就把对应影片改记为失败. 返回是否改动了某部影片: 干净的整理与本批之外的文件都不入账."""
        payload = OrganizePayload.model_validate(task.payload)
        reason = error
        if reason is None:
            if task.result is None:
                return False
            result = OrganizeResult.model_validate(task.result)
            if result.failed:
                reason = "整理失败"
            elif result.conflicted:
                reason = "整理冲突: 目标已存在"
        if reason is None:
            return False
        changed = False
        for media_file_id in payload.media_file_ids or []:
            film = self._films.get(self._file_keys.get(media_file_id, ""))
            if film is not None and film.error is None:
                film.error = reason
                changed = True
        return changed

    def _touch(self) -> None:
        now = time.monotonic()
        if self._started is None:
            self._started = now
        self._last_event = now
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(POLL_SECONDS)
            cfg = self._get_hot().notify
            if not self._active(cfg):
                self._reset()
                return
            if self._started is not None:
                now = time.monotonic()
                overdue = now - self._started >= cfg.max_wait_minutes * 60
                quiet = now - self._last_event >= cfg.quiet_seconds
                if overdue or (quiet and await self._queue_idle()):
                    await self._flush(cfg)
            # 发送期间又有影片入账时留在循环里, 否则它们会没人管.
            if not self._films:
                return

    async def _queue_idle(self) -> bool:
        busy = await self._repo.count_tasks(statuses=[TaskStatus.QUEUED, TaskStatus.RUNNING])
        return busy == 0

    def _reset(self) -> None:
        self._films = {}
        self._file_keys = {}
        self._started = None

    async def _flush(self, cfg: NotifyConfig) -> None:
        films = list(self._films.values())
        # 先清空再发送: 发送期间到达的结果记进下一批.
        self._reset()
        if not films:
            return
        title, text = build_summary(films, cfg.dingtalk_keyword)
        error = await send_markdown(self._get_client(), cfg, title, text)
        if error is None:
            logger.info("dingtalk summary sent", films=len(films))
        else:
            logger.warning("dingtalk summary failed", films=len(films), error=error)

    async def aclose(self) -> None:
        runner = self._runner
        if runner is not None and not runner.done():
            runner.cancel()
            with suppress(asyncio.CancelledError):
                await runner
