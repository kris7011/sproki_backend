from __future__ import annotations
from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from api.db import engine
from api.auth import require_roles, Role
from api.models_report import Report

router = APIRouter(prefix="/ppr", tags=["ppr"])


@router.get("/ping")
def ping_ppr() -> Dict[str, str]:
    return {"ok": "ppr"}


@router.get("/children/{child_id}/progress")
def get_child_progress(child_id: str, user=Depends(require_roles(Role.PPR, Role.LEDER))):
    with Session(engine) as s:
        rows: List[Report] = s.exec(
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
