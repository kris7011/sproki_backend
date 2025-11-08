from typing import List, Dict
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from .db import engine
from .auth import require_roles, Role
from .models_exercise import Exercise, ExerciseAttempt
from .models_report import Report

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("")
def list_exercises(category: str | None = Query(default=None), user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR))):
    with Session(engine) as s:
        stmt = select(Exercise).where(Exercise.is_active == True)
        if category:
            stmt = stmt.where(Exercise.category == category)
        rows = s.exec(stmt).all()
    return rows


@router.get("/for-child/{child_id}")
def exercises_for_child(child_id: str, user=Depends(require_roles(Role.LEDER, Role.PERSONALE))):
    with Session(engine) as s:
        rows = s.exec(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(Report.created_at.desc())
        ).all()
        latest: Dict[str, Report] = {}
        for r in rows:
            if r.category not in latest:
                latest[r.category] = r
        need_cats = [c for c, r in latest.items() if r.color_zone != "green"]
        if not need_cats:
            return {"child_id": child_id, "exercises": []}

        any_rep = next(iter(latest.values()))
        stmt = select(Exercise).where(
            Exercise.is_active == True,
            Exercise.category.in_(need_cats),
            Exercise.age_min <= any_rep.age_years,
            Exercise.age_max >= any_rep.age_years,
        )
        rows = s.exec(stmt).all()
        return {"child_id": child_id, "categories": need_cats, "exercises": rows}


class AttemptIn(BaseModel):
    child_id: str
    correct: bool


@router.post("/{exercise_id}/attempts")
def post_attempt(exercise_id: int, payload: AttemptIn, user=Depends(require_roles(Role.LEDER, Role.PERSONALE))):
    with Session(engine) as s:
        ex = s.get(Exercise, exercise_id)
        if not ex:
            raise HTTPException(status_code=404, detail="Exercise not found")
        att = ExerciseAttempt(child_id=payload.child_id,
                              exercise_id=exercise_id, correct=payload.correct)
        s.add(att)
        s.commit()
        s.refresh(att)
        return {"ok": True, "attempt_id": att.id}


@router.get("/progression/{child_id}")
def progression(child_id: str, user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR))):
    with Session(engine) as s:
        reps = s.exec(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(Report.created_at.desc())
        ).all()
        latest: Dict[str, Report] = {}
        for r in reps:
            if r.category not in latest:
                latest[r.category] = r

        attempts = s.exec(
            select(ExerciseAttempt)
            .where(ExerciseAttempt.child_id == child_id)
            .order_by(ExerciseAttempt.created_at.desc())
        ).all()

        cat_stats: Dict[str, Dict[str, float]] = {}
        for a in attempts[:200]:
            ex = s.get(Exercise, a.exercise_id)
            if not ex:
                continue
            st = cat_stats.setdefault(
                ex.category, {"total": 0.0, "correct": 0.0})
            st["total"] += 1
            st["correct"] += 1 if a.correct else 0

        out = []
        for cat, rep in latest.items():
            s_total = cat_stats.get(cat, {}).get("total", 0.0)
            s_correct = cat_stats.get(cat, {}).get("correct", 0.0)
            acc = (s_correct / s_total) if s_total > 0 else None
            out.append({
                "category": cat,
                "zone": rep.color_zone,
                "points_to_green": rep.points_to_green,
                "attempts_total": int(s_total),
                "accuracy": acc,
                "last_report_at": rep.created_at,
            })
        return {"child_id": child_id, "categories": out}
