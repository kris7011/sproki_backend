# === FILE: app/routers/exercises.py
from __future__ import annotations

from typing import Any, Optional, Sequence, cast
from collections.abc import Mapping
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    Child,
    ExerciseCategory,
    ExerciseItem,
    ExerciseAssignment,
    ExerciseProgress,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])


# ----------------------------- Hjælpe-funktioner ----------------------------- #
def _get_child(session: Session, child_id: int) -> Child:
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


def _age_in_months(child: Child) -> int:
    return child.age_years * 12 + child.age_months


def _fetch_categories(session: Session) -> list[ExerciseCategory]:
    # Result.all() kan være annoteret som Sequence i stubs → konverter til list
    cats_seq: Sequence[ExerciseCategory] = session.exec(
        select(ExerciseCategory)
    ).all()
    return list(cats_seq)


def _within_age(cat: ExerciseCategory, age_months: int) -> bool:
    lo = cat.age_years_min * 12 + cat.age_months_min
    hi = cat.age_years_max * 12 + cat.age_months_max
    return lo <= age_months <= hi


def _filter_by_age(cats: list[ExerciseCategory], age_months: int) -> list[ExerciseCategory]:
    return [c for c in cats if _within_age(c, age_months)]


def _assigned_category_ids(session: Session, child_id: int) -> set[int]:
    assignments: Sequence[ExerciseAssignment] = session.exec(
        select(ExerciseAssignment).where(
            ExerciseAssignment.child_id == child_id)
    ).all()
    return {a.category_id for a in assignments if a.category_id is not None}


def _filter_by_assigned(cats: list[ExerciseCategory], assigned_ids: set[int]) -> list[ExerciseCategory]:
    return [c for c in cats if (c.id is not None and c.id in assigned_ids)]


def _progress_map(session: Session, child_id: int) -> dict[tuple[int, int], ExerciseProgress]:
    rows_seq: Sequence[ExerciseProgress] = session.exec(
        select(ExerciseProgress).where(ExerciseProgress.child_id == child_id)
    ).all()
    rows: list[ExerciseProgress] = list(rows_seq)
    # Kun map entries med gyldig category_id
    out: dict[tuple[int, int], ExerciseProgress] = {}
    for p in rows:
        if p.category_id is None:
            continue
        # child_id bør være int (men cast hvis stubs gør den Optional)
        key: tuple[int, int] = (cast(int, p.child_id),
                                cast(int, p.category_id))
        out[key] = p
    return out


def _sort_by_weakness(
    cats: list[ExerciseCategory],
    child_id: int,
    progress_map: Mapping[tuple[int, int], ExerciseProgress],
) -> None:
    def weakness_key(c: ExerciseCategory) -> float:
        if c.id is None:
            # kategorier uden id skubbes til sidst
            return float("inf")
        cid = cast(int, c.id)
        prog = progress_map.get((child_id, cid))
        return prog.success_rate if prog else 0.0

    cats.sort(key=weakness_key)


def _items_for_category(session: Session, category_id: int, limit: int = 5) -> list[ExerciseItem]:
    items_seq: Sequence[ExerciseItem] = session.exec(
        select(ExerciseItem).where(
            ExerciseItem.category_id == category_id).limit(limit)
    ).all()
    return list(items_seq)


def _serialize_category(
    c: ExerciseCategory,
    child_id: int,
    progress_map: Mapping[tuple[int, int], ExerciseProgress],
    items: list[ExerciseItem],
) -> dict[str, Any]:
    prog: Optional[ExerciseProgress]
    if c.id is not None:
        prog = progress_map.get((child_id, cast(int, c.id)))
    else:
        prog = None
    return {
        "category_id": c.id,
        "category_code": c.code,
        "title": c.title,
        "description": c.description,
        "progress": {
            "attempts_total": prog.attempts_total if prog else 0,
            "correct_total": prog.correct_total if prog else 0,
            "success_rate": prog.success_rate if prog else 0.0,
        },
        "items": [{"id": it.id, "prompt": it.prompt, "media_url": it.media_url} for it in items],
    }


# ----------------------------------- Route ----------------------------------- #
@router.get("/{child_id}/categories")
def list_categories_for_child(
    child_id: int,
    only_assigned: bool = Query(False),
    prioritize_weak: bool = Query(True),
    session: Session = Depends(get_session),
):
    # 1) Barn + alder
    child = _get_child(session, child_id)
    age_m = _age_in_months(child)

    # 2) Kategorier (aldersfilter)
    cats = _filter_by_age(_fetch_categories(session), age_m)

    # 3) Kun tildelte (valgfrit)
    if only_assigned:
        cats = _filter_by_assigned(
            cats, _assigned_category_ids(session, child_id))

    # 4) Progress og sortering (valgfrit)
    pmap = _progress_map(session, child_id)
    if prioritize_weak:
        _sort_by_weakness(cats, child_id, pmap)

    # 5) Svar med få items pr. kategori
    result: list[dict[str, Any]] = []
    for c in cats:
        if c.id is None:
            continue
        items = _items_for_category(session, cast(int, c.id), limit=5)
        result.append(_serialize_category(c, child_id, pmap, items))

    return result
