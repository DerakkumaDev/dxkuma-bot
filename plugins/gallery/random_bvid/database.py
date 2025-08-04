from numpy import random
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from util.database import Base, with_transaction


class BvidRecord(Base):
    __tablename__ = "bvid_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bvid = Column(String(12), unique=True, nullable=False, index=True)


class BvidList:
    @with_transaction
    async def random_bvid(self, session: AsyncSession) -> str:
        rng = random.default_rng()
        stmt = select(BvidRecord.bvid)
        result = await session.execute(stmt)
        bvids = [row[0] for row in result.fetchall()]
        return rng.choice(bvids)

    @with_transaction
    async def add(self, bvid: str, session: AsyncSession) -> bool:
        stmt = select(BvidRecord).where(BvidRecord.bvid == bvid)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            return False

        new_record = BvidRecord(bvid=bvid)
        session.add(new_record)

        return True

    @with_transaction
    async def remove(self, bvid: str, session: AsyncSession) -> None:
        stmt = select(BvidRecord).where(BvidRecord.bvid == bvid)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            await session.delete(record)

    @with_transaction
    async def count(self, session: AsyncSession) -> int:
        stmt = select(BvidRecord)
        result = await session.execute(stmt)
        return len(result.fetchall())


bvidList = BvidList()
