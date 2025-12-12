# app/services.py
from __future__ import annotations

from datetime import datetime, timezone  # <- ændret linje
from typing import Dict, List

from sqlmodel import Session, select

from app.models import (
    Child,
    Domain,
    DomainThreshold,
    ExerciseCategory,
    ExerciseItem,
    ExerciseAssignment,
    ExerciseProgress,
    ExerciseAttempt,  # <- sørg for denne er her
)


def _age_in_months(child: Child) -> int:
    return max(child.age_years * 12 + child.age_months, 0)


def _utcnow() -> datetime:
    # Central helper for timezone-aware "now"
    return datetime.now(timezone.utc)


def _find_threshold_for_domain_and_age(
    session: Session,
    domain_code: str,
    age_months: int,
) -> DomainThreshold | None:
    """
    Finder første DomainThreshold for det givne domain_code,
    hvor barnets alder (i måneder) ligger inden for min/max.
    """
    domain = session.exec(
        select(Domain).where(Domain.code == domain_code)
    ).first()
    if not domain or domain.id is None:
        return None

    thresholds = session.exec(
        select(DomainThreshold).where(
            DomainThreshold.domain_id == int(domain.id))
    ).all()

    for th in thresholds:
        min_m = th.age_years_min * 12 + th.age_months_min
        max_m = th.age_years_max * 12 + th.age_months_max
        if min_m <= age_months <= max_m:
            return th

    return None


def analyze_domain_scores(
    session: Session,
    child: Child,
    domain_scores: Dict[str, int],
) -> Dict[str, Dict]:
    """
    domain_scores = {"rim": 42, "ordforraad": 38, ...}

    Returnerer fx:
    {
      "rim": {
        "score": 42,
        "color": "yellow",
        "missing_to_green": 5,
      },
      ...
    }
    """
    result: Dict[str, Dict] = {}
    age_m = _age_in_months(child)

    for domain_code, score in domain_scores.items():
        th = _find_threshold_for_domain_and_age(session, domain_code, age_m)

        if not th:
            color = "yellow"
            missing = 0
        else:
            green_min = th.score_min_green
            yellow_min = th.score_min_yellow

            if score >= green_min:
                color = "green"
                missing = 0
            elif score >= yellow_min:
                color = "yellow"
                missing = max(green_min - score, 0)
            else:
                color = "red"
                missing = max(green_min - score, 0)

        result[domain_code] = {
            "score": score,
            "color": color,
            "missing_to_green": missing,
        }

    return result


def _is_relevant_domain(analysis_entry: Dict) -> bool:
    # Skip domains that are already green and do not need work
    return not (
        analysis_entry.get("color") == "green"
        and analysis_entry.get("missing_to_green", 0) <= 0
    )


def _get_domain_by_code(session: Session, domain_code: str) -> Domain | None:
    return session.exec(
        select(Domain).where(Domain.code == domain_code)
    ).first()


def _iter_age_relevant_categories(
    session: Session,
    domain_id: int,
    age_months: int,
):
    categories = session.exec(
        select(ExerciseCategory).where(ExerciseCategory.domain_id == domain_id)
    ).all()

    for cat in categories:
        lo = cat.age_years_min * 12 + cat.age_months_min
        hi = cat.age_years_max * 12 + cat.age_months_max
        if lo <= age_months <= hi:
            yield cat


def _get_or_create_assignment(
    session: Session,
    child_id: int,
    category_id: int,
) -> ExerciseAssignment:
    existing = session.exec(
        select(ExerciseAssignment).where(
            (ExerciseAssignment.child_id == child_id)
            & (ExerciseAssignment.category_id == category_id)
        )
    ).first()
    if existing:
        return existing

    assign = ExerciseAssignment(
        child_id=child_id,
        category_id=category_id,
        is_completed=False,
    )
    session.add(assign)
    return assign


def ensure_assignments_for_child(
    session: Session,
    child: Child,
    analysis: Dict[str, Dict],
) -> List[ExerciseAssignment]:
    """
    For alle domæner der ikke er grønne:
    - Find Domain via code
    - Find aldersrelevante ExerciseCategory for det domæne
    - Opret ExerciseAssignment for barnet hvis det ikke allerede findes
    """
    if child.id is None:
        return []

    age_months = _age_in_months(child)
    assignments: List[ExerciseAssignment] = []

    for domain_code, data in analysis.items():
        if not _is_relevant_domain(data):
            continue

        domain = _get_domain_by_code(session, domain_code)
        if not domain or domain.id is None:
            continue

        for cat in _iter_age_relevant_categories(session, int(domain.id), age_months):
            if cat.id is None:
                continue

            assignment = _get_or_create_assignment(
                session,
                child_id=int(child.id),
                category_id=int(cat.id),
            )
            assignments.append(assignment)

    session.commit()
    for a in assignments:
        session.refresh(a)

    return assignments


# ---------------------------------------------------------------------------


def _is_category_age_relevant(category: ExerciseCategory, age_months: int) -> bool:
    lo = category.age_years_min * 12 + category.age_months_min
    hi = category.age_years_max * 12 + category.age_months_max
    return lo <= age_months <= hi


def _get_domain_for_category(
    session: Session,
    category: ExerciseCategory,
) -> Domain | None:
    return session.get(Domain, category.domain_id)


def _get_items_for_category(
    session: Session,
    category_id: int,
) -> List[ExerciseItem]:
    return session.exec(
        select(ExerciseItem).where(ExerciseItem.category_id == category_id)
    ).all()


def _get_progress_for_child_and_category(
    session: Session,
    child_id: int,
    category_id: int,
) -> ExerciseProgress | None:
    return session.exec(
        select(ExerciseProgress).where(
            (ExerciseProgress.child_id == child_id)
            & (ExerciseProgress.category_id == category_id)
        )
    ).first()


def _append_category_to_plan(
    plan: Dict[str, Dict],
    domain: Domain,
    category: ExerciseCategory,
    assign: ExerciseAssignment,
    items: List[ExerciseItem],
    progress: ExerciseProgress | None,
) -> None:
    domain_entry = plan.setdefault(
        domain.code,
        {
            "domain_code": domain.code,
            "domain_title": domain.title,
            "categories": [],
        },
    )

    domain_entry["categories"].append(
        {
            "category_id": category.id,
            "title": category.title,
            "description": category.description,
            "is_completed": assign.is_completed,
            "items": items,
            "progress": {
                "attempts_total": progress.attempts_total if progress else 0,
                "correct_total": progress.correct_total if progress else 0,
                "success_rate": progress.success_rate if progress else 0.0,
                "updated_at": progress.updated_at if progress else None,
            },
        }
    )


def build_training_plan(
    session: Session,
    child: Child,
) -> Dict[str, Dict]:
    """
    Bygger et trænings-overblik ud fra barnets ExerciseAssignment.
    """
    if child.id is None:
        return {}

    age_months = _age_in_months(child)

    assignments = session.exec(
        select(ExerciseAssignment).where(
            ExerciseAssignment.child_id == int(child.id)
        )
    ).all()

    plan: Dict[str, Dict] = {}

    for assign in assignments:
        category = session.get(ExerciseCategory, assign.category_id)
        if not category:
            continue

        if not _is_category_age_relevant(category, age_months):
            continue

        domain = _get_domain_for_category(session, category)
        if not domain:
            continue

        # Pylance: category.id er int | None → defensiv guard
        if category.id is None:
            continue

        items = _get_items_for_category(session, category_id=int(category.id))
        progress = _get_progress_for_child_and_category(
            session,
            child_id=int(child.id),
            category_id=int(category.id),
        )

        _append_category_to_plan(
            plan=plan,
            domain=domain,
            category=category,
            assign=assign,
            items=items,
            progress=progress,
        )

    return plan


# ---------------------------------------------------------------------------
# Record attempts + opdater progression
# ---------------------------------------------------------------------------


def record_attempt(
    session: Session,
    child: Child,
    item_id: int,
    is_correct: bool,
) -> ExerciseAttempt:
    if child.id is None:
        raise ValueError(
            "Child must be stored in DB before recording attempts"
        )

    item = session.get(ExerciseItem, item_id)
    if not item or item.id is None:
        raise ValueError("Exercise item not found")

    attempt = ExerciseAttempt(
        child_id=int(child.id),
        item_id=int(item.id),
        is_correct=is_correct,
        created_at=_utcnow(),  # <- før: datetime.utcnow()
    )
    session.add(attempt)

    category_id = item.category_id
    progress = session.exec(
        select(ExerciseProgress).where(
            (ExerciseProgress.child_id == int(child.id))
            & (ExerciseProgress.category_id == category_id)
        )
    ).first()

    if not progress:
        progress = ExerciseProgress(
            child_id=int(child.id),
            category_id=category_id,
            attempts_total=0,
            correct_total=0,
            success_rate=0.0,
            updated_at=_utcnow(),  # <- før: datetime.utcnow()
        )
        session.add(progress)

    progress.attempts_total += 1
    if is_correct:
        progress.correct_total += 1
    if progress.attempts_total > 0:
        progress.success_rate = progress.correct_total / progress.attempts_total
    progress.updated_at = _utcnow()  # <- før: datetime.utcnow()

    session.commit()
    session.refresh(attempt)
    session.refresh(progress)

    return attempt
