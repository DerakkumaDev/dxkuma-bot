import datetime

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class RankingRecord(Base):
    __tablename__ = "ranking_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qq: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    week_key: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    sfw_count: Mapped[int] = mapped_column(Integer, default=0)
    nsfw_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)

    __table_args__ = (UniqueConstraint("qq", "week_key", name="uq_qq_week_key"),)


class Ranking:
    def __init__(self):
        self.pic_path = "./Static/Gallery/SFW/"
        self.nsfw_pic_path = "./Static/Gallery/NSFW/"

    @property
    def now(self) -> str:
        today = datetime.date.today()

        # 获取当前年份
        year = today.year

        # 获取当前日期所在的周数
        week_number = today.isocalendar()[1]

        # 将年份和周数拼接成字符串
        return f"{year}{week_number:02d}"

    @with_transaction
    async def gen_rank(self, time: str, **kwargs) -> list[tuple[str, int]]:
        session: AsyncSession = kwargs["session"]

        stmt = select(
            RankingRecord.qq,
            (
                RankingRecord.sfw_count
                + RankingRecord.nsfw_count
                + RankingRecord.video_count
            ).label("total_count"),
        ).where(RankingRecord.week_key == time)

        result = await session.execute(stmt)
        leaderboard = [(row[0], row[1]) for row in result.fetchall()]

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        return leaderboard[:5]

    @with_transaction
    async def update_count(self, qq: str, type: str, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        time = self.now
        count_increment = {"sfw_count": 0, "nsfw_count": 0, "video_count": 0}
        if type == "sfw":
            count_increment["sfw_count"] = 1
        elif type == "nsfw":
            count_increment["nsfw_count"] = 1
        elif type == "video":
            count_increment["video_count"] = 1

        stmt = insert(RankingRecord).values(
            qq=qq, week_key=time, **count_increment, created_at=datetime.date.today()
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_qq_week_key",
            set_={
                "sfw_count": RankingRecord.sfw_count + stmt.excluded.sfw_count,
                "nsfw_count": RankingRecord.nsfw_count + stmt.excluded.nsfw_count,
                "video_count": RankingRecord.video_count + stmt.excluded.video_count,
            },
        )
        await session.execute(stmt)


ranking = Ranking()
