# === FILE: app/db.py
import os
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = os.getenv("SPROKI_DB_URL", "sqlite:///./sproki.db")
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    # For initial bootstrap; switch to Alembic for prod.
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
