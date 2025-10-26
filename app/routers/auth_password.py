# app/routers/auth_password.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select
from app.db import get_session
from app.models_auth import User
from app.security import hash_password, verify_password, issue_jwt

router = APIRouter(prefix="/auth/pw", tags=["auth"])


@router.post("/register")
def register(email: str = Body(...), password: str = Body(...), session: Session = Depends(get_session)):
    email_norm = email.strip().lower()
    if session.exec(select(User).where(User.email == email_norm)).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    if len(password) < 12:
        raise HTTPException(
            status_code=400, detail="Password too short (min 12)")
    user = User(email=email_norm, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"status": "ok", "user_id": user.id}


@router.post("/login")
def login(email: str = Body(...), password: str = Body(...), session: Session = Depends(get_session)):
    email_norm = email.strip().lower()
    user = session.exec(select(User).where(User.email == email_norm)).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If user has any 2FA, issue temporary token requiring step-up
    if user.totp_enabled or user.webauthn_enabled:
        tmp = issue_jwt(str(user.id), extra={
                        "amr": ["pwd"], "stepup": True}, minutes=10)
        return {"requires_2fa": True, "tmp_token": tmp, "totp": user.totp_enabled, "webauthn": user.webauthn_enabled}

    # No 2FA → full session (interim; i prod bør 2FA være obligatorisk)
    full = issue_jwt(str(user.id), extra={"amr": ["pwd"]})
    return {"requires_2fa": False, "token": full}
