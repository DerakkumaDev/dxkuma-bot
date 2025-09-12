from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from numpy import random
from sqlalchemy import Boolean, DateTime, Integer, String, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


INITIAL_STAR_BALANCE = 101


class StarBalance(Base):
    __tablename__ = "star_balances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qq: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=INITIAL_STAR_BALANCE)
    is_infinite: Mapped[bool] = mapped_column(Boolean, default=False)


class StarAction(Base):
    __tablename__ = "star_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qq: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    before_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    after_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    cause: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone(timedelta(hours=8))),
    )


class Stars:
    @with_transaction
    async def _is_first_reward_today(self, qq: str, time: int, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        tz = timezone(timedelta(hours=8))
        now = datetime.fromtimestamp(time, tz)
        day_start = datetime(now.year, now.month, now.day, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        first_reward_stmt = (
            select(StarAction.id)
            .where(
                StarAction.qq == qq,
                StarAction.created_at >= day_start,
                StarAction.created_at < day_end,
                StarAction.after_balance > StarAction.before_balance,
            )
            .limit(1)
        )
        first_reward_result = await session.execute(first_reward_stmt)
        return first_reward_result.first() is None

    @with_transaction
    async def get_balance(self, qq: str, **kwargs) -> int | Literal["inf"]:
        session: AsyncSession = kwargs["session"]

        stmt = select(StarBalance.balance, StarBalance.is_infinite).where(
            StarBalance.qq == qq
        )
        result = await session.execute(stmt)
        row = result.first()
        if not row:
            return INITIAL_STAR_BALANCE
        balance, is_infinite = row
        if is_infinite:
            return "inf"
        return int(balance) if balance is not None else INITIAL_STAR_BALANCE

    @with_transaction
    async def apply_change(
        self, qq: str, num: int, cause: str, time: int, **kwargs
    ) -> bool:
        if num == 0:
            return True

        session: AsyncSession = kwargs["session"]

        before_balance: int
        after_balance: int
        now = datetime.fromtimestamp(time, timezone(timedelta(hours=8)))

        sel_inf = select(StarBalance.is_infinite, StarBalance.balance).where(
            StarBalance.qq == qq
        )
        sel_res = await session.execute(sel_inf)
        sel_row = sel_res.first()
        if sel_row and bool(sel_row[0]):
            before_balance = sel_row[1]
            after_balance = sel_row[1]
            action_stmt = insert(StarAction).values(
                qq=qq,
                before_balance=before_balance,
                after_balance=after_balance,
                cause=cause,
                created_at=now,
            )
            await session.execute(action_stmt)
            return True

        if num < 0:
            ins_stmt = insert(StarBalance).values(
                qq=qq, balance=INITIAL_STAR_BALANCE, is_infinite=False
            )
            ins_stmt = ins_stmt.on_conflict_do_nothing(index_elements=["qq"])
            await session.execute(ins_stmt)

            upd_stmt = (
                update(StarBalance)
                .where(StarBalance.qq == qq, StarBalance.balance > 0)
                .values(balance=StarBalance.balance + num)
                .returning(StarBalance.balance)
            )
            upd_result = await session.execute(upd_stmt)
            upd_row = upd_result.first()
            if not upd_row:
                return False
            after_balance = int(upd_row[0])
            before_balance = after_balance - num
        else:
            upd_stmt = (
                update(StarBalance)
                .where(StarBalance.qq == qq)
                .values(balance=StarBalance.balance + num)
                .returning(StarBalance.balance)
            )
            upd_result = await session.execute(upd_stmt)
            upd_row = upd_result.first()
            if upd_row:
                after_balance = int(upd_row[0])
                before_balance = after_balance - num
            else:
                ins_stmt = insert(StarBalance).values(
                    qq=qq, balance=INITIAL_STAR_BALANCE + num, is_infinite=False
                )
                ins_stmt = ins_stmt.on_conflict_do_update(
                    index_elements=["qq"],
                    set_={"balance": StarBalance.balance + ins_stmt.excluded.balance},
                )
                await session.execute(ins_stmt)

                sel_stmt = select(StarBalance.balance).where(StarBalance.qq == qq)
                sel_result = await session.execute(sel_stmt)
                sel_row = sel_result.first()
                after_balance = (
                    int(sel_row[0]) if sel_row and sel_row[0] is not None else num
                )
                before_balance = after_balance - num

        action_stmt = insert(StarAction).values(
            qq=qq,
            before_balance=before_balance,
            after_balance=after_balance,
            cause=cause,
            created_at=now,
        )
        await session.execute(action_stmt)

        return True

    @with_transaction
    async def list_actions(
        self, qq: str, num: Optional[int] = None, **kwargs
    ) -> list[dict[str, Any]]:
        session: AsyncSession = kwargs["session"]

        stmt = (
            select(StarAction).where(StarAction.qq == qq).order_by(StarAction.id.desc())
        )
        if num is not None:
            stmt = stmt.limit(num)

        result = await session.execute(stmt)
        records = result.scalars().all()

        actions: list[dict[str, Any]] = list()
        for rec in records:
            actions.append(
                {
                    "id": rec.id,
                    "qq": rec.qq,
                    "change": rec.after_balance - rec.before_balance,
                    "cause": rec.cause,
                    "created_at": rec.created_at,
                }
            )

        return actions

    @with_transaction
    async def set_inf_balance(self, qq: str, enable: bool, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        upd_stmt = (
            update(StarBalance).where(StarBalance.qq == qq).values(is_infinite=enable)
        )
        upd_res = await session.execute(upd_stmt)
        if upd_res.rowcount and upd_res.rowcount > 0:
            return True

        ins_stmt = insert(StarBalance).values(
            qq=qq,
            balance=INITIAL_STAR_BALANCE,
            is_infinite=enable,
        )
        ins_stmt = ins_stmt.on_conflict_do_update(
            index_elements=["qq"],
            set_={"is_infinite": ins_stmt.excluded.is_infinite},
        )
        await session.execute(ins_stmt)
        return True

    async def give_rewards(
        self, qq: str, min: int, max: int, cause: str, time: int
    ) -> tuple[int, int, int]:
        rng = random.default_rng()
        star = int(rng.integers(min, max))
        extend = 0
        method = rng.choice(range(4), p=[0.91, 0.01, 0.03, 0.05])
        if method == 0b0001:
            extend = int(rng.integers(100, 200))
            method = 0b0100
        elif method == 0b0010:
            star = 50
        elif method == 0b0011:
            star = 101

        is_first_reward_today = await self._is_first_reward_today(qq, time)
        if is_first_reward_today:
            extend = int(rng.integers(50, 100))
            method |= 0b1_0000

        await self.apply_change(qq, star + extend, cause, time)
        return star, method, extend


stars = Stars()
