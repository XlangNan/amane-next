"""独立 asyncpg 引擎, 不写入 Alembic, 不参与 HotSettings 热重载链.

dsn 未配置则不连. 实例由调用方持有并注入, 无全局单例.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class R18Database:
    def __init__(self, read_url: str, *, echo: bool = False, pool_size: int = 5, max_overflow: int = 10):
        self._read_url = read_url
        self._engine: AsyncEngine = create_async_engine(
            read_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        # 只读, 不提交; 异常时回滚.
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        await self._engine.dispose()
