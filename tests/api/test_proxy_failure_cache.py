"""ProxyFailureCache 单元测试 - TTL / 容量 / singleflight."""

import asyncio

import pytest

from amane.app.proxy_failure_cache import ProxyFailureCache


class TestProxyFailureCache:
    @pytest.mark.parametrize(
        ("action", "url", "expect_blocked"),
        [
            ("none", "http://a/1", False),
            ("remember", "http://a/1", True),
            ("remember_forget", "http://a/1", False),
        ],
        ids=["empty", "remembered", "forgotten"],
    )
    def test_block_lifecycle(self, action: str, url: str, expect_blocked: bool):
        cache = ProxyFailureCache(ttl_seconds=60, max_entries=8)
        if action == "remember":
            cache.remember(url)
        elif action == "remember_forget":
            cache.remember(url)
            cache.forget(url)
        assert cache.is_blocked(url) is expect_blocked

    def test_ttl_expiry(self, monkeypatch: pytest.MonkeyPatch):
        cache = ProxyFailureCache(ttl_seconds=10, max_entries=8)
        now = 1000.0
        monkeypatch.setattr("amane.app.proxy_failure_cache.time.monotonic", lambda: now)
        cache.remember("http://a/x")
        assert cache.is_blocked("http://a/x")

        now = 1010.0
        assert not cache.is_blocked("http://a/x")

    def test_max_entries_evicts_oldest(self):
        cache = ProxyFailureCache(ttl_seconds=60, max_entries=2)
        cache.remember("http://a/1")
        cache.remember("http://a/2")
        cache.remember("http://a/3")
        assert not cache.is_blocked("http://a/1")
        assert cache.is_blocked("http://a/2")
        assert cache.is_blocked("http://a/3")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_coalesce_runs_once(self):
        cache = ProxyFailureCache(ttl_seconds=60, max_entries=8)
        calls = 0
        started = asyncio.Event()
        release = asyncio.Event()

        async def factory() -> str:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return "ok"

        t1 = asyncio.create_task(cache.coalesce("http://a/1", factory))
        await started.wait()
        t2 = asyncio.create_task(cache.coalesce("http://a/1", factory))
        await asyncio.sleep(0.01)
        release.set()
        assert await asyncio.gather(t1, t2) == ["ok", "ok"]
        assert calls == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_coalesce_shares_exception(self):
        cache = ProxyFailureCache(ttl_seconds=60, max_entries=8)
        started = asyncio.Event()
        release = asyncio.Event()

        async def factory() -> str:
            started.set()
            await release.wait()
            raise RuntimeError("boom")

        t1 = asyncio.create_task(cache.coalesce("http://a/1", factory))
        await started.wait()
        t2 = asyncio.create_task(cache.coalesce("http://a/1", factory))
        await asyncio.sleep(0.01)
        release.set()
        results = await asyncio.gather(t1, t2, return_exceptions=True)
        assert all(isinstance(r, RuntimeError) for r in results)
