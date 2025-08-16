from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import config

engine = create_async_engine(config.database_url, echo=False, poolclass=NullPool)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


def with_transaction(func):
    async def wrapper(*args, **kwargs):
        session = AsyncSessionLocal()
        kwargs["session"] = session
        try:
            result = await func(*args, **kwargs)
            await session.commit()
            return result
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                await session.close()
            except Exception:
                pass

    return wrapper


async def init_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    await engine.dispose()
