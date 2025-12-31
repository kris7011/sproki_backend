# api/routes_me.py
from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from .auth import get_current_user
from .db import engine
from .models_user import User as UserModel, Invite as InviteModel, Role

router = APIRouter(prefix="", tags=["me"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: Role
    institution_id: Optional[int] = None


class AcceptInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: MeResponse
    invite_applied: bool
    invite_role: Optional[Role] = None
    invite_institution_id: Optional[int] = None


def _to_me(u: UserModel) -> MeResponse:
    # Explicit conversion makes Pylance happy and keeps response stable.
    return MeResponse.model_validate(u, from_attributes=True)


@router.get("/me", response_model=MeResponse)
def me(user: UserModel = Depends(get_current_user)) -> MeResponse:
    return _to_me(user)


@router.post("/me/accept-invite", response_model=AcceptInviteResponse)
def accept_invite(user: UserModel = Depends(get_current_user)) -> AcceptInviteResponse:
    email = (user.email or "").strip().lower()

    with Session(engine) as session:
        db_user = session.get(UserModel, user.id)
        if not db_user:
            db_user = UserModel(id=user.id, email=email, role=Role.FORAELDER)
            session.add(db_user)
            session.commit()
            session.refresh(db_user)

        # Use "== None" instead of ".is_(None)" to avoid Pylance datetime confusion.
        inv = session.exec(
            select(InviteModel).where(
                InviteModel.email == email,
                InviteModel.accepted_at == None,  # noqa: E711
            )
        ).first()

        if not inv:
            return AcceptInviteResponse(
                user=_to_me(db_user),
                invite_applied=False,
            )

        db_user.role = inv.role
        db_user.institution_id = inv.institution_id

        inv.accepted_at = datetime.datetime.now(datetime.timezone.utc)
        inv.accepted_by_user_id = db_user.id

        session.add(db_user)
        session.add(inv)
        session.commit()
        session.refresh(db_user)

        return AcceptInviteResponse(
            user=_to_me(db_user),
            invite_applied=True,
            invite_role=inv.role,
            invite_institution_id=inv.institution_id,
        )
