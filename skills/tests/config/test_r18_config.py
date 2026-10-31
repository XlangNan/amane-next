"""R18Config 连接串派生测试.

dsn 是用户提供的唯一输入, 派生出 admin/read URL 与 enabled 判定. 表测试覆盖派生正确性
与未配置时的健壮性.
"""

import pytest

from amane.config import HotSettings, R18Config


class TestR18InHotSettings:
    """r18 是 Hot section: 进 TOML, 可热更新."""

    def test_toml_roundtrip_preserves_dsn(self):
        hot = HotSettings(r18=R18Config(dsn="postgresql://u:p@h:5432/postgres", db_name="mydb"))
        dumped = hot.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        assert dumped["r18"]["dsn"] == "postgresql://u:p@h:5432/postgres"
        # 重新构造 (模拟从 TOML 加载) 保持一致
        assert HotSettings(**dumped).r18.read_url() == hot.r18.read_url()


class TestR18ConfigEnabled:
    def test_disabled_without_dsn(self):
        assert R18Config().enabled is False

    def test_enabled_with_dsn(self):
        assert R18Config(dsn="postgresql://postgres@localhost/postgres").enabled is True


class TestAdminUrl:
    def test_replaces_database_and_adds_async_driver(self):
        cfg = R18Config(dsn="postgresql://postgres:pw@db:5432/postgres")
        assert cfg.admin_url("template1") == "postgresql+asyncpg://postgres:pw@db:5432/template1"

    def test_sync_mode_drops_async_driver(self):
        cfg = R18Config(dsn="postgresql://postgres:pw@db:5432/postgres")
        assert cfg.admin_url("foo", async_mode=False) == "postgresql://postgres:pw@db:5432/foo"

    def test_defaults_to_postgres_db_when_dsn_has_none(self):
        cfg = R18Config(dsn="postgresql://postgres@db:5432")
        assert cfg.admin_url().endswith("/postgres")

    def test_raises_without_dsn(self):
        with pytest.raises(ValueError, match="未配置"):
            R18Config().admin_url("x")


class TestReadUrl:
    def test_uses_readonly_credentials_and_target_db(self):
        cfg = R18Config(dsn="postgresql://postgres:pw@db:5432/postgres", db_name="r18dev", read_user="ro")
        url = cfg.read_url()
        assert url.startswith("postgresql+asyncpg://ro:")
        assert url.endswith("@db:5432/r18dev")

    def test_raises_without_dsn(self):
        with pytest.raises(ValueError, match="未配置"):
            R18Config().read_url()
