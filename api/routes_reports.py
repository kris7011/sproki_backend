# api/routes_reports.py
from __future__ import annotations
from typing import Dict, List, Tuple
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from api.db import engine
from api.models_report import Report
from api.auth import require_roles
from api.models_user import Role

router = APIRouter(prefix="/reports", tags=["reports"])

_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "rim": {"yellow": 40.0, "green": 60.0},
    "ordforraad": {"yellow": 50.0, "green": 70.0},
    "udtale": {"yellow": 45.0, "green": 65.0},
}


def _zone_and_points(cat: str, score: float) -> Tuple[str, float]:
    t = _THRESHOLDS.get(cat, {"yellow": 50.0, "green": 70.0})  # <-- fix here
    if score >= t["green"]:
        return "green", 0.0
    if score >= t["yellow"]:
        return "yellow", max(0.0, t["green"] - score)
    return "red", max(0.0, t["green"] - score)


class ReportItemIn(BaseModel):
    category: str
    score: float


class ReportUploadIn(BaseModel):
    age_years: int
    age_months: int
    items: List[ReportItemIn]


@router.post("/{child_id}")
def upload_report(
    child_id: str,
    payload: ReportUploadIn,
    user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR)),
):
    if not payload.items:
        raise HTTPException(
            status_code=400, detail="Report must include items")

    try:
        created_ids: List[int] = []
        with Session(engine) as s:
            for it in payload.items:
                zone, pts = _zone_and_points(it.category, it.score)
                r = Report(
                    child_id=child_id,
                    category=it.category,
                    score=it.score,
                    color_zone=zone,
                    points_to_green=pts,
                    age_years=payload.age_years,
                    age_months=payload.age_months,
                )
                s.add(r)
                s.commit()
                s.refresh(r)
                created_ids.append(int(r.id))
        return {"ok": True, "report_ids": created_ids}
    except Exception as e:
        # TEMP: surface root cause during dev
        raise HTTPException(
            status_code=500, detail=f"upload_report failed: {type(e).__name__}: {e}")


@router.get("/{child_id}/latest")
def latest_summary(
    child_id: str,
    user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR)),
):
    try:
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

        summary = [
            {
                "category": k,
                "score": v.score,
                "zone": v.color_zone,
                "points_to_green": v.points_to_green,
                "age": {"years": v.age_years, "months": v.age_months},
                "created_at": v.created_at,
            }
            for k, v in latest.items()
        ]
        return {"child_id": child_id, "summary": summary}
    except Exception as e:
        # TEMP: surface root cause during dev
        raise HTTPException(
            status_code=500, detail=f"latest_summary failed: {type(e).__name__}: {e}")


@router.get("/{child_id}/history")
def history(
    child_id: str,
    user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR)),
):
    with Session(engine) as s:
        rows = s.exec(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(Report.created_at.desc())
        ).all()
    return {
        "child_id": child_id,
        "items": [
            {
                "id": r.id,
                "category": r.category,
                "score": r.score,
                "zone": r.color_zone,
                "points_to_green": r.points_to_green,
                "age_years": r.age_years,
                "age_months": r.age_months,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }
