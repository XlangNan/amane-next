"""把 amane 本地已有的演员头像上传给 Emby 里还没有头像的人物.

Emby 里每个人物只有一份记录, 头像不随影片 NFO 更新. 因此按人物而不是按影片处理: 先列出 Emby 里
没有主图的人物, 再按名字到 amane 演员库里取本地头像文件上传. 人物要先被 Emby 扫描入库才存在,
所以周期执行, 每轮只处理仍缺头像的人物, 已有头像的不碰.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from ..db.models import TaskStatus, TaskType
from ..events import Event, EventType
from ..media.resource_store import internal_url_hash
from .client import EmbyClient, EmbyPerson, image_mime

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import HotSettings
    from ..db.repository import Repository
    from ..media import ResourceStore
    from ..net.http import WebClient

logger = structlog.get_logger()

#: 批次是否结束的检查间隔, 以及最后一个任务结束后要静默多久才算一批做完.
BATCH_POLL_SECONDS = 5.0
BATCH_QUIET_SECONDS = 60.0
MINUTE_SECONDS = 60.0
_FINISHED = frozenset({EventType.TASK_COMPLETED, EventType.TASK_FAILED})
#: 启动后先等一会儿, 让 Emby 先完成自己的扫描.
FIRST_DELAY_SECONDS = 60.0
#: 未启用时每隔多久回头看一次配置.
IDLE_POLL_SECONDS = 60.0
#: 单张头像上限; 超过的多半不是头像, 不上传.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ACTOR_PAGE = 500
#: 一位演员最多试几个头像地址 (缓存没有时每个都要下载).
_MAX_AVATAR_TRIES = 3


#: 统计里每类最多带几个演员名, 供排查.
SAMPLE_LIMIT = 5


class SyncRequest(BaseModel):
    """手动同步的选项; 周期同步固定为全服务器、只补缺失."""

    libraries: list[str] = []
    """Emby 媒体库名; 空 = 整个服务器."""
    overwrite: bool = False
    """False 只补没有头像的演员; True 连已有头像的也用 amane 的头像替换."""


class SyncReport(BaseModel):
    """一轮同步的统计. ``error`` 非空表示这一轮没跑起来 (未配置 / 连不上 / 媒体库名不存在)."""

    emby_persons: int = 0
    skipped_has_image: int = 0
    """只补缺失模式下, 因 Emby 已有头像而跳过的人数."""
    targeted: int = 0
    uploaded: int = 0
    no_local_image: int = 0
    not_in_amane: int = 0
    failed: int = 0
    no_local_names: list[str] = []
    not_in_amane_names: list[str] = []
    failed_names: list[str] = []
    error: str | None = None


class EmbyActorSync:
    def __init__(
        self,
        repo: Repository,
        store: ResourceStore,
        get_hot: Callable[[], HotSettings],
        get_client: Callable[[], WebClient],
    ) -> None:
        self._repo = repo
        self._store = store
        self._get_hot = get_hot
        self._get_client = get_client
        self._lock = asyncio.Lock()
        self._loop_task: asyncio.Task[None] | None = None
        self._batch_task: asyncio.Task[None] | None = None
        self._dirty = False
        self._last_event = 0.0
        self._oneshots: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._loop())

    def trigger(self) -> None:
        """立刻在后台跑一轮 (配置刚改过时用); 已有一轮在跑则本次放弃."""
        if self._lock.locked():
            return
        task = asyncio.create_task(self._run_logged())
        self._oneshots.add(task)
        task.add_done_callback(self._oneshots.discard)

    async def on_event(self, event: Event) -> None:
        """EventBus 监听器: 有刮削 / 整理任务收尾就记一笔, 批次做完后再通知 Emby 扫描并同步. 只记账, 不做慢操作."""
        if event.type not in _FINISHED or not self._auto_enabled():
            return
        task_id = event.data.get("task_id")
        if not isinstance(task_id, int):
            return
        task = await self._repo.get_task(task_id)
        if task is None or task.type not in (TaskType.SCRAPE, TaskType.ORGANIZE):
            return
        self._dirty = True
        self._last_event = time.monotonic()
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._batch_loop())

    def _auto_enabled(self) -> bool:
        cfg = self._get_hot().emby
        return cfg.enabled and bool(cfg.url) and bool(cfg.api_key) and cfg.auto_after_batch

    async def _batch_loop(self) -> None:
        """队列清空且静默满 ``BATCH_QUIET_SECONDS`` 才动手; 等待 Emby 扫描期间又有新结果就再来一轮."""
        while True:
            await asyncio.sleep(BATCH_POLL_SECONDS)
            if not self._auto_enabled():
                self._dirty = False
                return
            if not self._dirty:
                return
            if time.monotonic() - self._last_event < BATCH_QUIET_SECONDS:
                continue
            if await self._repo.count_tasks(statuses=[TaskStatus.QUEUED, TaskStatus.RUNNING]) > 0:
                continue
            self._dirty = False
            await self._refresh_then_sync()
            if not self._dirty:
                return

    async def _refresh_then_sync(self) -> None:
        cfg = self._get_hot().emby
        try:
            await EmbyClient(self._get_client(), cfg).refresh_library()
        except Exception as exc:
            # 扫描没触发成功也照常同步: Emby 可能自己开着实时监控, 已经扫过了.
            logger.warning("emby library refresh failed", error=_describe(exc, cfg.api_key))
        await asyncio.sleep(cfg.refresh_wait_minutes * MINUTE_SECONDS)
        await self._run_logged()

    async def aclose(self) -> None:
        tasks = [t for t in (self._loop_task, self._batch_task, *self._oneshots) if t is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._loop_task = None

    async def _loop(self) -> None:
        await asyncio.sleep(FIRST_DELAY_SECONDS)
        while True:
            cfg = self._get_hot().emby
            if cfg.enabled and cfg.url and cfg.api_key:
                await self._run_logged()
                await asyncio.sleep(cfg.interval_minutes * 60.0)
            else:
                await asyncio.sleep(IDLE_POLL_SECONDS)

    async def _run_logged(self) -> None:
        try:
            report = await self.run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("emby actor sync crashed", exc_info=True)
            return
        if report.error is not None:
            logger.warning("emby actor sync failed", error=report.error)
        else:
            logger.info("emby actor sync done", **report.model_dump(exclude={"error"}))

    async def libraries(self) -> list[str]:
        """Emby 里的媒体库名, 供界面选择. 连不上时抛出, 由路由转成错误提示."""
        cfg = self._get_hot().emby
        if not (cfg.url and cfg.api_key):
            raise ValueError("未填写 Emby 地址或 API 密钥")
        emby = EmbyClient(self._get_client(), cfg)
        return [lib.name for lib in await emby.list_libraries()]

    async def run_once(self, request: SyncRequest | None = None) -> SyncReport:
        options = request or SyncRequest()
        cfg = self._get_hot().emby
        if not (cfg.url and cfg.api_key):
            return SyncReport(error="未填写 Emby 地址或 API 密钥")
        async with self._lock:
            emby = EmbyClient(self._get_client(), cfg)
            try:
                persons = await self._emby_persons(emby, options.libraries)
            except ValueError as exc:
                return SyncReport(error=str(exc))
            except Exception as exc:
                return SyncReport(error=f"无法读取 Emby 人物列表: {_describe(exc, cfg.api_key)}")

            targets: dict[str, list[str]] = {}
            skipped = 0
            for person in persons:
                if options.overwrite or not person.has_primary_image:
                    targets.setdefault(person.name, []).append(person.id)
                else:
                    skipped += 1
            report = SyncReport(
                emby_persons=len(persons),
                skipped_has_image=skipped,
                targeted=sum(len(v) for v in targets.values()),
            )
            if not targets:
                return report

            seen: set[str] = set()
            offset = 0
            while True:
                actors = await self._repo.list_actors(offset=offset, limit=_ACTOR_PAGE)
                if not actors:
                    break
                for actor in actors:
                    if actor.name not in targets or actor.name in seen:
                        continue
                    seen.add(actor.name)
                    path = await self._local_avatar(actor.image_urls)
                    if path is None:
                        report.no_local_image += 1
                        _note(report.no_local_names, actor.name)
                        continue
                    for person_id in targets[actor.name]:
                        if await self._upload(emby, person_id, path, cfg.api_key):
                            report.uploaded += 1
                        else:
                            report.failed += 1
                            _note(report.failed_names, actor.name)
                offset += len(actors)
                if len(actors) < _ACTOR_PAGE:
                    break
            for name in targets:
                if name not in seen:
                    report.not_in_amane += 1
                    _note(report.not_in_amane_names, name)
            return report

    async def _emby_persons(self, emby: EmbyClient, libraries: Sequence[str]) -> list[EmbyPerson]:
        if not libraries:
            return await emby.list_persons()
        by_name = {lib.name: lib.id for lib in await emby.list_libraries()}
        unknown = [name for name in libraries if name not in by_name]
        if unknown:
            raise ValueError(f"Emby 里没有这些媒体库: {', '.join(unknown)}")
        merged: dict[str, EmbyPerson] = {}
        for name in dict.fromkeys(libraries):
            for person in await emby.list_library_persons(by_name[name]):
                merged.setdefault(person.id, person)
        return list(merged.values())

    async def _local_avatar(self, image_urls: list[str] | None) -> Path | None:
        """头像列表里第一个拿得到本地文件的: 先看缓存, 没有就下载 (演员库里有地址不等于文件已下载过)."""
        client = self._get_client()
        for url in (image_urls or [])[:_MAX_AVATAR_TRIES]:
            inner = internal_url_hash(url)
            if inner is not None:
                found = await self._store.get_by_url_hash(inner)
                path = found[1] if found else None
            else:
                path = await self._store.resolve(url)
                if path is None:
                    try:
                        path = await self._store.acquire(url, client)
                    except Exception as exc:
                        logger.warning("emby avatar download failed", url=url, error=str(exc))
                        path = None
            if path is not None:
                return path
        return None

    async def _upload(self, emby: EmbyClient, person_id: str, path: Path, api_key: str) -> bool:
        try:
            image = await asyncio.to_thread(path.read_bytes)
            if not image or len(image) > MAX_IMAGE_BYTES:
                return False
            await emby.upload_primary_image(person_id, image, image_mime(path))
        except Exception as exc:
            logger.warning("emby avatar upload failed", person_id=person_id, error=_describe(exc, api_key))
            return False
        return True


def _note(names: list[str], name: str) -> None:
    if len(names) < SAMPLE_LIMIT:
        names.append(name)


def _describe(exc: Exception, api_key: str) -> str:
    text = str(exc) or type(exc).__name__
    return text.replace(api_key, "***") if api_key else text
