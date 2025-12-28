from __future__ import annotations

import os
from typing import Generator, Dict, Any

from sqlmodel import SQLModel, Session, create_engine


def _get_database_url() -> str:
    # Local default
    default_local = "sqlite:///./sproki.db"

    # Render persistent disk (recommended)
    # If you mount a disk at /data, use sqlite:////data/sproki.db (4 slashes)
    default_render = "sqlite:////data/sproki.db"

    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()

    # Heuristic: if Render disk likely exists, prefer persistent sqlite
    # (won't break locally because /data usually doesn't exist, but you should set DATABASE_URL locally anyway)
    if os.path.isdir("/data"):
        return default_render

    return default_local


DATABASE_URL = _get_database_url()

connect_args: Dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed for sqlite with multiple threads in FastAPI/Uvicorn
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)


def init_db() -> None:
    # Import all models so SQLModel.metadata knows all tables before create_all.
    #
    # IMPORTANT:
    # Only import modules that define SQLModel(table=True) models.
    # If you have duplicates across app/* and api/*, prefer ONE place.
    # Your project currently uses app.models_* as the source of truth.
    try:
        from app import models  # noqa: F401
    except Exception as e:
        print("init_db: failed importing app.models:", repr(e))

    for mod in (
        "app.models_report",
        "app.models_exercise",
        "app.models_learning",
        "app.models_institution",
    ):
        try:
            __import__(mod)
        except Exception:
            # Optional modules
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
