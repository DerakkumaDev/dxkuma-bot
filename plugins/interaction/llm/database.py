from sqlalchemy import create_engine, Column, String, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional

DATABASE_URL = "sqlite:///data/llm.db"
engine = create_engine(DATABASE_URL, echo=False)

Base = declarative_base()


class ContextId(Base):
    __tablename__ = "contexts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False)
    context_id = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False)


class ChatMode(Base):
    __tablename__ = "chat_modes"

    chat_id = Column(String, primary_key=True)
    chat_mode = Column(Boolean, default=False)


class PromptHash(Base):
    __tablename__ = "prompt_hashs"

    chat_id = Column(String, primary_key=True)
    prompt_hash = Column(String, nullable=False)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ContextManager(object):
    def __init__(self):
        Base.metadata.create_all(engine)

    def get_latest_contextid(self, chat_id: str) -> Optional[str]:
        with SessionLocal() as session:
            latest_context = (
                session.query(ContextId)
                .filter(ContextId.chat_id == chat_id)
                .order_by(ContextId.order_index.desc())
                .first()
            )
            if latest_context is None:
                return None

            return latest_context.context_id

    def add_contextid(self, chat_id: str, context_id: str) -> None:
        with SessionLocal() as session:
            max_order = (
                session.query(ContextId)
                .filter(ContextId.chat_id == chat_id)
                .order_by(ContextId.order_index.desc())
                .first()
            )

            next_order = 0 if max_order is None else max_order.order_index + 1

            new_context = ContextId(
                chat_id=chat_id, context_id=context_id, order_index=next_order
            )
            session.add(new_context)
            session.commit()

    def delete_earliest_contextid(self, chat_id: str) -> Optional[str]:
        with SessionLocal() as session:
            earliest_context = (
                session.query(ContextId)
                .filter(ContextId.chat_id == chat_id)
                .order_by(ContextId.order_index.asc())
                .first()
            )

            if earliest_context is None:
                return None

            context_id = earliest_context.context_id
            session.delete(earliest_context)
            session.commit()
            return context_id

    def get_chatmode(self, chat_id: str) -> bool:
        with SessionLocal() as session:
            chat_mode = (
                session.query(ChatMode).filter(ChatMode.chat_id == chat_id).first()
            )
            if chat_mode is None:
                return False

            return chat_mode.chat_mode

    def set_chatmode(self, chat_id: str, chat_mode: bool) -> None:
        with SessionLocal() as session:
            existing = (
                session.query(ChatMode).filter(ChatMode.chat_id == chat_id).first()
            )
            if existing:
                existing.chat_mode = chat_mode
            else:
                new_chat_mode = ChatMode(chat_id=chat_id, chat_mode=chat_mode)
                session.add(new_chat_mode)

            session.commit()

    def get_prompthash(self, chat_id: str) -> Optional[str]:
        with SessionLocal() as session:
            prompt_hash = (
                session.query(PromptHash).filter(PromptHash.chat_id == chat_id).first()
            )
            if prompt_hash is None:
                return None

            return prompt_hash.prompt_hash

    def set_prompthash(self, chat_id: str, prompt_hash: str) -> None:
        with SessionLocal() as session:
            existing = (
                session.query(PromptHash).filter(PromptHash.chat_id == chat_id).first()
            )
            if existing:
                existing.prompt_hash = prompt_hash
            else:
                new_prompt_hash = PromptHash(chat_id=chat_id, prompt_hash=prompt_hash)
                session.add(new_prompt_hash)

            session.commit()


contextManager = ContextManager()
