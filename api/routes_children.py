# api/routes_children.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .auth import get_current_user
from .db import get_session
from .models_user import User as UserModel, Role
from .models_access import ChildAccess
from app.models import Child  # adjust import path if needed

router = APIRouter(prefix="", tags=["children"])


@router.get("/children", response_model=List[Child])
def list_children(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # Staff/leader/ppr -> children in same institution
    if user.role in (Role.LEDER, Role.PERSONALE, Role.PPR):
        if user.institution_id is None:
            return []
        stmt = select(Child).where(Child.institution_id == user.institution_id)
        return list(session.exec(stmt).all())

    # FORAELDER -> only children via access table
    stmt = (
        select(Child)
        .join(ChildAccess, ChildAccess.child_id == Child.id)
        .where(ChildAccess.user_id == user.id)
    )
    return list(session.exec(stmt).all())
