from typing import Optional

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import insert
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

        stmt = insert(ChatContext).values(chat_id=chat_id, context_id=context_id)
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"], set_={"context_id": stmt.excluded.context_id}
        )
        await session.execute(stmt)

    @with_transaction
    async def get_prompthash(self, chat_id: str, **kwargs) -> Optional[str]:
        session: AsyncSession = kwargs["session"]

        stmt = select(PromptHash.prompt_hash).where(PromptHash.chat_id == chat_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @with_transaction
    async def set_prompthash(self, chat_id: str, prompt_hash: str, **kwargs) -> None:
        session: AsyncSession = kwargs["session"]

        stmt = insert(PromptHash).values(chat_id=chat_id, prompt_hash=prompt_hash)
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"], set_={"prompt_hash": stmt.excluded.prompt_hash}
        )
        await session.execute(stmt)


contextManager = ContextManager()
