from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine


# Use DATABASE_URL if set, otherwise default to a local SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sproki.db")

# Single shared engine for the backend
engine = create_engine(
    DATABASE_URL,
    echo=False,
)


def init_db() -> None:
    """
    Initialize database schema.

    Imports all model modules so that SQLModel is aware of every table,
    and then creates any missing tables in the database.
    """
    # Import *all* modules that define SQLModel tables
    from app import models          # noqa: F401
    from app import models_institution  # noqa: F401
    from app import models_exercise     # noqa: F401
    from app import models_report       # noqa: F401

    SQLModel.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """
    Simple context manager to get a Session:

        from app.db import get_session

        with get_session() as session:
            ...

    """
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
