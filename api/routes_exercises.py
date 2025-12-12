# api/routes_exercises.py
# pyright: reportMissingImports=false

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy import desc

from app.auth import require_role, User
from .db import get_session
from app.models_exercise import Exercise, ChildExerciseProgress
from app.models_report import Domain, ChildReport
from app.report_analysis import (
    compute_report_analysis,
    ReportAnalysisResult,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])


def get_db_session() -> Session:
    return next(get_session())


# ----------------------------------------------------------------------
# Pydantic schemas
# ----------------------------------------------------------------------


class ExerciseResponse(BaseModel):
    id: int
    code: str
    title: str
    description: str
    domain_code: str
    domain_name: str
    min_age_months: int
    max_age_months: int


class RecommendedExercisesResponse(BaseModel):
    child_id: int
    age_months: int
    domains: List[str]
    exercises: List[ExerciseResponse]


class AttemptIn(BaseModel):
    child_id: int
    correct: bool


# ----------------------------------------------------------------------
# LIST ALL EXERCISES
# ----------------------------------------------------------------------


@router.get("")
def list_exercises(
    domain_code: str | None = Query(default=None),
    user: User = Depends(require_role(["leader", "staff", "ppr"])),
    session: Session = Depends(get_db_session),
):
    stmt = select(Exercise).where(Exercise.is_active == True)  # noqa: E712

    if domain_code:
        domain_stmt = select(Domain).where(Domain.code == domain_code)
        domain = session.exec(domain_stmt).first()
        if not domain or domain.id is None:
            return []
        stmt = stmt.where(Exercise.domain_id == domain.id)

    rows = list(session.exec(stmt))
    return rows


# ----------------------------------------------------------------------
# RECOMMENDED EXERCISES FOR A CHILD
# ----------------------------------------------------------------------


@router.get(
    "/for-child/{child_id}",
    response_model=RecommendedExercisesResponse,
)
def exercises_for_child(
    child_id: int,
    user: User = Depends(require_role(["leader", "staff", "parent", "ppr"])),
    session: Session = Depends(get_db_session),
):
    stmt = (
        select(ChildReport)
        .where(ChildReport.child_id == child_id)
        .order_by(desc(ChildReport.created_at))
    )

    report = session.exec(stmt).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report found for this child",
        )

    analysis: ReportAnalysisResult = compute_report_analysis(
        session=session,
        report=report,
    )

    needed_domains = [
        d.domain_code for d in analysis.domains if d.zone != "green"
    ]

    if not needed_domains:
        return RecommendedExercisesResponse(
            child_id=child_id,
            age_months=analysis.age_months,
            domains=[],
            exercises=[],
        )

    all_domains = list(session.exec(select(Domain)))
    domain_rows = [
        d for d in all_domains if d.code in needed_domains and d.id is not None
    ]
    domain_by_id = {d.id: d for d in domain_rows}
    domain_ids = list(domain_by_id.keys())

    age_months = analysis.age_months

    all_exercises = list(
        session.exec(select(Exercise).where(Exercise.is_active == True))  # noqa: E712
    )

    exercises = [
        ex
        for ex in all_exercises
        if ex.domain_id in domain_ids
        and ex.min_age_months <= age_months
        and ex.max_age_months >= age_months
    ]

    ex_items: List[ExerciseResponse] = []
    for ex in exercises:
        domain = domain_by_id.get(ex.domain_id)
        if domain is None:
            continue

        ex_items.append(
            ExerciseResponse(
                id=ex.id or 0,
                code=ex.code,
                title=ex.title,
                description=ex.description,
                domain_code=domain.code,
                domain_name=domain.name,
                min_age_months=ex.min_age_months,
                max_age_months=ex.max_age_months,
            )
        )

    return RecommendedExercisesResponse(
        child_id=child_id,
        age_months=age_months,
        domains=needed_domains,
        exercises=ex_items,
    )


# ----------------------------------------------------------------------
# POST ATTEMPT
# ----------------------------------------------------------------------


@router.post("/{exercise_id}/attempts")
def post_attempt(
    exercise_id: int,
    payload: AttemptIn,
    user: User = Depends(require_role(["leader", "staff", "parent", "ppr"])),
    session: Session = Depends(get_db_session),
):
    ex = session.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    att = ChildExerciseProgress(
        child_id=payload.child_id,
        exercise_id=exercise_id,
        status="completed" if payload.correct else "in_progress",
    )

    session.add(att)
    session.commit()
    session.refresh(att)

    return {"ok": True, "attempt_id": att.id}


# ----------------------------------------------------------------------
# CHILD PROGRESSION
# ----------------------------------------------------------------------


@router.get("/progression/{child_id}")
def progression(
    child_id: int,
    user: User = Depends(require_role(["leader", "staff", "ppr"])),
    session: Session = Depends(get_db_session),
):
    rep_stmt = (
        select(ChildReport)
        .where(ChildReport.child_id == child_id)
        .order_by(desc(ChildReport.created_at))
    )
    report = session.exec(rep_stmt).first()

    if report is None:
        raise HTTPException(status_code=404, detail="No report found")

    att_stmt = (
        select(ChildExerciseProgress)
        .where(ChildExerciseProgress.child_id == child_id)
        .order_by(desc(ChildExerciseProgress.last_updated_at))
    )
    attempts = list(session.exec(att_stmt))

    stats: dict[str, dict[str, float]] = {}

    for a in attempts:
        ex = session.get(Exercise, a.exercise_id)
        if not ex:
            continue

        domain = session.get(Domain, ex.domain_id)
        if not domain:
            continue

        st = stats.setdefault(domain.code, {"total": 0.0, "correct": 0.0})
        st["total"] += 1
        if a.status == "completed":
            st["correct"] += 1

    out = []
    for domain_code, st in stats.items():
        accuracy = st["correct"] / st["total"] if st["total"] > 0 else None
        out.append(
            {
                "domain": domain_code,
                "attempts_total": int(st["total"]),
                "accuracy": accuracy,
            }
        )

    return {
        "child_id": child_id,
        "age_months": report.age_months,
        "progression": out,
    }
