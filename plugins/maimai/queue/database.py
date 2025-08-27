from datetime import datetime
from typing import Optional

import nanoid
from rapidfuzz import fuzz, process
from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
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
        stmt = insert(Arcade).values(
            id=arcade_id, name=arcade_name, count=0, action_times=0
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        result = await session.execute(stmt)

        return arcade_id if result.rowcount > 0 else None

    @with_transaction
    async def bind(self, group_id: int, arcade_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = insert(ArcadeBinding).values(group_id=group_id, arcade_id=arcade_id)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_arcade_binding")
        result = await session.execute(stmt)

        return result.rowcount > 0

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

    async def search(self, group_id: int, word: str) -> list[str]:
        bounden_arcade_ids = await self.get_bounden_arcade_ids(group_id)
        matched_ids = list()

        for arcade_id in bounden_arcade_ids:
            arcade = await self.get_arcade(arcade_id)
            if arcade is None:
                continue

            if word in arcade["aliases"]:
                matched_ids.append(arcade_id)

            if word == arcade["name"]:
                matched_ids.append(arcade_id)

        return matched_ids

    async def _filter_arcade_ids(
        self,
        word: str,
        names: list[str],
        scorer,
        score_cutoff: int,
        session: AsyncSession,
    ) -> list[str]:
        results = process.extract(word, names, scorer=scorer, score_cutoff=score_cutoff)
        filtered = []
        for name, _, _ in results:
            stmt = select(Arcade.id).where(Arcade.name == name)
            result = await session.execute(stmt)
            arcade_id = result.scalar_one_or_none()
            if arcade_id is not None:
                filtered.append(arcade_id)
        return list(dict.fromkeys(filtered))

    @with_transaction
    async def search_all(self, word: str, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(ArcadeAlias.arcade_id).where(ArcadeAlias.alias == word)
        result = await session.execute(stmt)
        arcade_ids = [row[0] for row in result.fetchall()]
        if len(arcade_ids) == 1:
            return [arcade_ids[0]]
        elif len(arcade_ids) > 1:
            return arcade_ids

        names = list()
        stmt = select(Arcade.name)
        result = await session.execute(stmt)
        for row in result.fetchall():
            names.append(row[0])

        matched_ids = await self._filter_arcade_ids(
            word, names, scorer=fuzz.QRatio, score_cutoff=100, session=session
        )
        if len(matched_ids) > 0:
            return matched_ids

        matched_ids = await self._filter_arcade_ids(
            word, names, scorer=fuzz.WRatio, score_cutoff=80, session=session
        )

        return matched_ids

    @with_transaction
    async def all_arcade_ids(self, **kwargs) -> list[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(Arcade.id)
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    @with_transaction
    async def add_alias(self, arcade_id: str, alias: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = insert(ArcadeAlias).values(arcade_id=arcade_id, alias=alias)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_arcade_alias")
        result = await session.execute(stmt)

        return result.rowcount > 0

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
            stmt = insert(ArcadeLastAction).values(
                arcade_id=arcade_id,
                group_id=group_id,
                operator_id=operator,
                action_time=time,
                before_count=before,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["arcade_id"],
                set_={
                    "group_id": stmt.excluded.group_id,
                    "operator_id": stmt.excluded.operator_id,
                    "action_time": stmt.excluded.action_time,
                    "before_count": stmt.excluded.before_count,
                },
            )
            await session.execute(stmt)

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
                stmt = insert(ArcadeLastAction).values(
                    arcade_id=arcade_id,
                    group_id=-1,
                    operator_id=-1,
                    action_time=time,
                    before_count=arcade.count,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["arcade_id"],
                    set_={
                        "group_id": stmt.excluded.group_id,
                        "operator_id": stmt.excluded.operator_id,
                        "action_time": stmt.excluded.action_time,
                        "before_count": stmt.excluded.before_count,
                    },
                )
                await session.execute(stmt)

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

        aliases_stmt = select(ArcadeAlias.alias).where(
            ArcadeAlias.arcade_id == arcade.id
        )
        aliases_result = await session.execute(aliases_stmt)
        aliases = [row[0] for row in aliases_result.fetchall()]

        bindings_stmt = select(ArcadeBinding.group_id).where(
            ArcadeBinding.arcade_id == arcade.id
        )
        bindings_result = await session.execute(bindings_stmt)
        bindings = [row[0] for row in bindings_result.fetchall()]

        return {
            "id": arcade.id,
            "name": arcade.name,
            "count": arcade.count,
            "action_times": arcade.action_times,
            "last_action": last_action_dict,
            "aliases": aliases,
            "bindings": bindings,
        }


arcadeManager = ArcadeManager()
