from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.auth import require_role, User
from app.models_institution import Child

router = APIRouter(prefix="/ppr", tags=["ppr"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.get("/children/{child_id}/progress")
async def get_child_progress(
    child_id: int,
    user: User = Depends(require_role(["ppr", "leader"])),
    session: Session = Depends(get_session),
):
    child = session.get(Child, child_id)
    if not child:
        return {"child_id": child_id, "exists": False}

    # Placeholder data
    return {
        "child_id": child_id,
        "name": child.name,
        "domains": [
            {"domain": "rim", "status": "yellow", "score": 42},
            {"domain": "ordforråd", "status": "red", "score": 30},
        ],
    }
