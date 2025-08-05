from typing import Optional, Dict, Any, List

import orjson
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from util.database import Base, with_transaction
from .utils import generate_game_data, check_char_in_text


class WordleGame(Base):
    __tablename__ = "wordle_games"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(
        String(9), unique=True, nullable=False, index=True
    )

    open_chars: Mapped[List["WordleOpenChar"]] = relationship(
        "WordleOpenChar", back_populates="game", cascade="all, delete-orphan"
    )
    game_contents: Mapped[List["WordleGameContent"]] = relationship(
        "WordleGameContent", back_populates="game", cascade="all, delete-orphan"
    )


class WordleOpenChar(Base):
    __tablename__ = "wordle_open_chars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("wordle_games.id"), nullable=False)
    char: Mapped[str] = mapped_column(String(16), nullable=False)

    game: Mapped["WordleGame"] = relationship("WordleGame", back_populates="open_chars")


class WordleGameContent(Base):
    __tablename__ = "wordle_game_contents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("wordle_games.id"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    music_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    tips: Mapped[str] = mapped_column(Text, nullable=True)
    pic_times: Mapped[int] = mapped_column(Integer, default=0)
    aud_times: Mapped[int] = mapped_column(Integer, default=0)
    opc_times: Mapped[int] = mapped_column(Integer, default=0)
    part: Mapped[str] = mapped_column(Text, nullable=True)

    game: Mapped["WordleGame"] = relationship(
        "WordleGame", back_populates="game_contents"
    )


class OpenChars:
    @with_transaction
    async def start(self, group_id: str, session: AsyncSession) -> Dict[str, Any]:
        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            return await self._build_game_data(record)

        game_data = await generate_game_data()

        new_game = WordleGame(group_id=group_id)
        session.add(new_game)
        await session.flush()

        for content in game_data["game_contents"]:
            game_content = WordleGameContent(
                game_id=new_game.id,
                index=content["index"],
                title=content["title"],
                music_id=content["music_id"],
                is_correct=content["is_correct"],
                tips=orjson.dumps(content.get("tips", [])).decode(),
                pic_times=content["pic_times"],
                aud_times=content["aud_times"],
                opc_times=content["opc_times"],
                part=orjson.dumps(content.get("part", [])).decode(),
            )
            session.add(game_content)

        return game_data

    @with_transaction
    async def game_over(self, group_id: str, session: AsyncSession) -> bool:
        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            await session.delete(record)
            return True
        return False

    @with_transaction
    async def open_char(
        self, group_id: str, chars: str, user_id: str, session: AsyncSession
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return None, None

        stmt = select(WordleOpenChar).where(
            WordleOpenChar.game_id == record.id, WordleOpenChar.char == chars.casefold()
        )
        result = await session.execute(stmt)
        existing_char = result.scalar_one_or_none()

        if existing_char:
            return False, None

        new_char = WordleOpenChar(game_id=record.id, char=chars.casefold())
        session.add(new_char)

        stmt = select(WordleGameContent).where(WordleGameContent.game_id == record.id)
        result = await session.execute(stmt)
        game_contents = result.scalars().all()

        for content in game_contents:
            if check_char_in_text(content.title, chars):
                part_list = orjson.loads(content.part) if content.part else []
                if user_id not in part_list:
                    part_list.append(user_id)
                    content.part = orjson.dumps(part_list).decode()

                content.opc_times += 1

        game_data = await self._build_game_data(record, session)
        return True, game_data

    @with_transaction
    async def get_game_data(
        self, group_id: str, session: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            return await self._build_game_data(record, session)
        return None

    @with_transaction
    async def update_game_data(
        self, group_id: str, game_data: Dict[str, Any], session: AsyncSession
    ) -> None:
        stmt = select(WordleGame).where(WordleGame.group_id == group_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            await session.delete(record)
            await session.flush()

        new_game = WordleGame(group_id=group_id)
        session.add(new_game)
        await session.flush()

        for char in game_data.get("open_chars", []):
            open_char = WordleOpenChar(game_id=new_game.id, char=char)
            session.add(open_char)

        for content in game_data.get("game_contents", []):
            game_content = WordleGameContent(
                game_id=new_game.id,
                index=content["index"],
                title=content["title"],
                music_id=content["music_id"],
                is_correct=content["is_correct"],
                tips=orjson.dumps(content.get("tips", [])).decode(),
                pic_times=content["pic_times"],
                aud_times=content["aud_times"],
                opc_times=content["opc_times"],
                part=orjson.dumps(content.get("part", [])).decode(),
            )
            session.add(game_content)

    async def _build_game_data(self, game_record: WordleGame, session: AsyncSession) -> Dict[str, Any]:
        open_chars_stmt = select(WordleOpenChar.char).where(WordleOpenChar.game_id == game_record.id)
        open_chars_result = await session.execute(open_chars_stmt)
        open_chars = [row[0] for row in open_chars_result.fetchall()]

        game_contents_stmt = select(WordleGameContent).where(WordleGameContent.game_id == game_record.id)
        game_contents_result = await session.execute(game_contents_stmt)
        game_contents_records = game_contents_result.scalars().all()

        game_contents = []
        for content in game_contents_records:
            game_content = {
                "index": content.index,
                "title": content.title,
                "music_id": content.music_id,
                "is_correct": content.is_correct,
                "tips": orjson.loads(content.tips) if content.tips else [],
                "pic_times": content.pic_times,
                "aud_times": content.aud_times,
                "opc_times": content.opc_times,
                "part": orjson.loads(content.part) if content.part else [],
            }
            game_contents.append(game_content)

        return {"open_chars": open_chars, "game_contents": game_contents}


openchars = OpenChars()
