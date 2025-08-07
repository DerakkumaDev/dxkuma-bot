from typing import Optional

import orjson
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    ForeignKey,
    Text,
    UniqueConstraint,
    delete,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from util.database import Base, with_transaction
from .utils import generate_game_data, check_char_in_text


class WordleGame(Base):
    __tablename__ = "wordle_games"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, index=True
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
    @with_transaction
    async def start(self, group_id: str, **kwargs) -> dict:
        session: AsyncSession = kwargs["session"]

        for i in range(3):
            stmt = select(WordleGame).where(WordleGame.group_id == group_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                return await self._build_game_data(record, session)

            game_data = await generate_game_data()

            new_game = WordleGame(group_id=group_id)
            session.add(new_game)
            try:
                await session.flush()
                break
            except IntegrityError:
                if i >= 2:
                    raise

                await session.rollback()
                continue

        for content in game_data["game_contents"]:
            game_content = WordleGameContent(
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
            session.add(game_content)

        return game_data

    @with_transaction
    async def game_over(self, group_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = (
            select(WordleGame).where(WordleGame.group_id == group_id).with_for_update()
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            await session.delete(record)
            return True
        return False

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

        new_char = WordleOpenChar(game_id=record.id, char=chars.casefold())
        session.add(new_char)

        try:
            await session.flush()
        except IntegrityError:
            return False, None

        stmt = (
            select(WordleGameContent)
            .where(WordleGameContent.game_id == record.id)
            .order_by(WordleGameContent.id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        game_contents = result.scalars().all()

        for content in game_contents:
            if check_char_in_text(content.title, chars):
                part_list = orjson.loads(content.part) if content.part else list()
                if user_id not in part_list:
                    part_list.append(user_id)
                    content.part = orjson.dumps(part_list).decode()

                content.opc_times += 1

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

        if record:
            return await self._build_game_data(record, session)
        return None

    @with_transaction
    async def update_game_data(self, group_id: str, game_data: dict, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = (
            select(WordleGame).where(WordleGame.group_id == group_id).with_for_update()
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            record = WordleGame(group_id=group_id)
            session.add(record)
        else:
            await session.execute(
                delete(WordleOpenChar).where(WordleOpenChar.game_id == record.id)
            )
            await session.execute(
                delete(WordleGameContent).where(WordleGameContent.game_id == record.id)
            )

        await session.flush()

        for char in game_data.get("open_chars", list()):
            open_char = WordleOpenChar(game_id=record.id, char=char)
            session.add(open_char)

        for content in game_data.get("game_contents", list()):
            game_content = WordleGameContent(
                game_id=record.id,
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
            session.add(game_content)

        await session.flush()

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


openchars = OpenChars()
