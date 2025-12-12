# scripts/seed_dev_data.py
from __future__ import annotations

from sqlmodel import Session, select

from api.db import engine, init_db
from app.models_report import Domain, Threshold
from app.models_exercise import Exercise


def get_or_create_domain(session: Session, code: str, name: str) -> Domain:
    stmt = select(Domain).where(Domain.code == code)
    domain = session.exec(stmt).first()
    if domain:
        return domain

    domain = Domain(code=code, name=name)
    session.add(domain)
    session.commit()
    session.refresh(domain)
    return domain


def get_or_create_threshold(
    session: Session,
    domain_id: int,
    min_age_months: int,
    max_age_months: int,
    yellow_min: int,
    green_min: int,
) -> Threshold:
    stmt = (
        select(Threshold)
        .where(Threshold.domain_id == domain_id)
        .where(Threshold.min_age_months == min_age_months)
        .where(Threshold.max_age_months == max_age_months)
    )
    th = session.exec(stmt).first()
    if th:
        return th

    th = Threshold(
        domain_id=domain_id,
        min_age_months=min_age_months,
        max_age_months=max_age_months,
        yellow_min=yellow_min,
        green_min=green_min,
    )
    session.add(th)
    session.commit()
    session.refresh(th)
    return th


def get_or_create_exercise(
    session: Session,
    code: str,
    domain_id: int,
    title: str,
    description: str,
    min_age_months: int,
    max_age_months: int,
) -> Exercise:
    stmt = select(Exercise).where(Exercise.code == code)
    ex = session.exec(stmt).first()
    if ex:
        return ex

    ex = Exercise(
        code=code,
        domain_id=domain_id,
        title=title,
        description=description,
        min_age_months=min_age_months,
        max_age_months=max_age_months,
        is_active=True,
    )
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


def main() -> None:
    print("Initializing DB...")
    init_db()

    with Session(engine) as session:
        # ---- Domains ----
        ordforraad = get_or_create_domain(
            session,
            code="ordforraad",
            name="Ordforråd",
        )

        rim = get_or_create_domain(
            session,
            code="rim",
            name="Rim og lydlig opmærksomhed",
        )

        # ---- Thresholds (meget simple testdata) ----
        # 4–5 år (48–59 mdr)
        get_or_create_threshold(
            session,
            domain_id=ordforraad.id,  # type: ignore[arg-type]
            min_age_months=48,
            max_age_months=59,
            yellow_min=5,
            green_min=8,
        )
        get_or_create_threshold(
            session,
            domain_id=rim.id,  # type: ignore[arg-type]
            min_age_months=48,
            max_age_months=59,
            yellow_min=3,
            green_min=6,
        )

        # ---- Exercises ----
        get_or_create_exercise(
            session,
            code="ord_001",
            domain_id=ordforraad.id,  # type: ignore[arg-type]
            title="Find ting i rummet",
            description="Barnet skal pege på genstande, når den voksne siger ordet.",
            min_age_months=48,
            max_age_months=59,
        )

        get_or_create_exercise(
            session,
            code="ord_002",
            domain_id=ordforraad.id,  # type: ignore[arg-type]
            title="Navngiv billeder",
            description="Barnet skal sige, hvad der er på billedet.",
            min_age_months=48,
            max_age_months=59,
        )

        get_or_create_exercise(
            session,
            code="rim_001",
            domain_id=rim.id,  # type: ignore[arg-type]
            title="Find ord der rimer",
            description="Barnet skal vælge det ord, der rimer på et givent ord.",
            min_age_months=48,
            max_age_months=59,
        )

        print("Seed complete ✅")


if __name__ == "__main__":
    main()
