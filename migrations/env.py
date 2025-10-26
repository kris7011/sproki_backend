from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Importér alle modeller så autogenerate kan “se” dem
from app.models_progress import DomainProgress  # noqa: F401
from app.models_learning import Exercise, ExerciseAnswer, DomainThreshold  # noqa: F401
from app.models_institution import (  # noqa: F401
    Institution,
    Staff,
    Parent,
    Child,
    ChildParentLink,
    ChildStaffLink,
)

# --- Alembic config object ---
config = context.config

# --- Logging config (fra alembic.ini) ---
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Metadata som Alembic skal bruge til autogenerate ---
target_metadata = SQLModel.metadata

# Konfig-nøgler som konstante
SQLALCHEMY_URL_KEY = "sqlalchemy.url"


def _resolve_db_url() -> str:
    """
    Find DB URL i prioriteret rækkefølge:
      1) env-var DATABASE_URL
      2) app.db.DATABASE_URL (hvis sat)
      3) fallback: sqlite:///./dev.db
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    try:
        from app.db import DATABASE_URL as APP_DB_URL  # type: ignore
        if APP_DB_URL:
            return APP_DB_URL
    except Exception:
        pass
    return "sqlite:///./dev.db"


DB_URL = _resolve_db_url()

# Hvis alembic.ini ikke har en url, sæt den dynamisk her:
if not config.get_main_option(SQLALCHEMY_URL_KEY):
    config.set_main_option(SQLALCHEMY_URL_KEY, DB_URL)


def _effective_url() -> str:
    """Returnér den effektive URL (config-værdi eller DB_URL)."""
    return config.get_main_option(SQLALCHEMY_URL_KEY) or DB_URL


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Kør migrationer i 'offline' mode (kun URL, ingen engine)."""
    url = _effective_url()
    render_as_batch = _is_sqlite(url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Kør migrationer i 'online' mode (engine + connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        url = _effective_url()
        render_as_batch = _is_sqlite(url)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=render_as_batch,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
