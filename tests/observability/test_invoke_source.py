"""invoke_source 是来源 outcome 的唯一写入点."""

from pathlib import Path

import pytest

from amane.config import HotSettings
from amane.db.models import Task, TaskStatus, TaskType
from amane.net.errors import FailureKind, FailureReason, RequestError, RequestFailure, SourceError
from amane.observability.models import SiteOutcomeKind
from amane.observability.recorder import Recorder
from amane.observability.source import invoke_source


@pytest.fixture
def rec(tmp_path: Path) -> Recorder:
    task = Task(id=7, type=TaskType.SCRAPE, status=TaskStatus.RUNNING, payload={}, priority=0)
    return Recorder.begin(tmp_path, task, HotSettings())


@pytest.mark.asyncio
async def test_invoke_source_ok(rec: Recorder):
    async def fetch() -> str:
        return "meta"

    assert await invoke_source("javdb", fetch) == "meta"
    out = rec.summary.outcomes["javdb"]
    assert out.outcome == SiteOutcomeKind.OK
    assert out.reason is None


@pytest.mark.asyncio
async def test_invoke_source_miss(rec: Recorder):
    async def fetch() -> None:
        return None

    assert await invoke_source("dmm", fetch) is None
    out = rec.summary.outcomes["dmm"]
    assert out.outcome == SiteOutcomeKind.FAILED
    assert out.reason == FailureReason.NO_USABLE_METADATA


@pytest.mark.asyncio
async def test_invoke_source_source_error(rec: Recorder):
    async def fetch() -> None:
        raise SourceError(FailureReason.CLOUDFLARE_CHALLENGE, http_status=403, detail="cf")

    assert await invoke_source("javbus", fetch) is None
    out = rec.summary.outcomes["javbus"]
    assert out.reason == FailureReason.CLOUDFLARE_CHALLENGE
    assert out.http_status == 403
    assert out.detail == "cf"


@pytest.mark.asyncio
async def test_invoke_source_request_error_classified(rec: Recorder):
    async def fetch() -> None:
        raise RequestError(
            "https://x.test", RequestFailure(kind=FailureKind.HTTP_STATUS, status=404, message="HTTP 404")
        )

    assert await invoke_source("official", fetch) is None
    out = rec.summary.outcomes["official"]
    assert out.reason == FailureReason.NOT_FOUND
    assert out.http_status == 404


@pytest.mark.asyncio
async def test_invoke_source_unexpected(rec: Recorder):
    async def fetch() -> None:
        raise RuntimeError("bug")

    assert await invoke_source("plugin.x", fetch) is None
    out = rec.summary.outcomes["plugin.x"]
    assert out.reason == FailureReason.UNEXPECTED
