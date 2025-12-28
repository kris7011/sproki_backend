# api/db.py
from __future__ import annotations

import os
from typing import Any, Dict, Generator

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


def get_session() -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def open_session() -> Session:
    return Session(engine)


def seed_minimal_data() -> dict:
    # Seed a minimal demo dataset into the SAME DB as the API uses.
    # More robust idempotency: checks both Domain + Exercise.

    from sqlmodel import select
    from app.models import Institution, Parent, Child, Domain, DomainThreshold
    from app.models_exercise import Exercise

    with Session(engine) as session:
        existing_domain = session.exec(
            select(Domain).where(Domain.code == "rim")
        ).first()

        existing_ex = session.exec(
            select(Exercise).where(Exercise.domain == "rim")
        ).first()

        if existing_domain and existing_ex:
            return {"seeded": False, "reason": "demo data already exists"}

        # Institution
        inst = session.exec(select(Institution)).first()
        if not inst:
            inst = Institution(name="Sproki Børnehus")
            session.add(inst)
            session.commit()
            session.refresh(inst)

        assert inst.id is not None
        inst_id: int = inst.id

        # Parent
        parent = session.exec(select(Parent).where(
            Parent.email == "maria@example.com")).first()
        if not parent:
            parent = Parent(name="Mor Maria", email="maria@example.com")
            session.add(parent)
            session.commit()
            session.refresh(parent)

        # Child
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

        # Domain
        if not existing_domain:
            domain_rim = Domain(code="rim", name="Rim", title="Rim og lydleg")
            session.add(domain_rim)
            session.commit()
            session.refresh(domain_rim)
        else:
            domain_rim = existing_domain

        assert domain_rim.id is not None
        domain_id: int = domain_rim.id

        # Threshold (insert only if missing)
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

        # Exercise
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
