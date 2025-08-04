from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from util.Config import config

engine = create_async_engine(
    config.database_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self):
        self._session: Optional[AsyncSession] = None

    async def get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSessionLocal()
        return self._session

    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        self._session = await self.get_session()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()


def with_transaction(func):
    async def wrapper(*args, **kwargs):
        async with DatabaseManager() as session:
            kwargs["session"] = session
            try:
                result = await func(*args, **kwargs)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

    return wrapper


async def init_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    await engine.dispose()
