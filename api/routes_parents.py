# api/routes_parents.py

from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy import desc

from .db import engine
from .auth import require_roles
from .models_user import Role
from .models_report import Report

router = APIRouter(prefix="/parents", tags=["parents"])


@router.get("/{child_id}/overview")
def parent_overview(
    child_id: str,
    user=Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.FORAELDER)),
):
    with Session(engine) as s:
        rows = s.exec(
            select(Report)
            .where(Report.child_id == child_id)
            .order_by(desc(Report.created_at))
        ).all()

        latest: dict[str, Report] = {}
        for r in rows:
            if r.category not in latest:
                latest[r.category] = r

        cards = [
            {
                "category": k,
                "score": v.score,
                "zone": v.color_zone,
                "points_to_green": v.points_to_green,
            }
            for k, v in latest.items()
        ]

        return {"child_id": child_id, "cards": cards}
