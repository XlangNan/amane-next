"""Emby 头像同步: 只给缺头像的人物上传, 且统计准确."""

import asyncio
import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amane.config import EmbyConfig, HotSettings
from amane.db.models import TaskStatus, TaskType
from amane.emby import sync as sync_module
from amane.emby import EmbyActorSync, SyncRequest
from amane.emby.client import base_url, image_mime
from amane.events import Event, EventType


class FakeWeb:
    """只实现同步用到的两个入口; ``fail_upload`` 里的人物 ID 上传时抛错."""

    def __init__(
        self,
        persons: list[dict[str, Any]],
        fail_upload: frozenset[str] = frozenset(),
        libraries: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.persons = persons
        self.fail_upload = fail_upload
        self.libraries = libraries or {}
        self.uploads: list[tuple[str, str, dict[str, str], str]] = []
        self.urls: list[str] = []
        self.refreshes = 0
        self.fail_refresh = False

    async def get_json(self, url: str, *, headers: dict[str, str], use_proxy: bool) -> dict[str, Any]:
        self.urls.append(url)
        if url.endswith("/Library/VirtualFolders"):
            return [{"Name": name, "ItemId": f"lib-{name}"} for name in self.libraries]  # type: ignore[return-value]
        if "/Items?" in url:
            name = url.split("ParentId=lib-")[1].split("&")[0]
            people = self.libraries[name]
            return {"Items": [{"People": people}], "TotalRecordCount": 1}
        start = int(url.split("StartIndex=")[1].split("&")[0])
        limit = int(url.split("Limit=")[1])
        return {"Items": self.persons[start : start + limit], "TotalRecordCount": len(self.persons)}

    async def request(
        self, method: str, url: str, *, headers: dict[str, str], use_proxy: bool, data: str | None = None
    ) -> None:
        if url.endswith("/Library/Refresh"):
            if self.fail_refresh:
                raise RuntimeError("refresh refused key-123")
            self.refreshes += 1
            return
        assert data is not None
        person_id = url.split("/Items/")[1].split("/")[0]
        if person_id in self.fail_upload:
            raise RuntimeError("boom key-123")
        self.uploads.append((method, person_id, headers, data))


class FakeRepo:
    def __init__(self, actors: list[SimpleNamespace], tasks: dict[int, TaskType] | None = None, busy: int = 0) -> None:
        self.actors = actors
        self.tasks = tasks or {}
        self.busy = busy
        """前 ``busy`` 次查询队列时仍有任务在跑."""

    async def get_task(self, task_id: int) -> SimpleNamespace | None:
        kind = self.tasks.get(task_id)
        return None if kind is None else SimpleNamespace(type=kind)

    async def count_tasks(self, statuses: list[TaskStatus]) -> int:
        assert TaskStatus.RUNNING in statuses
        if self.busy > 0:
            self.busy -= 1
            return 1
        return 0

    async def list_actors(self, *, offset: int, limit: int) -> list[SimpleNamespace]:
        return self.actors[offset : offset + limit]


class FakeStore:
    """外链按 ``files`` 命中本地文件; 内部地址按 hash 命中."""

    def __init__(self, files: dict[str, Path], remote: dict[str, Path] | None = None) -> None:
        self.files = files
        self.remote = remote or {}
        self.acquired: list[str] = []

    async def acquire(self, url: str, client: object) -> Path | None:
        self.acquired.append(url)
        return self.remote.get(url)

    async def resolve(self, url: str) -> Path | None:
        return self.files.get(url)

    async def get_by_url_hash(self, url_hash: str) -> tuple[None, Path] | None:
        path = self.files.get(f"hash:{url_hash}")
        return None if path is None else (None, path)


def _person(name: str, pid: str, *, primary: bool = False) -> dict[str, Any]:
    return {"Name": name, "Id": pid, "ImageTags": {"Primary": "t"} if primary else {}}


def _actor(name: str, *urls: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, image_urls=list(urls))


def _sync(web: FakeWeb, actors: list[SimpleNamespace], store: FakeStore, cfg: EmbyConfig) -> EmbyActorSync:
    hot = HotSettings(emby=cfg)
    return EmbyActorSync(FakeRepo(actors), store, lambda: hot, lambda: web)  # type: ignore[arg-type]


CFG = EmbyConfig(enabled=True, url="http://nas:8096/", api_key="key-123")


@pytest.mark.asyncio(loop_scope="function")
async def test_uploads_only_people_without_image(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"JPEGDATA")
    png = tmp_path / "b.png"
    png.write_bytes(b"PNGDATA")
    web = FakeWeb(
        [
            _person("有图", "1", primary=True),
            _person("外链", "2"),
            _person("内部", "3"),
            _person("无本地图", "4"),
            _person("不在库", "5"),
        ]
    )
    actors = [
        _actor("有图", "https://x/1.jpg"),
        _actor("外链", "https://x/2.jpg"),
        _actor("内部", "/api/resources/abcd1234"),
        _actor("无本地图", "https://x/missing.jpg"),
    ]
    store = FakeStore({"https://x/2.jpg": jpg, "hash:abcd1234": png, "https://x/1.jpg": jpg})
    report = await _sync(web, actors, store, CFG).run_once()

    assert report.error is None
    assert (report.emby_persons, report.targeted, report.skipped_has_image) == (5, 4, 1)
    assert (report.uploaded, report.no_local_image, report.not_in_amane, report.failed) == (2, 1, 1, 0)
    assert (report.no_local_names, report.not_in_amane_names, report.failed_names) == (["无本地图"], ["不在库"], [])
    uploaded = {pid: (headers, data) for _, pid, headers, data in web.uploads}
    assert set(uploaded) == {"2", "3"}
    assert uploaded["2"][0] == {"X-Emby-Token": "key-123", "Content-Type": "image/jpeg"}
    assert base64.b64decode(uploaded["2"][1]) == b"JPEGDATA"
    assert uploaded["3"][0]["Content-Type"] == "image/png"
    assert all(url.startswith("http://nas:8096/emby/Persons?") for url in web.urls)


@pytest.mark.asyncio(loop_scope="function")
async def test_upload_failure_is_counted(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"x")
    web = FakeWeb([_person("甲", "1"), _person("乙", "2")], fail_upload=frozenset({"1"}))
    store = FakeStore({"https://x/a.jpg": jpg})
    report = await _sync(web, [_actor("甲", "https://x/a.jpg"), _actor("乙", "https://x/a.jpg")], store, CFG).run_once()
    assert (report.uploaded, report.failed, report.failed_names) == (1, 1, ["甲"])


@pytest.mark.asyncio(loop_scope="function")
async def test_nothing_missing_skips_actor_scan() -> None:
    web = FakeWeb([_person("甲", "1", primary=True)])
    repo = FakeRepo([])
    hot = HotSettings(emby=CFG)
    report = await EmbyActorSync(repo, FakeStore({}), lambda: hot, lambda: web).run_once()  # type: ignore[arg-type]
    assert (report.emby_persons, report.targeted, report.skipped_has_image, report.uploaded) == (1, 0, 1, 0)
    assert web.uploads == []


@pytest.mark.asyncio(loop_scope="function")
async def test_paging_reads_every_person() -> None:
    persons = [_person(f"n{i}", str(i), primary=True) for i in range(1203)]
    report = await _sync(FakeWeb(persons), [], FakeStore({}), CFG).run_once()
    assert report.emby_persons == 1203


@pytest.mark.parametrize(
    "cfg",
    [EmbyConfig(), EmbyConfig(url="http://nas:8096"), EmbyConfig(api_key="k")],
)
@pytest.mark.asyncio(loop_scope="function")
async def test_missing_settings_reports_error_without_requests(cfg: EmbyConfig) -> None:
    web = FakeWeb([])
    report = await _sync(web, [], FakeStore({}), cfg).run_once()
    assert report.error is not None
    assert web.urls == []


@pytest.mark.asyncio(loop_scope="function")
async def test_list_failure_is_reported_with_key_redacted() -> None:
    class Down(FakeWeb):
        async def get_json(self, url: str, *, headers: dict[str, str], use_proxy: bool) -> dict[str, Any]:
            raise RuntimeError("connect failed key-123")

    report = await _sync(Down([]), [], FakeStore({}), CFG).run_once()
    assert report.error is not None
    assert "key-123" not in report.error
    assert "***" in report.error


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://nas:8096", "http://nas:8096"),
        ("http://nas:8096/", "http://nas:8096"),
        ("http://nas:8096/emby", "http://nas:8096"),
        ("http://nas:8096/EMBY/", "http://nas:8096"),
        ("https://x.example/proxy/emby", "https://x.example/proxy"),
    ],
)
def test_base_url(raw: str, expected: str) -> None:
    assert base_url(raw) == expected


@pytest.mark.parametrize(
    ("name", "mime"),
    [("a.jpg", "image/jpeg"), ("a.JPEG", "image/jpeg"), ("a.png", "image/png"), ("a.webp", "image/webp"), ("a.bin", "image/jpeg")],
)
def test_image_mime(name: str, mime: str) -> None:
    assert image_mime(Path(name)) == mime


@pytest.mark.parametrize("url", ["ftp://x", "nas:8096", "http://", "http://a b"])
def test_config_rejects_bad_url(url: str) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        EmbyConfig(url=url)


def _ref(name: str, pid: int, *, tag: str | None = None, kind: str = "Actor") -> dict[str, Any]:
    ref: dict[str, Any] = {"Name": name, "Id": pid, "Type": kind}
    if tag is not None:
        ref["PrimaryImageTag"] = tag
    return ref


@pytest.mark.asyncio(loop_scope="function")
async def test_library_scope_only_touches_people_of_selected_libraries(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"x")
    web = FakeWeb(
        [],
        libraries={
            "番号": [_ref("甲", 1), _ref("乙", 2, tag="t"), _ref("导演", 3, kind="Director")],
            "电影": [_ref("丙", 4)],
        },
    )
    store = FakeStore({f"https://x/{n}.jpg": jpg for n in "甲乙丙"})
    actors = [_actor(n, f"https://x/{n}.jpg") for n in "甲乙丙"]
    report = await _sync(web, actors, store, CFG).run_once(SyncRequest(libraries=["番号"]))
    assert report.error is None
    assert [pid for _, pid, _, _ in web.uploads] == ["1"]
    assert (report.emby_persons, report.skipped_has_image, report.targeted) == (2, 1, 1)


@pytest.mark.asyncio(loop_scope="function")
async def test_overwrite_replaces_existing_avatars(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"x")
    web = FakeWeb([_person("甲", "1", primary=True), _person("乙", "2")])
    store = FakeStore({"https://x/a.jpg": jpg})
    actors = [_actor("甲", "https://x/a.jpg"), _actor("乙", "https://x/a.jpg")]
    report = await _sync(web, actors, store, CFG).run_once(SyncRequest(overwrite=True))
    assert sorted(pid for _, pid, _, _ in web.uploads) == ["1", "2"]
    assert (report.skipped_has_image, report.targeted, report.uploaded) == (0, 2, 2)


@pytest.mark.asyncio(loop_scope="function")
async def test_unknown_library_is_an_error_and_uploads_nothing() -> None:
    web = FakeWeb([], libraries={"番号": [_ref("甲", 1)]})
    report = await _sync(web, [], FakeStore({}), CFG).run_once(SyncRequest(libraries=["番号", "不存在"]))
    assert report.error is not None
    assert "不存在" in report.error
    assert web.uploads == []


@pytest.mark.asyncio(loop_scope="function")
async def test_libraries_lists_names() -> None:
    web = FakeWeb([], libraries={"番号": [], "电影": []})
    assert await _sync(web, [], FakeStore({}), CFG).libraries() == ["番号", "电影"]


@pytest.mark.asyncio(loop_scope="function")
async def test_name_samples_are_capped() -> None:
    web = FakeWeb([_person(f"n{i}", str(i)) for i in range(9)])
    report = await _sync(web, [], FakeStore({}), CFG).run_once()
    assert report.not_in_amane == 9
    assert len(report.not_in_amane_names) == 5


@pytest.mark.asyncio(loop_scope="function")
async def test_uncached_avatar_is_downloaded_then_uploaded(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"x")
    web = FakeWeb([_person("甲", "1"), _person("乙", "2")])
    store = FakeStore({}, remote={"https://x/a.jpg": jpg})
    actors = [_actor("甲", "https://x/dead.jpg", "https://x/a.jpg"), _actor("乙", "https://x/dead2.jpg")]
    report = await _sync(web, actors, store, CFG).run_once()
    assert [pid for _, pid, _, _ in web.uploads] == ["1"]
    assert store.acquired == ["https://x/dead.jpg", "https://x/a.jpg", "https://x/dead2.jpg"]
    assert (report.uploaded, report.no_local_image, report.no_local_names) == (1, 1, ["乙"])


@pytest.mark.asyncio(loop_scope="function")
async def test_download_error_counts_as_no_local_image() -> None:
    class Boom(FakeStore):
        async def acquire(self, url: str, client: object) -> Path | None:
            raise RuntimeError("network down")

    web = FakeWeb([_person("甲", "1")])
    report = await _sync(web, [_actor("甲", "https://x/a.jpg")], Boom({}), CFG).run_once()
    assert (report.uploaded, report.no_local_image) == (0, 1)


@pytest.mark.asyncio(loop_scope="function")
async def test_at_most_three_urls_are_tried() -> None:
    store = FakeStore({})
    urls = [f"https://x/{i}.jpg" for i in range(6)]
    await _sync(FakeWeb([_person("甲", "1")]), [_actor("甲", *urls)], store, CFG).run_once()
    assert store.acquired == urls[:3]


def _batch_sync(
    web: FakeWeb, repo: FakeRepo, monkeypatch: pytest.MonkeyPatch, **cfg_kw: Any
) -> tuple[EmbyActorSync, HotSettings]:
    monkeypatch.setattr(sync_module, "BATCH_POLL_SECONDS", 0.01)
    monkeypatch.setattr(sync_module, "BATCH_QUIET_SECONDS", 0.0)
    monkeypatch.setattr(sync_module, "MINUTE_SECONDS", 0.01)
    hot = HotSettings(emby=EmbyConfig(enabled=True, url="http://nas:8096", api_key="key-123", **cfg_kw))
    return EmbyActorSync(repo, FakeStore({}), lambda: hot, lambda: web), hot  # type: ignore[arg-type]


def _done(task_id: int, kind: EventType = EventType.TASK_COMPLETED) -> Event:
    return Event(kind, {"task_id": task_id})


async def _settle(sync: EmbyActorSync) -> None:
    task = sync._batch_task  # noqa: SLF001
    if task is not None:
        await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio(loop_scope="function")
async def test_batch_end_refreshes_emby_then_syncs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    web = FakeWeb([_person("甲", "1")])
    repo = FakeRepo([], tasks={1: TaskType.SCRAPE, 2: TaskType.ORGANIZE, 3: TaskType.SCRAPE}, busy=3)
    sync, _ = _batch_sync(web, repo, monkeypatch)
    for tid in (1, 2, 3):
        await sync.on_event(_done(tid))
    await _settle(sync)
    assert web.refreshes == 1
    assert sum("/Persons?" in url for url in web.urls) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_failed_tasks_also_count_but_other_task_types_and_events_do_not(monkeypatch: pytest.MonkeyPatch) -> None:
    web = FakeWeb([])
    repo = FakeRepo([], tasks={1: TaskType.REFRESH, 2: TaskType.SCRAPE})
    sync, _ = _batch_sync(web, repo, monkeypatch)
    await sync.on_event(_done(1))
    await sync.on_event(_done(404))
    await sync.on_event(Event(EventType.TASK_PROGRESS, {"task_id": 2}))
    await sync.on_event(Event(EventType.TASK_COMPLETED, {"task_id": "2"}))
    assert sync._batch_task is None  # noqa: SLF001
    await sync.on_event(_done(2, EventType.TASK_FAILED))
    await _settle(sync)
    assert web.refreshes == 1


@pytest.mark.parametrize(
    "cfg_kw",
    [{"auto_after_batch": False}, {"enabled": False}, {"api_key": ""}, {"url": ""}],
)
@pytest.mark.asyncio(loop_scope="function")
async def test_auto_sync_is_off_when_disabled_or_unconfigured(cfg_kw: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    web = FakeWeb([])
    sync, hot = _batch_sync(web, FakeRepo([], tasks={1: TaskType.SCRAPE}), monkeypatch)
    hot.emby = hot.emby.model_copy(update=cfg_kw)
    await sync.on_event(_done(1))
    assert sync._batch_task is None  # noqa: SLF001
    assert web.refreshes == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_refresh_failure_still_syncs(monkeypatch: pytest.MonkeyPatch) -> None:
    web = FakeWeb([_person("甲", "1")])
    web.fail_refresh = True
    sync, _ = _batch_sync(web, FakeRepo([], tasks={1: TaskType.SCRAPE}), monkeypatch)
    await sync.on_event(_done(1))
    await _settle(sync)
    assert web.refreshes == 0
    assert sum("/Persons?" in url for url in web.urls) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_results_arriving_during_the_wait_get_another_round(monkeypatch: pytest.MonkeyPatch) -> None:
    web = FakeWeb([])
    repo = FakeRepo([], tasks={1: TaskType.SCRAPE, 2: TaskType.SCRAPE})
    sync, _ = _batch_sync(web, repo, monkeypatch)
    real_sleep = asyncio.sleep
    injected = False

    async def sleep_and_inject(delay: float) -> None:
        nonlocal injected
        if not injected and delay == 0.01 * 3:  # 扫描等待 (3 分钟 × 桩化的分钟长度)
            injected = True
            await sync.on_event(_done(2))
        await real_sleep(delay)

    monkeypatch.setattr(sync_module.asyncio, "sleep", sleep_and_inject)
    await sync.on_event(_done(1))
    await _settle(sync)
    assert web.refreshes == 2
