"""仅服务 ``GET /resources/proxy``: 失效外链短时间内直接 502, 避免打满 WebClient 重试. 不写入 DB / HotSettings."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

TTL_SECONDS = 15 * 60
MAX_ENTRIES = 4096

T = TypeVar("T")


class ProxyFailureCache:
    def __init__(self, *, ttl_seconds: float = TTL_SECONDS, max_entries: int = MAX_ENTRIES) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._failures: OrderedDict[str, float] = OrderedDict()
        self._inflight: dict[str, asyncio.Future[object]] = {}
        self._lock = asyncio.Lock()

    def is_blocked(self, url: str) -> bool:
        expires = self._failures.get(url)
        if expires is None:
            return False
        if time.monotonic() >= expires:
            self._failures.pop(url, None)
            return False
        # 访问时移到末尾, 满容淘汰时优先删除最久未用的
        self._failures.move_to_end(url)
        return True

    def remember(self, url: str) -> None:
        self._purge_expired()
        self._failures[url] = time.monotonic() + self._ttl
        self._failures.move_to_end(url)
        while len(self._failures) > self._max_entries:
            self._failures.popitem(last=False)

    def forget(self, url: str) -> None:
        self._failures.pop(url, None)

    async def coalesce(self, url: str, factory: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            existing = self._inflight.get(url)
            if existing is not None:
                wait_fut = existing
                is_leader = False
            else:
                wait_fut = asyncio.get_running_loop().create_future()
                self._inflight[url] = wait_fut
                is_leader = True

        if not is_leader:
            return await cast("asyncio.Future[T]", wait_fut)

        try:
            result = await factory()
            wait_fut.set_result(result)
            return result
        except BaseException as e:
            if not wait_fut.done():
                wait_fut.set_exception(e)
            raise
        finally:
            async with self._lock:
                if self._inflight.get(url) is wait_fut:
                    del self._inflight[url]

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [u for u, exp in self._failures.items() if now >= exp]
        for u in expired:
            del self._failures[u]
