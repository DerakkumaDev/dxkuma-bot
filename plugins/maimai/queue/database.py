from datetime import datetime
from typing import Optional

import nanoid
from rapidfuzz import fuzz, process
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from util.database import Base, with_transaction


class Arcade(Base):
    __tablename__ = "arcades"

    id: Mapped[str] = mapped_column(String(21), primary_key=True)
    name: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    count: Mapped[int] = mapped_column(Integer, default=0)
    action_times: Mapped[int] = mapped_column(Integer, default=0)

    aliases: Mapped[list["ArcadeAlias"]] = relationship(
        "ArcadeAlias", back_populates="arcade", cascade="all, delete-orphan"
    )
    bindings: Mapped[list["ArcadeBinding"]] = relationship(
        "ArcadeBinding", back_populates="arcade", cascade="all, delete-orphan"
    )
    last_action: Mapped[Optional["ArcadeLastAction"]] = relationship(
        "ArcadeLastAction",
        back_populates="arcade",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ArcadeLastAction(Base):
    __tablename__ = "arcade_last_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arcade_id: Mapped[str] = mapped_column(
        String(21), ForeignKey("arcades.id"), nullable=False, unique=True, index=True
    )
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action_time: Mapped[int] = mapped_column(Integer, nullable=False)
    before_count: Mapped[int] = mapped_column(Integer, nullable=False)

    arcade: Mapped["Arcade"] = relationship("Arcade", back_populates="last_action")


class ArcadeAlias(Base):
    __tablename__ = "arcade_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arcade_id: Mapped[str] = mapped_column(
        String(21), ForeignKey("arcades.id"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    arcade: Mapped["Arcade"] = relationship("Arcade", back_populates="aliases")

    __table_args__ = (UniqueConstraint("arcade_id", "alias", name="uq_arcade_alias"),)


class ArcadeBinding(Base):
    __tablename__ = "arcade_bindings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arcade_id: Mapped[str] = mapped_column(
        String(21), ForeignKey("arcades.id"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    arcade: Mapped["Arcade"] = relationship("Arcade", back_populates="bindings")

    __table_args__ = (
        UniqueConstraint("arcade_id", "group_id", name="uq_arcade_binding"),
    )


class ArcadeManager:
    @with_transaction
    async def get_arcade(self, arcade_id: str, **kwargs) -> Optional[dict]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade).where(Arcade.id == arcade_id)
        result = await session.execute(stmt)
        arcade_record = result.scalar_one_or_none()

        if not arcade_record:
            return None

        last_action_stmt = select(ArcadeLastAction).where(
            ArcadeLastAction.arcade_id == arcade_id
        )
        last_action_result = await session.execute(last_action_stmt)
        last_action = last_action_result.scalar_one_or_none()

        if last_action is None:
            return await self._arcade_to_dict(arcade_record, session)

        last_action_time = datetime.fromtimestamp(last_action.action_time)
        now = datetime.now()
        today = datetime(now.year, now.month, now.day, 4, 0, 0, 0)

        if last_action_time >= today or now.hour < 4:
            return await self._arcade_to_dict(arcade_record, session)

        await self.reset(arcade_id, int(today.timestamp()), session)
        return await self._arcade_to_dict(arcade_record, session)

    @with_transaction
    async def get_arcade_id(self, arcade_name: str, **kwargs) -> Optional[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade.id).where(Arcade.name == arcade_name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def get_bounden_arcade_ids(self, group_id: int, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeBinding.arcade_id).where(ArcadeBinding.group_id == group_id)
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    @with_transaction
    async def create(self, arcade_name: str, **kwargs) -> Optional[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade.id).where(Arcade.name == arcade_name)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return None

        arcade_id = nanoid.generate()
        new_arcade = Arcade(id=arcade_id, name=arcade_name)
        session.add(new_arcade)

        return arcade_id

    @with_transaction
    async def bind(self, group_id: int, arcade_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeBinding).where(
            ArcadeBinding.group_id == group_id, ArcadeBinding.arcade_id == arcade_id
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            return False

        new_binding = ArcadeBinding(group_id=group_id, arcade_id=arcade_id)
        session.add(new_binding)
        return True

    @with_transaction
    async def unbind(self, group_id: int, arcade_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeBinding).where(
            ArcadeBinding.group_id == group_id, ArcadeBinding.arcade_id == arcade_id
        )
        result = await session.execute(stmt)
        binding = result.scalar_one_or_none()

        if not binding:
            return False

        await session.delete(binding)

        stmt = select(ArcadeBinding).where(ArcadeBinding.arcade_id == arcade_id)
        result = await session.execute(stmt)
        remaining_bindings = result.scalars().all()

        if not remaining_bindings:
            stmt = select(Arcade).where(Arcade.id == arcade_id)
            result = await session.execute(stmt)
            arcade = result.scalar_one_or_none()
            if arcade:
                await session.delete(arcade)

        return True

    @with_transaction
    async def search(self, group_id: int, word: str, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeBinding.arcade_id).where(ArcadeBinding.group_id == group_id)
        result = await session.execute(stmt)
        bound_arcade_ids = [row[0] for row in result.fetchall()]
        if not bound_arcade_ids:
            return []

        stmt = select(Arcade.name).where(Arcade.id.in_(bound_arcade_ids))
        result = await session.execute(stmt)
        names = [row[0] for row in result.fetchall()]

        stmt = select(ArcadeAlias.alias, ArcadeAlias.arcade_id).where(
            ArcadeAlias.arcade_id.in_(bound_arcade_ids)
        )
        result = await session.execute(stmt)
        aliases = {row[0]: row[1] for row in result.fetchall()}

        all_names = names + list(aliases.keys())

        matched_arcade_ids = await self._filter_arcade_ids(
            word, all_names, fuzz.ratio, 60, session
        )

        return matched_arcade_ids

    async def _filter_arcade_ids(
        self,
        word: str,
        names: list[str],
        scorer,
        score_cutoff: int,
        session: AsyncSession,
    ) -> list[str]:
        matches = process.extract(
            word, names, scorer=scorer, score_cutoff=score_cutoff, limit=10
        )

        matched_names = [match[0] for match in matches]

        arcade_ids = set()

        stmt = select(Arcade.id).where(Arcade.name.in_(matched_names))
        result = await session.execute(stmt)
        arcade_ids.update([row[0] for row in result.fetchall()])

        stmt = select(ArcadeAlias.arcade_id).where(ArcadeAlias.alias.in_(matched_names))
        result = await session.execute(stmt)
        arcade_ids.update([row[0] for row in result.fetchall()])

        return list(arcade_ids)

    @with_transaction
    async def search_all(self, word: str, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade.name)
        result = await session.execute(stmt)
        names = [row[0] for row in result.fetchall()]

        stmt = select(ArcadeAlias.alias)
        result = await session.execute(stmt)
        aliases = [row[0] for row in result.fetchall()]

        all_names = names + aliases

        matches = process.extract(
            word, all_names, scorer=fuzz.ratio, score_cutoff=60, limit=10
        )

        matched_names = [match[0] for match in matches]

        arcade_ids = set()

        stmt = select(Arcade.id).where(Arcade.name.in_(matched_names))
        result = await session.execute(stmt)
        arcade_ids.update([row[0] for row in result.fetchall()])

        stmt = select(ArcadeAlias.arcade_id).where(ArcadeAlias.alias.in_(matched_names))
        result = await session.execute(stmt)
        arcade_ids.update([row[0] for row in result.fetchall()])

        return list(arcade_ids)

    @with_transaction
    async def all_arcade_ids(self, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade.id)
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    @with_transaction
    async def add_alias(self, arcade_id: str, alias: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeAlias).where(
            ArcadeAlias.arcade_id == arcade_id, ArcadeAlias.alias == alias
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            return False

        new_alias = ArcadeAlias(arcade_id=arcade_id, alias=alias)
        session.add(new_alias)
        return True

    @with_transaction
    async def remove_alias(self, arcade_id: str, alias: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeAlias).where(
            ArcadeAlias.arcade_id == arcade_id, ArcadeAlias.alias == alias
        )
        result = await session.execute(stmt)
        alias_record = result.scalar_one_or_none()

        if not alias_record:
            return False

        await session.delete(alias_record)
        return True

    @with_transaction
    async def do_action(
        self,
        arcade_id: str,
        type: str,
        group_id: int,
        operator: int,
        time: int,
        num: int,
        **kwargs,
    ) -> dict:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade).where(Arcade.id == arcade_id)
        result = await session.execute(stmt)
        arcade = result.scalar_one_or_none()

        if not arcade:
            return {}

        before = arcade.count

        match type:
            case "add":
                new_count = arcade.count + num
                if new_count > 50:
                    return await self._arcade_to_dict(arcade, session)
                arcade.count = new_count
            case "remove":
                new_count = arcade.count - num
                if new_count < 0:
                    return await self._arcade_to_dict(arcade, session)
                arcade.count = new_count
            case "set":
                if num < 0 or num > 50 or arcade.count == num:
                    return await self._arcade_to_dict(arcade, session)
                arcade.count = num
            case _:
                return await self._arcade_to_dict(arcade, session)

        arcade.action_times += 1

        last_action_stmt = select(ArcadeLastAction).where(
            ArcadeLastAction.arcade_id == arcade_id
        )
        last_action_result = await session.execute(last_action_stmt)
        last_action = last_action_result.scalar_one_or_none()

        if last_action:
            last_action.group_id = group_id
            last_action.operator_id = operator
            last_action.action_time = time
            last_action.before_count = before
        else:
            new_last_action = ArcadeLastAction(
                arcade_id=arcade_id,
                group_id=group_id,
                operator_id=operator,
                action_time=time,
                before_count=before,
            )
            session.add(new_last_action)

        return await self._arcade_to_dict(arcade, session)

    async def reset(self, arcade_id: str, time: int, session: AsyncSession) -> dict:
        stmt = select(Arcade).where(Arcade.id == arcade_id)
        result = await session.execute(stmt)
        arcade = result.scalar_one_or_none()

        if not arcade:
            return {}

        arcade.action_times = 0
        if arcade.count > 0:
            last_action_stmt = select(ArcadeLastAction).where(
                ArcadeLastAction.arcade_id == arcade_id
            )
            last_action_result = await session.execute(last_action_stmt)
            last_action = last_action_result.scalar_one_or_none()

            if last_action:
                last_action.group_id = -1
                last_action.operator_id = -1
                last_action.action_time = time
                last_action.before_count = arcade.count
            else:
                new_last_action = ArcadeLastAction(
                    arcade_id=arcade_id,
                    group_id=-1,
                    operator_id=-1,
                    action_time=time,
                    before_count=arcade.count,
                )
                session.add(new_last_action)
            arcade.count = 0

        return await self._arcade_to_dict(arcade, session)

    async def _arcade_to_dict(self, arcade: Arcade, session: AsyncSession) -> dict:
        last_action_stmt = select(ArcadeLastAction).where(
            ArcadeLastAction.arcade_id == arcade.id
        )
        last_action_result = await session.execute(last_action_stmt)
        last_action = last_action_result.scalar_one_or_none()

        last_action_dict = None
        if last_action:
            last_action_dict = {
                "group": last_action.group_id,
                "operator": last_action.operator_id,
                "time": last_action.action_time,
                "before": last_action.before_count,
            }

        return {
            "id": arcade.id,
            "name": arcade.name,
            "count": arcade.count,
            "action_times": arcade.action_times,
            "last_action": last_action_dict,
        }


arcadeManager = ArcadeManager()
