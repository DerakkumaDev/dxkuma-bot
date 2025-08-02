from openai import NOT_GIVEN
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///data/llm.db"
engine = create_engine(DATABASE_URL, echo=False)

Base = declarative_base()


class ContextId(Base):
    __tablename__ = "contexts"

    chat_id = Column(String, primary_key=True)
    context_id = Column(String, nullable=False)


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

    def get_contextid(self, chat_id: str):
        with SessionLocal() as session:
            context_id = (
                session.query(ContextId).filter(ContextId.chat_id == chat_id).first()
            )
            if context_id is None:
                return NOT_GIVEN
            return context_id.context_id

    def set_contextid(self, chat_id: str, context_id: str):
        with SessionLocal() as session:
            existing = (
                session.query(ContextId).filter(ContextId.chat_id == chat_id).first()
            )
            if existing:
                existing.context_id = context_id
            else:
                new_context_id = ContextId(chat_id=chat_id, context_id=context_id)
                session.add(new_context_id)
            session.commit()

    def get_chatmode(self, chat_id: str):
        with SessionLocal() as session:
            chat_mode = (
                session.query(ChatMode).filter(ChatMode.chat_id == chat_id).first()
            )
            if chat_mode is None:
                return False
            return chat_mode.chat_mode

    def set_chatmode(self, chat_id: str, chat_mode: bool):
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

    def get_prompthash(self, chat_id: str):
        with SessionLocal() as session:
            prompt_hash = (
                session.query(PromptHash).filter(PromptHash.chat_id == chat_id).first()
            )
            if prompt_hash is None:
                return None
            return prompt_hash.prompt_hash

    def set_prompthash(self, chat_id: str, prompt_hash: str):
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
