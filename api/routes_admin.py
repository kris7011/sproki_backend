# api/routes_admin.py
from __future__ import annotations

import datetime
import uuid
from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select, col
from sqlalchemy import func, desc
from sqlalchemy.sql import ColumnElement

from .auth import require_roles
from .db import engine
from .models_user import User as UserModel, Role, Invite as InviteModel
from .supabase_admin import invite_user

router = APIRouter(prefix="/admin", tags=["admin"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: Role
    institution_id: Optional[int] = None


class RolePatch(BaseModel):
    role: Role


class InviteCreate(BaseModel):
    email: str
    role: Role
    institution_id: int
    redirect_to: Optional[str] = None


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    email: str
    role: Role
    institution_id: int
    created_by_user_id: str
    created_at: datetime.datetime
    accepted_at: Optional[datetime.datetime] = None
    accepted_by_user_id: Optional[str] = None


@router.get("/users", response_model=List[UserRead])
def list_users(
    q: Optional[str] = Query(default=None),
    _: UserModel = Depends(require_roles(Role.LEDER)),
):
    with Session(engine) as session:
        stmt = select(UserModel)

        if q:
            qn = q.strip().lower()

            # SQLModel fields look like "str" to Pylance, but are SQLAlchemy columns at runtime.
            email_col = cast(ColumnElement[Any], col(UserModel.email))
            stmt = stmt.where(func.lower(email_col).like(f"%{qn}%"))

        return list(session.exec(stmt).all())


@router.patch("/users/{user_id}/role", response_model=UserRead)
def set_role(
    user_id: str,
    body: RolePatch,
    _: UserModel = Depends(require_roles(Role.LEDER)),
):
    with Session(engine) as session:
        u = session.get(UserModel, user_id)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        u.role = body.role
        session.add(u)
        session.commit()
        session.refresh(u)
        return u


@router.get("/invites", response_model=List[InviteRead])
def list_invites(
    only_pending: bool = Query(default=False),
    _: UserModel = Depends(require_roles(Role.LEDER)),
):
    with Session(engine) as session:
        created_at_col = cast(ColumnElement[Any], col(InviteModel.created_at))
        stmt = select(InviteModel).order_by(desc(created_at_col))

        if only_pending:
            accepted_at_col = cast(
                ColumnElement[Any], col(InviteModel.accepted_at))
            stmt = stmt.where(accepted_at_col.is_(None))

        return list(session.exec(stmt).all())


@router.post("/invites", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: InviteCreate,
    leader: UserModel = Depends(require_roles(Role.LEDER)),
):
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    token = uuid.uuid4().hex
    accepted_at_col = cast(ColumnElement[Any], col(InviteModel.accepted_at))

    with Session(engine) as session:
        existing = session.exec(
            select(InviteModel).where(
                InviteModel.email == email,
                accepted_at_col.is_(None),
            )
        ).first()
        if existing:
            return existing

        inv = InviteModel(
            token=token,
            email=email,
            role=body.role,
            institution_id=body.institution_id,
            created_by_user_id=leader.id,
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

    try:
        await invite_user(email=email, invite_token=token, redirect_to=body.redirect_to)
    except Exception as ex:
        raise HTTPException(
            status_code=502, detail=f"Supabase invite failed: {ex}")

    return inv
