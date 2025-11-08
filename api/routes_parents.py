from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from .db import engine
from .auth import require_roles, Role
from .models_report import Report

router = APIRouter(prefix="/parents", tags=["parents"])


@router.get("/{child_id}/overview")
def parent_overview(child_id: str, user=Depends(require_roles(Role.LEDER, Role.PERSONALE))):
    with Session(engine) as s:
        rows = s.exec(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(Report.created_at.desc())
        ).all()
        latest = {}
        for r in rows:
            if r.category not in latest:
                latest[r.category] = r
        cards = [
            {"category": k, "score": v.score, "zone": v.color_zone,
                "points_to_green": v.points_to_green}
            for k, v in latest.items()
        ]
        return {"child_id": child_id, "cards": cards}
