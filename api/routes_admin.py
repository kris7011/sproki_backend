# api/routes_admin.py
from __future__ import annotations

from typing import Any, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select
from sqlalchemy import func
from sqlalchemy.sql import ColumnElement

from .auth import require_roles
from .db import engine
from .models_user import User as UserModel, Role

router = APIRouter(prefix="/admin", tags=["admin"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: Role


class RolePatch(BaseModel):
    role: Role


@router.get("/users", response_model=List[UserRead])
def list_users(
    q: Optional[str] = Query(default=None),
    _: UserModel = Depends(require_roles(Role.LEDER)),
):
    with Session(engine) as session:
        stmt = select(UserModel)

        if q:
            qn = q.strip().lower()

            # SQLModel annotates columns as str, but at runtime it's a SQLAlchemy column.
            # Cast to ColumnElement[Any] to keep Pylance happy.
            email_col = cast(ColumnElement[Any], UserModel.email)
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
