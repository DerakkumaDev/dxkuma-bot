from sqlalchemy import String, Integer, Boolean, Float, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class WordleScore(Base):
    __tablename__ = "wordle_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    oc_times: Mapped[int] = mapped_column(Integer, default=1)
    it_times: Mapped[int] = mapped_column(Integer, default=0)
    pt_times: Mapped[int] = mapped_column(Integer, default=0)
    ad_times: Mapped[int] = mapped_column(Integer, default=0)
    is_guesser: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)


class Ranking:
    def _compute_score(
        self,
        oc_times: int = 1,
        it_times: int = 0,
        pt_times: int = 0,
        ad_times: int = 0,
        is_guesser: bool = False,
    ) -> float:
        score = 1.01
        if oc_times <= 0:
            score *= 1.002

        if pt_times > 0:
            score *= 0.991**pt_times
        elif ad_times > 0:
            score *= 0.993**ad_times
        elif it_times > 0:
            score *= 0.995**it_times

        if not is_guesser:
            score *= 0.98

        return score

    @with_transaction
    async def add_score(
        self,
        user_id: str,
        oc_times: int,
        it_times: int,
        pt_times: int,
        ad_times: int,
        is_guesser: bool,
        **kwargs,
    ) -> None:
        session: AsyncSession = kwargs["session"]

        score = self._compute_score(oc_times, it_times, pt_times, ad_times, is_guesser)
        stmt = insert(WordleScore).values(
            user_id=user_id,
            oc_times=oc_times,
            it_times=it_times,
            pt_times=pt_times,
            ad_times=ad_times,
            is_guesser=is_guesser,
            score=score,
        )
        await session.execute(stmt)

    @with_transaction
    async def avg_scores(self, **kwargs) -> list[tuple[str, float, int]]:
        session: AsyncSession = kwargs["session"]

        stmt = (
            select(
                WordleScore.user_id,
                func.avg(WordleScore.score).label("avg_score"),
                func.count(WordleScore.id).label("count"),
            )
            .group_by(WordleScore.user_id)
            .order_by(func.avg(WordleScore.score).desc())
        )

        result = await session.execute(stmt)
        records = result.fetchall()

        achis = list()
        for record in records:
            if record.count > 0:
                achis.append((record.user_id, float(record.avg_score), record.count))

        return achis

    @with_transaction
    async def get_score(self, user_id: str, **kwargs) -> tuple[float, int]:
        session: AsyncSession = kwargs["session"]

        stmt = select(
            func.avg(WordleScore.score).label("avg_score"),
            func.count(WordleScore.id).label("count"),
        ).where(WordleScore.user_id == user_id)

        result = await session.execute(stmt)
        record = result.fetchone()

        if record and record.count > 0:
            return (float(record.avg_score), record.count)

        return (0.0, 0)


ranking = Ranking()
