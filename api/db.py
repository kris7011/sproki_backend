from __future__ import annotations
import os
from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from api.settings import settings

# Engine
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    connect_args=connect_args,
)


def init_db() -> None:
    # Import models BEFORE create_all so that SQLModel registers tables
    try:
        from .models_user import User, Role  # noqa: F401
    except Exception:
        pass
    try:
        from .models_report import Report  # noqa: F401
    except Exception:
        pass

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
