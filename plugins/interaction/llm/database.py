from sqlalchemy import create_engine, Column, String, Text, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///data/llm.db"
engine = create_engine(DATABASE_URL, echo=False)

Base = declarative_base()


class Context(Base):
    __tablename__ = "contexts"

    context_id = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(Integer, nullable=False)


class ChatMode(Base):
    __tablename__ = "chat_modes"

    id = Column(String, primary_key=True)
    chat_mode = Column(Boolean, default=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CONTEXT_LIMIT = 50 - 1


class ContextManager(object):
    def __init__(self):
        Base.metadata.create_all(engine)

    def get_context(self, id: str):
        with SessionLocal() as session:
            contexts = (
                session.query(Context)
                .filter(Context.id == id)
                .order_by(Context.timestamp)
                .all()
            )
            return [{"role": ctx.role, "content": ctx.content} for ctx in contexts]

    def add_to_context(self, id: str, role: str, message: str):
        with SessionLocal() as session:
            import time

            timestamp = int(time.time())

            new_context = Context(
                id=id, role=role, content=message, timestamp=timestamp
            )
            session.add(new_context)
            session.commit()

            contexts = (
                session.query(Context)
                .filter(Context.id == id)
                .order_by(Context.timestamp)
                .all()
            )
            if len(contexts) > CONTEXT_LIMIT:
                contexts_to_delete = contexts[:-CONTEXT_LIMIT]
                for ctx in contexts_to_delete:
                    session.delete(ctx)
                session.commit()

    def get_chatmode(self, id: str):
        with SessionLocal() as session:
            chat_mode = session.query(ChatMode).filter(ChatMode.id == id).first()
            if chat_mode is None:
                return True
            return chat_mode.chat_mode

    def set_chatmode(self, id: str, chat_mode: bool):
        with SessionLocal() as session:
            existing = session.query(ChatMode).filter(ChatMode.id == id).first()
            if existing:
                existing.chat_mode = chat_mode
            else:
                new_chat_mode = ChatMode(id=id, chat_mode=chat_mode)
                session.add(new_chat_mode)
            session.commit()


contextManager = ContextManager()
