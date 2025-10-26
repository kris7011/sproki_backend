# === FILE: app/routers/invites.py
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.auth import require_role, User
from app.db import get_session as get_db_session
from app.security import issue_jwt, verify_jwt
from app.services.mailer import mailer, MailMessage
from app.models_institution import Child, Parent, ChildParentLink

router = APIRouter(prefix="/children", tags=["invites"])

# Frontend/base-url til link i mail (kan være din webapp)
FRONTEND_BASE = os.getenv("SPROKI_FRONTEND_BASE", "https://app.sproki.example")
CHILD_NOT_FOUND = "Child not found"


def _must_id(val: Optional[int], what: str) -> int:
    if val is None:
        raise HTTPException(status_code=500, detail=f"{what} has no ID yet")
    return val


class InviteParentBody(BaseModel):
    email: EmailStr
    minutes_valid: Optional[int] = Field(default=60 * 24)  # 24 timer default


@router.post("/{child_id}/invite-parent")
def invite_parent(
    child_id: int,
    body: InviteParentBody,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    # Issue et kortlivet invite-token
    token = issue_jwt(
        sub=str(body.email),
        extra={"typ": "parent_invite", "child_id": child_id},
        minutes=body.minutes_valid,
    )

    # Link som forældre klikker (frontend kan hente token fra URL-fragmentet)
    accept_url = f"{FRONTEND_BASE}/accept-invite?token={token}"

    # Send e-mail (simpel HTML)
    mailer.send(
        MailMessage(
            to=str(body.email),
            subject=f"Invitation til Sproki – {child.name}",
            html=(
                f"<p>Du er inviteret til at følge '{child.name}' i Sproki.</p>"
                f"<p>Klik for at acceptere: <a href='{accept_url}'>Accepter invitation</a></p>"
                f"<p>Linket udløber om {body.minutes_valid} min.</p>"
            ),
        )
    )

    return {"sent": True, "to": str(body.email)}


# Offentligt endpoint som linket peger på
# (Din frontend kan også kalde dette server-side for at færdiggøre linkningen)
@router.get("/accept-invite")
def accept_invite(
    token: str,
    session: Session = Depends(get_db_session),
):
    # Verificér token + standardclaims
    claims = verify_jwt(token)
    if not claims or claims.get("typ") != "parent_invite":
        raise HTTPException(status_code=400, detail="Invalid invite token")

    email = claims.get("sub")
    child_id_claim = claims.get("child_id")
    if not email or child_id_claim is None:
        raise HTTPException(status_code=400, detail="Token missing data")

    # Slå barnet op ud fra token-claim
    child = session.get(Child, int(child_id_claim))
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)
    child_id = _must_id(child.id, "Child")

    # Upsert Parent
    parent = session.exec(select(Parent).where(Parent.email == email)).first()
    if not parent:
        parent = Parent(name=str(email).split(
            "@")[0], email=email)  # simpelt navn
        session.add(parent)
        session.commit()
        session.refresh(parent)
    parent_id = _must_id(parent.id, "Parent")

    # Link Parent <-> Child (idempotent)
    exists = session.exec(
        select(ChildParentLink).where(
            ChildParentLink.child_id == child_id,
            ChildParentLink.parent_id == parent_id,
        )
    ).first()
    if not exists:
        session.add(ChildParentLink(child_id=child_id, parent_id=parent_id))
        session.commit()

    return {
        "accepted": True,
        "child_id": child_id,
        "parent_email": email,
    }


@router.get("/verify-invite")
def verify_invite(
    token: str,
):
    """
    Simpel validering til UI: er token gyldigt, og hvilket barn+email gælder det?
    Opretter/ændrer intet i DB.
    """
    claims = verify_jwt(token)
    if not claims or claims.get("typ") != "parent_invite":
        raise HTTPException(status_code=400, detail="Invalid invite token")

    email = claims.get("sub")
    child_id_claim = claims.get("child_id")
    if not email or child_id_claim is None:
        raise HTTPException(status_code=400, detail="Token missing data")

    return {
        "valid": True,
        "child_id": int(child_id_claim),
        "parent_email": str(email),
        "expires_at": claims.get("exp"),  # unix time
    }


@router.delete("/{child_id}/parent/{parent_id}")
def unlink_parent(
    child_id: int,
    parent_id: int,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_db_session),
):
    """
    Fjern relationen mellem et barn og en forælder. Idempotent (no-op hvis ikke findes).
    """
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    # Tjek at parent findes (valgfrit, men bedre fejlbesked)
    parent = session.get(Parent, parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    link = session.exec(
        select(ChildParentLink).where(
            ChildParentLink.child_id == child_id,
            ChildParentLink.parent_id == parent_id,
        )
    ).first()

    if not link:
        # Idempotent svar
        return {"unlinked": False, "reason": "link_not_found"}

    session.delete(link)
    session.commit()
    return {"unlinked": True}
