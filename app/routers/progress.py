# app/routers/progress.py
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.db import get_session
from app.models import Child, ExerciseAssignment, ExerciseAttempt, ExerciseCategory, ExerciseItem, ExerciseProgress

router = APIRouter(prefix="/progress", tags=["progress"])


class AttemptIn(BaseModel):
    child_id: int
    item_id: int
    is_correct: bool


@router.post("/attempt")
def post_attempt(inp: AttemptIn, session: Session = Depends(get_session)):
    # --- Find barn og item ---
    child = session.get(Child, inp.child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    item = session.get(ExerciseItem, inp.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # --- Sikre gyldige IDs før brug ---
    if child.id is None or item.id is None:
        raise HTTPException(status_code=400, detail="Invalid database IDs")

    # --- Log forsøg ---
    att = ExerciseAttempt(
        child_id=int(child.id),
        item_id=int(item.id),
        is_correct=inp.is_correct,
    )
    session.add(att)

    # --- Opdater progress (child_id + category_id) ---
    category_id = item.category_id
    if category_id is None:
        raise HTTPException(
            status_code=400, detail="Exercise item missing category_id")

    prog = session.exec(
        select(ExerciseProgress).where(
            (ExerciseProgress.child_id == child.id)
            & (ExerciseProgress.category_id == category_id)
        )
    ).first()

    if not prog:
        prog = ExerciseProgress(child_id=int(child.id),
                                category_id=int(category_id))
        session.add(prog)

    prog.attempts_total += 1
    if inp.is_correct:
        prog.correct_total += 1
    prog.success_rate = prog.correct_total / max(1, prog.attempts_total)
    prog.updated_at = datetime.now(timezone.utc)

    # --- Markér assignment completed hvis målet er nået ---
    cat = session.get(ExerciseCategory, category_id)
    if cat and prog.success_rate >= cat.target_success_rate:
        assign = session.exec(
            select(ExerciseAssignment).where(
                (ExerciseAssignment.child_id == child.id)
                & (ExerciseAssignment.category_id == cat.id)
            )
        ).first()

        if assign and not assign.is_completed:
            assign.is_completed = True
            session.add(assign)

    # --- Gem alt ---
    session.commit()

    return {
        "ok": True,
        "progress": {
            "attempts_total": prog.attempts_total,
            "correct_total": prog.correct_total,
            "success_rate": prog.success_rate,
            "category_id": prog.category_id,
        },
    }
