from typing import Optional

from sqlalchemy import String, Boolean
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, mapped_column

from util.database import Base, with_transaction


class ChatContext(Base):
    __tablename__ = "chat_contexts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False, index=True
    )
    context_id: Mapped[str] = mapped_column(String(58), nullable=False)


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
    async def get_contextid(self, chat_id: str, **kwargs) -> Optional[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(ChatContext.context_id).where(ChatContext.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def set_contextid(self, chat_id: str, context_id: str, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = select(ChatContext).where(ChatContext.chat_id == chat_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.context_id = context_id
        else:
            new_context = ChatContext(chat_id=chat_id, context_id=context_id)
            session.add(new_context)

    @with_transaction
    async def get_chatmode(self, chat_id: str, **kwargs) -> bool:
        session: AsyncSession = kwargs["session"]

        stmt = select(ChatMode.chat_mode).where(ChatMode.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() or False

    @with_transaction
    async def set_chatmode(self, chat_id: str, chat_mode: bool, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = select(ChatMode).where(ChatMode.chat_id == chat_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.chat_mode = chat_mode
        else:
            new_record = ChatMode(chat_id=chat_id, chat_mode=chat_mode)
            session.add(new_record)

    @with_transaction
    async def get_prompthash(self, chat_id: str, **kwargs) -> Optional[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(PromptHash.prompt_hash).where(PromptHash.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def set_prompthash(self, chat_id: str, prompt_hash: str, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = select(PromptHash).where(PromptHash.chat_id == chat_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            record.prompt_hash = prompt_hash
        else:
            new_record = PromptHash(chat_id=chat_id, prompt_hash=prompt_hash)
            session.add(new_record)


contextManager = ContextManager()
