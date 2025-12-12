# app/db.py
from __future__ import annotations

from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine


# Very simple SQLite setup. File = sproki.db in projektroden.
DATABASE_URL = "sqlite:///./sproki.db"

engine = create_engine(
    DATABASE_URL,
    echo=False,      # sæt True hvis du vil se SQL i konsollen
    future=True,
)


def init_db() -> None:
    """
    Importér alle modeller og opret tabellerne hvis de ikke findes.
    Kaldes fra app.main:on_startup()
    """
    # Sørg for at alle modeller er importeret, så SQLModel.metadata
    # kender tabellerne, inden vi kalder create_all.
    from app import models            # noqa: F401
    from app import models_report     # noqa: F401
    from app import models_learning   # noqa: F401
    from app import models_institution  # noqa: F401

    SQLModel.metadata.create_all(bind=engine)


def get_session() -> Session:
    """
    Returnér en almindelig SQLModel Session.
    Din kode kan så gøre:

        session = get_session()
        ...
        session.add(obj)
        session.commit()

    eller

        with get_session() as session:
            ...

    (Session er selv en context manager.)
    """
    return Session(engine)
