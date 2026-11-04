"""GET /dashboard 的汇总口径."""

from typing import TYPE_CHECKING

import pytest

from amane.db.models import TaskType
from amane.handlers import ScrapePayload

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


class TestDashboard:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty(self, client: AsyncClient, stop_worker: None):
        data = (await client.get("dashboard")).json()
        assert data["metadata"] == 0
        assert data["untranslated"] == 0
        assert data["recent_tasks"] == []
        assert data["translate_enabled"] is False
        assert (data["tasks_queued"], data["tasks_running"], data["tasks_failed"]) == (0, 0, 0)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_counts_untranslated_and_recent_tasks(self, client: AsyncClient, repo: Repository, stop_worker: None):
        await repo.upsert_metadata(number="DB-001", title="こんにちは")
        await repo.upsert_metadata(number="DB-002", title="你好", plot="说明")
        await repo.upsert_metadata(number="DB-003", title="你好", plot="これは説明")
        await repo.create_tasks(TaskType.SCRAPE, [ScrapePayload(number="DB-001"), ScrapePayload(number="DB-002")])

        data = (await client.get("dashboard")).json()
        assert data["metadata"] == 3
        assert data["untranslated"] == 2
        assert data["tasks_queued"] == 2
        assert {t["label"] for t in data["recent_tasks"]} == {"DB-001", "DB-002"}
        assert all(t["status"] == "queued" and t["type"] == "scrape" for t in data["recent_tasks"])
