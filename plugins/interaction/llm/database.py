from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class ChatContext(Base):
    __tablename__ = "chat_contexts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    context_id: Mapped[str] = mapped_column(String(58), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatMode(Base):
    __tablename__ = "chat_modes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False, index=True
    )
    chat_mode: Mapped[bool] = mapped_column(Boolean, default=False)


class PromptHash(Base):
    __tablename__ = "prompt_hashes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False, index=True
    )
    prompt_hash: Mapped[str] = mapped_column(String(8), nullable=False)


class ContextManager:
    @with_transaction
    async def get_latest_contextid(
        self, chat_id: str, session: AsyncSession
    ) -> Optional[str]:
        stmt = (
            select(ChatContext.context_id)
            .where(ChatContext.chat_id == chat_id)
            .order_by(ChatContext.created_at.desc())
            .limit(1)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def add_contextid(
        self, chat_id: str, context_id: str, session: AsyncSession
    ) -> None:
        new_context = ChatContext(chat_id=chat_id, context_id=context_id)
        session.add(new_context)

    @with_transaction
    async def delete_earliest_contextid(
        self, chat_id: str, session: AsyncSession
    ) -> Optional[str]:
        stmt = (
            select(ChatContext)
            .where(ChatContext.chat_id == chat_id)
            .order_by(ChatContext.created_at.asc())
            .limit(1)
        )

        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            context_id = record.context_id
            await session.delete(record)
            return context_id
        return None

    @with_transaction
    async def get_chatmode(self, chat_id: str, session: AsyncSession) -> bool:
        stmt = select(ChatMode.chat_mode).where(ChatMode.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() or False

    @with_transaction
    async def set_chatmode(
        self, chat_id: str, chat_mode: bool, session: AsyncSession
    ) -> None:
        stmt = select(ChatMode).where(ChatMode.chat_id == chat_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.chat_mode = chat_mode
        else:
            new_record = ChatMode(chat_id=chat_id, chat_mode=chat_mode)
            session.add(new_record)

    @with_transaction
    async def get_prompthash(
        self, chat_id: str, session: AsyncSession
    ) -> Optional[str]:
        stmt = select(PromptHash.prompt_hash).where(PromptHash.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def set_prompthash(
        self, chat_id: str, prompt_hash: str, session: AsyncSession
    ) -> None:
        stmt = select(PromptHash).where(PromptHash.chat_id == chat_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.prompt_hash = prompt_hash
        else:
            new_record = PromptHash(chat_id=chat_id, prompt_hash=prompt_hash)
            session.add(new_record)


contextManager = ContextManager()
