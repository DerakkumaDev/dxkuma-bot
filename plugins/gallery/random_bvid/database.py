from numpy import random
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from util.database import Base, with_transaction


class BvidRecord(Base):
    __tablename__ = "bvid_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bvid = Column(String(12), unique=True, nullable=False, index=True)


class BvidList:
    @with_transaction
    async def random_bvid(self, **kwargs) -> str:
        rng = random.default_rng()
        session: AsyncSession = kwargs["session"]

        stmt = select(BvidRecord.bvid)
        result = await session.execute(stmt)
        bvids = [row[0] for row in result.fetchall()]
        return rng.choice(bvids)

    @with_transaction
    async def add(self, bvid: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = (
            insert(BvidRecord)
            .values(bvid=bvid)
            .on_conflict_do_nothing(index_elements=["bvid"])
            .returning(BvidRecord.id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @with_transaction
    async def remove(self, bvid: str, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = select(BvidRecord).where(BvidRecord.bvid == bvid)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            await session.delete(record)

    @with_transaction
    async def count(self, **kwargs) -> int:
        session: AsyncSession = kwargs["session"]

        stmt = select(BvidRecord)
        result = await session.execute(stmt)
        return len(result.fetchall())


bvidList = BvidList()
