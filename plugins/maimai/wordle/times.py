from datetime import date, datetime, timedelta

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class WordleTimes(Base):
    __tablename__ = "wordle_times"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now()
    )

    @property
    def game_date(self) -> date:
        return date(self.year, self.month, self.day)


class Times:
    @with_transaction
    async def add(
        self, user_id: str, year: int, month: int, day: int, **kwargs
    ) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = insert(WordleTimes).values(
            user_id=user_id, created_at=date(year, month, day)
        )
        await session.execute(stmt)

    @with_transaction
    async def check_available(self, user_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        today = date.today()
        week_ago = today - timedelta(days=7)

        stmt = (
            select(WordleTimes)
            .where(WordleTimes.user_id == user_id, WordleTimes.created_at >= week_ago)
            .order_by(WordleTimes.created_at.desc())
        )

        result = await session.execute(stmt)
        records = result.scalars().all()

        return len(records) > 9


times = Times()
