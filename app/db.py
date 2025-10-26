# app/db.py
from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def init_db() -> None:
    # IMPORTÉR ALLE MODELLER HER, så de er registreret før create_all
    from app.models_institution import Institution, Staff, Parent, Child, ChildParentLink, ChildStaffLink
    from app.models_learning import Exercise, ExerciseAnswer, DomainThreshold
    from app.models_progress import DomainProgress
    # Hvis du har en DB-model for brugere, importér den også:
    # from app.models_user import User  # eksempel
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
