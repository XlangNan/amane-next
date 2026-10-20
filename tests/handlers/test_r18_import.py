"""R18ImportHandler 测试 - 聚焦 ETag 状态持久化与跳过逻辑.

真实导入 (psql/PG) 不在单测覆盖: 这里 mock R18Importer.run 验证 handler 的编排与状态管理.
"""

import json

import pytest

from amane.config import R18Config
from amane.crawlers.r18dev import RemoteMeta
from amane.handlers import R18ImportHandler, R18ImportPayload


def _meta(etag: str = "abc") -> RemoteMeta:
    return RemoteMeta(filename="dump.sql.gz", size=100, etag=etag, file_url="https://x/dump.sql.gz")


@pytest.fixture
def web_client():
    from unittest.mock import AsyncMock

    return AsyncMock()


class TestR18ImportHandler:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_disabled_when_no_dsn(self, tmp_path, web_client):
        handler = R18ImportHandler(R18Config(), web_client, tmp_path)
        result = await handler.handle(R18ImportPayload())
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_successful_import_persists_etag(self, tmp_path, web_client, monkeypatch):
        cfg = R18Config(dsn="postgresql://u@h/postgres")
        handler = R18ImportHandler(cfg, web_client, tmp_path)

        async def _run(self, current_meta=None):
            return True, "", _meta("new-etag")

        monkeypatch.setattr("amane.handlers.r18_import.R18Importer.run", _run)
        result = await handler.handle(R18ImportPayload())

        assert result.success is True
        assert result.result is not None
        assert result.result.imported is True
        assert result.result.etag == "new-etag"
        # 状态落盘
        state = json.loads((tmp_path / "r18_import.json").read_text())
        assert state["etag"] == "new-etag"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_loads_prior_meta_for_comparison(self, tmp_path, web_client, monkeypatch):
        cfg = R18Config(dsn="postgresql://u@h/postgres")
        # 预置上次导入的状态
        (tmp_path / "r18_import.json").write_text(json.dumps(_meta("old")._asdict()))
        handler = R18ImportHandler(cfg, web_client, tmp_path)

        seen: dict = {}

        async def _run(self, current_meta=None):
            seen["current"] = current_meta
            return True, "", _meta("old")  # 远程未变

        monkeypatch.setattr("amane.handlers.r18_import.R18Importer.run", _run)
        result = await handler.handle(R18ImportPayload())

        # handler 应把已存状态传给 importer 作比对基准
        assert seen["current"] is not None
        assert seen["current"].etag == "old"
        assert result.success is True
        assert result.result is not None
        assert result.result.imported is False  # 未变化, 视为跳过

    @pytest.mark.asyncio(loop_scope="function")
    async def test_force_ignores_prior_meta(self, tmp_path, web_client, monkeypatch):
        cfg = R18Config(dsn="postgresql://u@h/postgres")
        (tmp_path / "r18_import.json").write_text(json.dumps(_meta("old")._asdict()))
        handler = R18ImportHandler(cfg, web_client, tmp_path)

        seen: dict = {}

        async def _run(self, current_meta=None):
            seen["current"] = current_meta
            return True, "", _meta("forced")

        monkeypatch.setattr("amane.handlers.r18_import.R18Importer.run", _run)
        result = await handler.handle(R18ImportPayload(force=True))

        assert seen["current"] is None  # force → 不传比对基准
        assert result.success is True

    @pytest.mark.asyncio(loop_scope="function")
    async def test_import_failure_propagates_error(self, tmp_path, web_client, monkeypatch):
        cfg = R18Config(dsn="postgresql://u@h/postgres")
        handler = R18ImportHandler(cfg, web_client, tmp_path)

        async def _run(self, current_meta=None):
            return False, "schema 校验失败", None

        monkeypatch.setattr("amane.handlers.r18_import.R18Importer.run", _run)
        result = await handler.handle(R18ImportPayload())

        assert result.success is False
        assert result.error == "schema 校验失败"
        # 失败不写状态
        assert not (tmp_path / "r18_import.json").exists()
