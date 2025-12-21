from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import (
    Institution,
    Staff,
    Parent,
    Child,
    Domain,
    DomainThreshold,
    ExerciseCategory,
    ExerciseItem
)

from app.models_exercise import Exercise


def seed_initial_data() -> None:
    init_db()

    with Session(engine) as session:
        # Kør kun én gang
        if session.exec(select(Institution)).first():
            print("Seed data already exists, skipping.")
            return

        # Institution
        inst = Institution(name="Sproki Børnehus")
        session.add(inst)
        session.commit()
        session.refresh(inst)
        assert inst.id is not None  # PK skal være sat nu

        # Staff
        staff1 = Staff(
            institution_id=inst.id,
            name="Pædagog Pernille",
            email="pernille@example.com",
            role="leader",
        )
        staff2 = Staff(
            institution_id=inst.id,
            name="Pædagog Peter",
            email="peter@example.com",
            role="staff",
        )
        session.add(staff1)
        session.add(staff2)

        # Forældre + barn
        parent = Parent(name="Mor Maria", email="maria@example.com")
        session.add(parent)
        session.commit()
        session.refresh(parent)

        child = Child(
            name="Alma",
            age_years=4,
            age_months=3,
            institution_id=inst.id,
            ppr_consent=True,
        )
        session.add(child)
        session.commit()
        session.refresh(child)

        # Domæne + thresholds
        domain_rim = Domain(
            code="rim",
            name="Rim",
            title="Rim og lydleg",
        )

        session.add(domain_rim)
        session.commit()
        session.refresh(domain_rim)
        assert domain_rim.id is not None

        th_rim = DomainThreshold(
            domain_id=domain_rim.id,
            age_years_min=4,
            age_months_min=0,
            age_years_max=5,
            age_months_max=11,
            score_min_green=40,
            score_min_yellow=30,
        )
        session.add(th_rim)

        # Kategori + items
        cat_rim = ExerciseCategory(
            domain_id=domain_rim.id,
            code="rim_1",
            title="Simple rim",
            description="Enkle rim-øvelser med billeder",
            age_years_min=4,
            age_months_min=0,
            age_years_max=5,
            age_months_max=11,
            target_success_rate=0.8,
        )
        session.add(cat_rim)
        session.commit()
        session.refresh(cat_rim)
        assert cat_rim.id is not None

        item1 = ExerciseItem(
            category_id=cat_rim.id,
            prompt="Hvad rimer på 'kat'?",
            media_url=None,
            difficulty=1,
        )
        item2 = ExerciseItem(
            category_id=cat_rim.id,
            prompt="Hvad rimer på 'hus'?",
            media_url=None,
            difficulty=1,
        )
        session.add(item1)
        session.add(item2)

        session.commit()
        print("Seed completed.")

        # Exercise (den tabel /exercises læser fra)
        ex1 = Exercise(
            domain=domain_rim.code,  # "rim"
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


if __name__ == "__main__":
    seed_initial_data()
