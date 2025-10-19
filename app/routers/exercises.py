from sqlmodel import select
from typing import Optional
import json
import random
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.models_learning import Exercise, ExerciseAnswer
from app.auth import require_role, User

router = APIRouter(prefix="/exercises", tags=["exercises"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.post("/answer")
async def post_answer(
    child_id: int,
    exercise_id: int,
    correct: bool,
    user: User = Depends(require_role(["parent", "staff", "leader"])),
    session: Session = Depends(get_session),
):
    ans = ExerciseAnswer(
        child_id=child_id, exercise_id=exercise_id, correct=correct)
    session.add(ans)
    session.commit()
    return {"status": "ok"}


def _infer_weakest_domain(session: Session, child_id: int) -> Optional[str]:
    answers = session.exec(
        select(ExerciseAnswer).where(ExerciseAnswer.child_id == child_id)
    ).all()
    if not answers:
        return None

    scores: dict[str, int] = {}
    for a in answers:
        ex = session.get(Exercise, a.exercise_id)
        if not ex:
            continue
        scores[ex.domain] = scores.get(
            ex.domain, 0) + (2 if not a.correct else -1)

    return max(scores, key=scores.get) if scores else None


def _fetch_exercise_pool(session: Session, domain: Optional[str]) -> list[Exercise]:
    q = select(Exercise).where(Exercise.domain ==
                               domain) if domain else select(Exercise)
    return session.exec(q).all()


def _answer_stats(session: Session, child_id: int, exercise_id: int) -> tuple[int, int]:
    ans = session.exec(
        select(ExerciseAnswer).where(
            ExerciseAnswer.child_id == child_id,
            ExerciseAnswer.exercise_id == exercise_id,
        )
    ).all()
    incorrect = sum(1 for a in ans if not a.correct)
    correct = len(ans) - incorrect
    return incorrect, correct


def _weight_func(session: Session, child_id: int):
    def _inner(ex: Exercise) -> int:
        inc, cor = _answer_stats(session, child_id, ex.id)
        return max(1, inc * 2 - cor)
    return _inner


@router.get("/plan/next")
async def get_next_exercise(
    child_id: int = Query(...),
    domain: Optional[str] = Query(None),
    user: User = Depends(require_role(["parent", "staff", "leader"])),
    session: Session = Depends(get_session),
):
    target_domain = domain or _infer_weakest_domain(session, child_id)
    pool = _fetch_exercise_pool(session, target_domain)

    if not pool:
        raise HTTPException(status_code=404, detail="No exercises available")

    weight = _weight_func(session, child_id)
    chosen = random.choices(pool, weights=[weight(ex) for ex in pool], k=1)[0]

    payload = json.loads(chosen.payload_json)
    return {"exercise_id": chosen.id, "domain": chosen.domain, "payload": payload}
