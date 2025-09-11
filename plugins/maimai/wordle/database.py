from datetime import datetime, timedelta
from typing import Optional

import orjson
from numpy import random
from pykakasi import kakasi
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from util.data import get_music_data_lxns
from util.database import Base, with_transaction

kks = kakasi()


class WordleGame(Base):
    __tablename__ = "wordle_games"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    open_chars: Mapped[list["WordleOpenChar"]] = relationship(
        "WordleOpenChar", back_populates="game", cascade="all, delete-orphan"
    )
    game_contents: Mapped[list["WordleGameContent"]] = relationship(
        "WordleGameContent", back_populates="game", cascade="all, delete-orphan"
    )


class WordleOpenChar(Base):
    __tablename__ = "wordle_open_chars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("wordle_games.id", ondelete="CASCADE"), nullable=False
    )
    char: Mapped[str] = mapped_column(String(16), nullable=False)

    game: Mapped["WordleGame"] = relationship("WordleGame", back_populates="open_chars")

    __table_args__ = (UniqueConstraint("game_id", "char", name="uq_game_char"),)


class WordleGameContent(Base):
    __tablename__ = "wordle_game_contents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("wordle_games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    music_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tips: Mapped[str] = mapped_column(Text, nullable=True)
    pic_times: Mapped[int] = mapped_column(Integer, default=0)
    aud_times: Mapped[int] = mapped_column(Integer, default=0)
    opc_times: Mapped[int] = mapped_column(Integer, default=0)
    part: Mapped[str] = mapped_column(Text, nullable=True)

    game: Mapped["WordleGame"] = relationship(
        "WordleGame", back_populates="game_contents"
    )

    __table_args__ = (UniqueConstraint("game_id", "index", name="uq_game_index"),)


class OpenChars:
    async def _generate_game_data(self) -> dict:
        rng = random.default_rng()
        game_data = {"open_chars": list()}
        game_contents = list()
        while len(game_contents) <= 4:
            music = rng.choice((await get_music_data_lxns())["songs"])
            game_contents.append(
                {
                    "index": len(game_contents) + 1,
                    "title": music["title"],
                    "music_id": music["id"],
                    "is_correct": False,
                    "tips": list(),
                    "pic_times": 0,
                    "aud_times": 0,
                    "opc_times": 0,
                    "part": list(),
                }
            )
        game_data["game_contents"] = game_contents
        return game_data

    def _check_char_in_text(self, text: str, char: str) -> bool:
        text = text.casefold()
        if char.casefold() in text:
            return True

        for c in kks.convert(char):
            for v in c.values():
                if v.casefold() in text:
                    return True

        return False

    @with_transaction
    async def start(self, group_id: str, **kwargs) -> dict:
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            if datetime.now() - record.updated_at > timedelta(hours=12):
                await session.delete(record)
                await session.flush()
            else:
                return await self._build_game_data(record, session)

        game_data = await self._generate_game_data()

        stmt = insert(WordleGame).values(group_id=group_id, updated_at=datetime.now())
        stmt = stmt.on_conflict_do_update(
            index_elements=["group_id"],
            set_={
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
        await session.flush()

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        new_game = result.scalar_one()

        for content in game_data["game_contents"]:
            stmt = insert(WordleGameContent).values(
                game_id=new_game.id,
                index=content["index"],
                title=content["title"],
                music_id=content["music_id"],
                is_correct=content["is_correct"],
                tips=orjson.dumps(content.get("tips", list())).decode(),
                pic_times=content["pic_times"],
                aud_times=content["aud_times"],
                opc_times=content["opc_times"],
                part=orjson.dumps(content.get("part", list())).decode(),
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_game_index",
                set_={
                    "title": stmt.excluded.title,
                    "music_id": stmt.excluded.music_id,
                    "is_correct": stmt.excluded.is_correct,
                    "tips": stmt.excluded.tips,
                    "pic_times": stmt.excluded.pic_times,
                    "aud_times": stmt.excluded.aud_times,
                    "opc_times": stmt.excluded.opc_times,
                    "part": stmt.excluded.part,
                },
            )

            await session.execute(stmt)

        return game_data

    @with_transaction
    async def game_over(self, group_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        await session.delete(record)
        return True

    @with_transaction
    async def open_char(
        self, group_id: str, chars: str, user_id: str, **kwargs
    ) -> tuple[bool, Optional[dict]]:
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False, None

        if datetime.now() - record.updated_at > timedelta(hours=12):
            await session.delete(record)
            await session.flush()
            return False, None

        stmt = insert(WordleOpenChar).values(game_id=record.id, char=chars.casefold())
        stmt = stmt.on_conflict_do_nothing(constraint="uq_game_char")
        result = await session.execute(stmt)

        if result.rowcount == 0:
            return False, None

        stmt = (
            select(WordleGameContent)
            .where(WordleGameContent.game_id == record.id)
            .order_by(WordleGameContent.id)
        )
        result = await session.execute(stmt)
        game_contents = result.scalars().all()

        for content in game_contents:
            if self._check_char_in_text(content.title, chars):
                part_list = orjson.loads(content.part) if content.part else list()
                if user_id not in part_list:
                    part_list.append(user_id)
                    content.part = orjson.dumps(part_list).decode()

                content.opc_times += 1

        record.updated_at = datetime.now()

        await session.flush()
        with session.no_autoflush:
            game_data = await self._build_game_data(record, session)

        return True, game_data

    @with_transaction
    async def get_game_data(self, group_id: str, **kwargs) -> Optional[dict]:
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None

        if datetime.now() - record.updated_at > timedelta(hours=12):
            await session.delete(record)
            await session.flush()
            return None

        return await self._build_game_data(record, session)

    @with_transaction
    async def update_game_content_field(
        self, group_id: str, content_index: int, field: str, value, **kwargs
    ) -> bool:
        """更新游戏内容中的特定字段"""
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        if datetime.now() - record.updated_at > timedelta(hours=12):
            await session.delete(record)
            await session.flush()
            return False

        stmt = select(WordleGameContent).where(
            WordleGameContent.game_id == record.id,
            WordleGameContent.index == content_index,
        )
        result = await session.execute(stmt)
        content = result.scalar_one_or_none()

        if not content:
            return False

        # 根据字段类型进行相应的更新
        if field == "part":
            if isinstance(value, list):
                content.part = orjson.dumps(value).decode()
            else:
                part_list = orjson.loads(content.part) if content.part else list()
                if value not in part_list:
                    part_list.append(value)
                    content.part = orjson.dumps(part_list).decode()
        elif field == "tips":
            if isinstance(value, list):
                content.tips = orjson.dumps(value).decode()
            else:
                tips_list = orjson.loads(content.tips) if content.tips else list()
                if value not in tips_list:
                    tips_list.append(value)
                    content.tips = orjson.dumps(tips_list).decode()
        elif field == "pic_times":
            content.pic_times = value
        elif field == "aud_times":
            content.aud_times = value
        elif field == "opc_times":
            content.opc_times = value
        elif field == "is_correct":
            content.is_correct = value
        else:
            return False

        record.updated_at = datetime.now()
        await session.flush()
        return True

    @with_transaction
    async def add_user_to_content_part(
        self, group_id: str, content_index: int, user_id: str, **kwargs
    ) -> bool:
        """将用户添加到指定内容的参与者列表中"""
        return await self.update_game_content_field(
            group_id, content_index, "part", user_id, **kwargs
        )

    @with_transaction
    async def add_tip_to_content(
        self, group_id: str, content_index: int, tip: str, **kwargs
    ) -> bool:
        """向指定内容添加提示"""
        return await self.update_game_content_field(
            group_id, content_index, "tips", tip, **kwargs
        )

    @with_transaction
    async def increment_content_counter(
        self, group_id: str, content_index: int, counter_type: str, **kwargs
    ) -> bool:
        """增加指定内容的计数器"""
        if counter_type not in ["pic_times", "aud_times", "opc_times"]:
            return False

        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        if datetime.now() - record.updated_at > timedelta(hours=12):
            await session.delete(record)
            await session.flush()
            return False

        stmt = select(WordleGameContent).where(
            WordleGameContent.game_id == record.id,
            WordleGameContent.index == content_index,
        )
        result = await session.execute(stmt)
        content = result.scalar_one_or_none()

        if not content:
            return False

        if counter_type == "pic_times":
            content.pic_times += 1
        elif counter_type == "aud_times":
            content.aud_times += 1
        elif counter_type == "opc_times":
            content.opc_times += 1

        record.updated_at = datetime.now()
        await session.flush()
        return True

    @with_transaction
    async def mark_content_as_correct(
        self, group_id: str, content_index: int, **kwargs
    ) -> bool:
        """将指定内容标记为正确"""
        return await self.update_game_content_field(
            group_id, content_index, "is_correct", True, **kwargs
        )

    async def _build_game_data(
        self, game_record: WordleGame, session: AsyncSession
    ) -> dict:
        open_chars_stmt = select(WordleOpenChar.char).where(
            WordleOpenChar.game_id == game_record.id
        )
        open_chars_result = await session.execute(open_chars_stmt)
        open_chars = [row[0] for row in open_chars_result.fetchall()]

        game_contents_stmt = (
            select(WordleGameContent)
            .where(WordleGameContent.game_id == game_record.id)
            .order_by(WordleGameContent.index)
        )
        game_contents_result = await session.execute(game_contents_stmt)
        game_contents_records = game_contents_result.scalars().all()

        game_contents = list()
        for content in game_contents_records:
            game_content = {
                "index": content.index,
                "title": content.title,
                "music_id": content.music_id,
                "is_correct": content.is_correct,
                "tips": orjson.loads(content.tips) if content.tips else list(),
                "pic_times": content.pic_times,
                "aud_times": content.aud_times,
                "opc_times": content.opc_times,
                "part": orjson.loads(content.part) if content.part else list(),
            }
            game_contents.append(game_content)

        return {"open_chars": open_chars, "game_contents": game_contents}

    @with_transaction
    async def is_gaming(self, group_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return False

        if datetime.now() - record.updated_at > timedelta(hours=12):
            await session.delete(record)
            await session.flush()
            return False

        return True


openchars = OpenChars()
