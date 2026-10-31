from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    import asyncio


class RepositoryMixinBase:
    """子类须提供 ``_session()``. 任务 mixin 还依赖 ``_task_insert_lock`` 串行化入队互斥."""

    _task_insert_lock: asyncio.Lock

    def _session(self) -> AsyncSession:
        raise NotImplementedError
