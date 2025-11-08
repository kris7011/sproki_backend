# api/routes_invites.py
# pyright: reportMissingImports=none, reportUndefinedVariable=none, reportAttributeAccessIssue=none, reportArgumentType=none

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .auth import get_current_user
from .main import engine
from .models_user import Invite, User

router = APIRouter(prefix="/invites", tags=["invites"])


class InviteAcceptIn(BaseModel):
    token: str  # keep simple; Pydantic will validate


@router.post("/accept")
def accept_invite(payload: InviteAcceptIn, user: User = Depends(get_current_user)):
    with Session(engine) as s:
        inv = s.exec(
            select(Invite).where(Invite.token == payload.token)
        ).one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invite not found")
        if inv.acceptedByUserId:
            raise HTTPException(
                status_code=400, detail="Invite already accepted")

        # basic safety: email must match invite
        if user.email.lower() != inv.email.lower():
            raise HTTPException(
                status_code=403, detail="Invite email mismatch")

        # update user's role + institution
        u = s.exec(select(User).where(User.id == user.id)).one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        u.role = inv.role
        if inv.institutionId:
            u.institutionId = inv.institutionId

        inv.acceptedByUserId = user.id
        inv.acceptedAt = datetime.datetime.now(datetime.timezone.utc)

        s.add(u)
        s.add(inv)
        s.commit()

        return {"ok": True, "role": u.role, "institutionId": u.institutionId}
