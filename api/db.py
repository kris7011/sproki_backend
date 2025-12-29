# api/db.py
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, Generator

from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine


def _is_render() -> bool:
    return os.getenv("RENDER", "").lower() == "true" or bool(os.getenv("RENDER_SERVICE_ID"))


def _get_database_url() -> str:
    default_local = "sqlite:///./sproki.db"
    default_render = "sqlite:////data/sproki.db"

    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url

    if os.path.isdir("/data"):
        return default_render

    return default_local


DATABASE_URL = _get_database_url()

connect_args: Dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # wait on locks (seconds)
    }

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)


def _sqlite_db_path() -> str | None:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return None
    return engine.url.database


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (table,),
    )
    return cur.fetchone() is not None


def _cols(cur: sqlite3.Cursor, table: str) -> dict[str, dict]:
    cur.execute(f"PRAGMA table_info('{table}')")
    out: dict[str, dict] = {}
    for cid, name, col_type, notnull, dflt_value, pk in cur.fetchall():
        out[name] = {
            "type": col_type,
            "notnull": int(notnull),
            "default": dflt_value,
            "pk": int(pk),
        }
    return out


def _sqlite_migrate() -> None:
    db_path = _sqlite_db_path()
    if not db_path:
        return

    print(f"[db] DATABASE_URL={str(engine.url)} sqlite_path={db_path}")

    if _is_render() and not os.path.isdir("/data"):
        print(
            "[db] WARNING: Render detected but /data is not mounted. DB may be ephemeral.")

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    if not _table_exists(cur, "childreport"):
        con.close()
        return

    cols = _cols(cur, "childreport")
    if "source" not in cols:
        cur.execute(
            "ALTER TABLE childreport ADD COLUMN source TEXT DEFAULT 'unknown'")
    if "age_months" not in cols:
        cur.execute(
            "ALTER TABLE childreport ADD COLUMN age_months INTEGER DEFAULT 0")

    if _table_exists(cur, "childreportscore"):
        cols = _cols(cur, "childreportscore")
        if "domain_id" not in cols:
            cur.execute(
                "ALTER TABLE childreportscore ADD COLUMN domain_id INTEGER")
        if "raw_score" not in cols:
            cur.execute(
                "ALTER TABLE childreportscore ADD COLUMN raw_score INTEGER DEFAULT 0")

        cols = _cols(cur, "childreportscore")
        item_id_notnull = ("item_id" in cols) and (
            cols["item_id"]["notnull"] == 1)

        if item_id_notnull:
            cur.execute("BEGIN")
            cur.execute(
                "ALTER TABLE childreportscore RENAME TO childreportscore_old")

            cur.execute(
                """
                CREATE TABLE childreportscore (
                    id INTEGER PRIMARY KEY,
                    report_id INTEGER NOT NULL,
                    item_id INTEGER,
                    domain TEXT DEFAULT 'unknown',
                    score INTEGER DEFAULT 0,
                    max_score INTEGER DEFAULT 1,
                    note TEXT,
                    domain_id INTEGER,
                    raw_score INTEGER DEFAULT 0
                )
                """
            )

            cur.execute(
                """
                INSERT INTO childreportscore (id, report_id, item_id, domain, score, max_score, note, domain_id, raw_score)
                SELECT
                    id,
                    report_id,
                    item_id,
                    COALESCE(domain, 'unknown'),
                    COALESCE(score, 0),
                    COALESCE(max_score, 1),
                    note,
                    domain_id,
                    COALESCE(raw_score, COALESCE(score, 0))
                FROM childreportscore_old
                """
            )

            cur.execute("DROP TABLE childreportscore_old")
            cur.execute("COMMIT")

    con.commit()
    con.close()


def init_db() -> None:
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
            pass

    SQLModel.metadata.create_all(bind=engine)

    try:
        _sqlite_migrate()
    except Exception as e:
        print("sqlite migrate failed:", repr(e))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def open_session() -> Session:
    return Session(engine)


def seed_minimal_data() -> dict:
    from sqlmodel import select
    from app.models import Institution, Parent, Child, Domain, DomainThreshold
    from app.models_exercise import Exercise

    with Session(engine) as session:
        existing_domain = session.exec(
            select(Domain).where(Domain.code == "rim")).first()
        existing_ex = session.exec(select(Exercise).where(
            Exercise.domain == "rim")).first()

        if existing_domain and existing_ex:
            return {"seeded": False, "reason": "demo data already exists"}

        inst = session.exec(select(Institution)).first()
        if not inst:
            inst = Institution(name="Sproki Børnehus")
            session.add(inst)
            session.commit()
            session.refresh(inst)

        assert inst.id is not None
        inst_id: int = inst.id

        parent = session.exec(select(Parent).where(
            Parent.email == "maria@example.com")).first()
        if not parent:
            parent = Parent(name="Mor Maria", email="maria@example.com")
            session.add(parent)
            session.commit()
            session.refresh(parent)

        child = session.exec(select(Child).where(Child.name == "Alma")).first()
        if not child:
            child = Child(
                name="Alma",
                age_years=4,
                age_months=3,
                institution_id=inst_id,
                ppr_consent=True,
            )
            session.add(child)
            session.commit()
            session.refresh(child)

        assert child.id is not None
        child_id: int = child.id

        if not existing_domain:
            domain_rim = Domain(code="rim", name="Rim", title="Rim og lydleg")
            session.add(domain_rim)
            session.commit()
            session.refresh(domain_rim)
        else:
            domain_rim = existing_domain

        assert domain_rim.id is not None
        domain_id: int = domain_rim.id

        existing_th = session.exec(
            select(DomainThreshold).where(
                DomainThreshold.domain_id == domain_id)
        ).first()

        if not existing_th:
            th_rim = DomainThreshold(
                domain_id=domain_id,
                age_years_min=4,
                age_months_min=0,
                age_years_max=5,
                age_months_max=11,
                score_min_green=40,
                score_min_yellow=30,
            )
            session.add(th_rim)

        if not existing_ex:
            ex1 = Exercise(
                domain="rim",
                title="Rim: kat",
                description="Enkel rim-øvelse",
                min_age_months=48,
                max_age_months=71,
                content_ref=None,
                mastery_target_correct=8,
                mastery_window=10,
                is_active=True,
            )
            session.add(ex1)
            session.commit()
            session.refresh(ex1)
            assert ex1.id is not None
            ex_id = ex1.id
        else:
            ex_id = existing_ex.id

        session.commit()

        return {
            "seeded": True,
            "child_id": child_id,
            "exercise_id": ex_id,
            "domain": domain_rim.code,
        }
