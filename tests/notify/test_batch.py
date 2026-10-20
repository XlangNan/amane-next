"""批次汇总器: 记账规则与发送时机. 不碰真实数据库与网络."""

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest

from amane.config import HotSettings, NotifyConfig
from amane.db.models import Task, TaskStatus, TaskType
from amane.events import Event, EventType
from amane.handlers.models import OrganizePayload, OrganizeResult, ScrapePayload
from amane.notify import BatchNotifier
from amane.scheduler.worker import CANCEL_ERROR

if TYPE_CHECKING:
    from amane.db.repository import Repository
    from amane.net.http import WebClient

WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=tok"


class _FakeRepo:
    """``busy`` 依次给出 count_tasks 的返回, 末项重复."""

    def __init__(self, busy: list[int] | None = None) -> None:
        self.tasks: dict[int, Task] = {}
        self.busy = busy or [0]
        self.count_calls = 0

    def add(self, task: Task) -> None:
        assert task.id is not None
        self.tasks[task.id] = task

    async def get_task(self, task_id: int) -> Task | None:
        return self.tasks.get(task_id)

    async def count_tasks(self, *_: Any, **__: Any) -> int:
        self.count_calls += 1
        return self.busy.pop(0) if len(self.busy) > 1 else self.busy[0]


class _FakeClient:
    def __init__(self, reply: dict[str, Any] | None = None) -> None:
        self.reply = reply or {"errcode": 0, "errmsg": "ok"}
        self.bodies: list[dict[str, Any]] = []

    async def post_json(self, url: str, *, json: Any = None, **_: Any) -> Any:
        self.bodies.append(json)
        return self.reply

    @property
    def texts(self) -> list[str]:
        return [body["markdown"]["text"] for body in self.bodies]


def _hot(**notify: Any) -> HotSettings:
    # model_construct 绕过 quiet_seconds 的下限校验, 测试里不能真等几秒.
    fields: dict[str, Any] = {
        "dingtalk_enabled": True,
        "dingtalk_webhook": WEBHOOK,
        "quiet_seconds": 0.0,
        "max_wait_minutes": 30,
        **notify,
    }
    return HotSettings(notify=NotifyConfig.model_construct(**fields))


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("amane.notify.batch.POLL_SECONDS", 0.01)


def _build(hot: HotSettings | None = None, repo: _FakeRepo | None = None) -> tuple[BatchNotifier, _FakeRepo, _FakeClient]:
    repo = repo or _FakeRepo()
    client = _FakeClient()
    settings = hot or _hot()
    notifier = BatchNotifier(cast("Repository", repo), lambda: settings, lambda: cast("WebClient", client))
    return notifier, repo, client


def _scrape(task_id: int, number: str, media_file_id: int | None = None) -> Task:
    payload = ScrapePayload(number=number, media_file_id=media_file_id).model_dump(mode="json")
    return Task(id=task_id, type=TaskType.SCRAPE, status=TaskStatus.DONE, payload=payload)


def _organize(task_id: int, file_ids: list[int], *, failed: int = 0, conflicted: int = 0) -> Task:
    payload = OrganizePayload(library_id=1, media_file_ids=file_ids).model_dump(mode="json")
    result = OrganizeResult(
        organized=len(file_ids) - failed - conflicted,
        skipped=0,
        conflicted=conflicted,
        failed=failed,
        pruned_dirs=0,
        conflicts=[],
    ).model_dump(mode="json")
    return Task(id=task_id, type=TaskType.ORGANIZE, status=TaskStatus.DONE, payload=payload, result=result)


def _done(task: Task) -> Event:
    return Event(EventType.TASK_COMPLETED, {"task_id": task.id, "type": str(task.type)})


def _failed(task: Task, error: str) -> Event:
    return Event(EventType.TASK_FAILED, {"task_id": task.id, "type": str(task.type), "error": error})


async def _settle(notifier: BatchNotifier) -> None:
    """等批次循环自然结束 (汇总已发出, 无后续入账)."""
    runner = notifier._runner
    assert runner is not None
    await asyncio.wait_for(runner, timeout=2)


@pytest.mark.asyncio
async def test_counts_each_scraped_film_once() -> None:
    notifier, repo, client = _build()
    ok, bad = _scrape(1, "ABC-123"), _scrape(2, "DEF-456")
    repo.add(ok)
    repo.add(bad)
    await notifier.on_event(_done(ok))
    await notifier.on_event(_failed(bad, "未找到 DEF-456 的元数据"))
    await _settle(notifier)

    (text,) = client.texts
    assert "本次处理影片 **2** 部, 成功 **1** 部, 失败 **1** 部" in text
    assert "- DEF-456: 未找到 DEF-456 的元数据" in text
    assert "ABC-123" not in text.split("失败明细")[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failed", "conflicted", "reason"),
    [(1, 0, "整理失败"), (0, 1, "整理冲突")],
    ids=["failed", "conflict"],
)
async def test_organize_problem_downgrades_a_scraped_film(failed: int, conflicted: int, reason: str) -> None:
    notifier, repo, client = _build()
    scrape, organize = _scrape(1, "ABC-123", media_file_id=7), _organize(2, [7], failed=failed, conflicted=conflicted)
    repo.add(scrape)
    repo.add(organize)
    await notifier.on_event(_done(scrape))
    await notifier.on_event(_done(organize))
    await _settle(notifier)

    (text,) = client.texts
    assert "处理影片 **1** 部, 成功 **0** 部, 失败 **1** 部" in text
    assert f"- ABC-123: {reason}" in text


@pytest.mark.asyncio
async def test_clean_organize_keeps_the_film_successful() -> None:
    notifier, repo, client = _build()
    scrape, organize = _scrape(1, "ABC-123", media_file_id=7), _organize(2, [7])
    repo.add(scrape)
    repo.add(organize)
    await notifier.on_event(_done(scrape))
    await notifier.on_event(_done(organize))
    await _settle(notifier)

    (text,) = client.texts
    assert "成功 **1** 部, 失败 **0** 部" in text


@pytest.mark.asyncio
async def test_organize_task_crash_marks_the_film_failed() -> None:
    notifier, repo, client = _build()
    scrape, organize = _scrape(1, "ABC-123", media_file_id=7), _organize(2, [7])
    repo.add(scrape)
    repo.add(organize)
    await notifier.on_event(_done(scrape))
    await notifier.on_event(_failed(organize, "磁盘只读"))
    await _settle(notifier)

    (text,) = client.texts
    assert "- ABC-123: 磁盘只读" in text


@pytest.mark.asyncio
async def test_organize_of_unknown_file_is_ignored() -> None:
    """手动整理的文件不在本批里 (没有对应的刮削记录): 既不计数也不开批."""
    notifier, repo, client = _build()
    organize = _organize(1, [99], failed=1)
    repo.add(organize)
    await notifier.on_event(_done(organize))
    assert notifier._runner is None
    assert client.bodies == []


@pytest.mark.asyncio
async def test_rescrape_of_same_number_keeps_the_latest_result() -> None:
    notifier, repo, client = _build()
    first, second = _scrape(1, "abc-123"), _scrape(2, "ABC-123")
    repo.add(first)
    repo.add(second)
    await notifier.on_event(_failed(first, "超时"))
    await notifier.on_event(_done(second))
    await _settle(notifier)

    (text,) = client.texts
    assert "处理影片 **1** 部, 成功 **1** 部, 失败 **0** 部" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["cancelled", "other-task-type", "unknown-task-id", "bad-event-data"])
async def test_events_that_are_not_film_results_are_ignored(kind: str) -> None:
    notifier, repo, client = _build()
    actor = Task(id=5, type=TaskType.ACTOR_SCRAPE, status=TaskStatus.DONE, payload={})
    scrape = _scrape(1, "ABC-123")
    repo.add(actor)
    repo.add(scrape)
    events = {
        "cancelled": _failed(scrape, CANCEL_ERROR),
        "other-task-type": _done(actor),
        "unknown-task-id": Event(EventType.TASK_COMPLETED, {"task_id": 404, "type": "scrape"}),
        "bad-event-data": Event(EventType.TASK_COMPLETED, {"type": "scrape"}),
    }
    await notifier.on_event(events[kind])
    assert notifier._runner is None
    assert client.bodies == []


@pytest.mark.asyncio
async def test_progress_and_log_events_are_ignored() -> None:
    notifier, repo, client = _build()
    scrape = _scrape(1, "ABC-123")
    repo.add(scrape)
    await notifier.on_event(Event(EventType.TASK_PROGRESS, {"task_id": 1}))
    await notifier.on_event(Event(EventType.LOG, {}))
    assert notifier._runner is None


@pytest.mark.asyncio
async def test_disabled_config_records_nothing() -> None:
    for hot in (_hot(dingtalk_enabled=False), _hot(dingtalk_webhook="")):
        notifier, repo, client = _build(hot)
        scrape = _scrape(1, "ABC-123")
        repo.add(scrape)
        await notifier.on_event(_done(scrape))
        assert notifier._runner is None
        assert client.bodies == []


@pytest.mark.asyncio
async def test_waits_until_queue_is_idle() -> None:
    repo = _FakeRepo(busy=[2, 1, 0])
    notifier, _, client = _build(repo=repo)
    scrape = _scrape(1, "ABC-123")
    repo.add(scrape)
    await notifier.on_event(_done(scrape))
    await _settle(notifier)

    assert repo.count_calls == 3
    assert len(client.bodies) == 1


@pytest.mark.asyncio
async def test_overdue_batch_is_sent_even_if_queue_never_empties() -> None:
    repo = _FakeRepo(busy=[1])
    notifier, _, client = _build(_hot(max_wait_minutes=0), repo=repo)
    scrape = _scrape(1, "ABC-123")
    repo.add(scrape)
    await notifier.on_event(_done(scrape))
    await _settle(notifier)

    assert len(client.bodies) == 1


@pytest.mark.asyncio
async def test_send_failure_is_swallowed_and_batch_is_cleared() -> None:
    notifier, repo, client = _build()
    client.reply = {"errcode": 310000, "errmsg": "keywords not in content"}
    scrape = _scrape(1, "ABC-123")
    repo.add(scrape)
    await notifier.on_event(_done(scrape))
    await _settle(notifier)

    assert len(client.bodies) == 1
    # 失败的那批不重发; 下一批从零开始.
    nxt = _scrape(2, "XYZ-999")
    repo.add(nxt)
    await notifier.on_event(_done(nxt))
    await _settle(notifier)
    assert len(client.bodies) == 2
    assert "处理影片 **1** 部" in client.texts[1]


@pytest.mark.asyncio
async def test_disabling_mid_batch_drops_it() -> None:
    state = {"hot": _hot(quiet_seconds=3600.0)}
    repo = _FakeRepo()
    client = _FakeClient()
    notifier = BatchNotifier(cast("Repository", repo), lambda: state["hot"], lambda: cast("WebClient", client))
    scrape = _scrape(1, "ABC-123")
    repo.add(scrape)
    await notifier.on_event(_done(scrape))
    state["hot"] = _hot(dingtalk_enabled=False)
    await _settle(notifier)

    assert client.bodies == []
