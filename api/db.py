from __future__ import annotations

import os
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sproki.db")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)


def init_db() -> None:
    # Import all models so SQLModel.metadata knows all tables before create_all
    from app import models  # noqa: F401

    # Optional modules (only if they exist in your project)
    try:
        from app import models_report  # noqa: F401
    except Exception:
        pass

    try:
        from app import models_learning  # noqa: F401
    except Exception:
        pass

    try:
        from app import models_institution  # noqa: F401
    except Exception:
        pass

    try:
        from app import models_exercise  # noqa: F401
    except Exception:
        pass

    SQLModel.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    # FastAPI dependency: MUST yield
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def open_session() -> Session:
    # Manual usage: with open_session() as session:
    return Session(engine)
