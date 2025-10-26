# === FILE: app/routers/auth_totp.py
from __future__ import annotations
from typing import Optional, Dict, Any, Tuple

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select

from app.db import get_session
from app.models_auth import User, UserTOTP
from app.security import verify_jwt, issue_jwt
from app.config import settings

router = APIRouter(prefix="/auth/totp", tags=["auth"])


def _auth_tmp(token: str, session: Session) -> User:
    # Valider midlertidig (step-up) JWT
    try:
        claims = verify_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid tmp token")
    if not claims.get("stepup"):
        raise HTTPException(status_code=401, detail="Token is not step-up")

    try:
        uid = int(claims["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid subject in token")

    user = session.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not active")
    return user


def _require_user_id(user: User) -> int:
    # ORM-modeller har ofte id: Optional[int]; når brugeren findes, skal id være sat.
    if user.id is None:
        # Dette er en server-side inkonsistens – kast 500 så vi får den i Sentry.
        raise HTTPException(status_code=500, detail="User has no persisted id")
    return int(user.id)


@router.post("/enroll/start")
def enroll_start(tmp_token: str = Body(...), session: Session = Depends(get_session)):
    user = _auth_tmp(tmp_token, session)
    uid = _require_user_id(user)

    # Har brugeren allerede TOTP?
    if session.exec(select(UserTOTP).where(UserTOTP.user_id == uid)).first():
        raise HTTPException(status_code=409, detail="TOTP already enrolled")

    # Generér hemmelighed og otpauth-URL til QR-kode
    secret = pyotp.random_base32()  # 160-bit base32, kompatibel med Authenticator-apps
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=settings.RP_NAME,
    )
    return {"secret": secret, "otpauth_url": otpauth_url}


@router.post("/enroll/verify")
def enroll_verify(
    tmp_token: str = Body(...),
    secret: str = Body(...),
    code: str = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    uid = _require_user_id(user)

    totp = pyotp.TOTP(secret)
    # valid_window=1 tillader ±1 30s-skifte (tolerant for små clock skews)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    session.add(UserTOTP(user_id=uid, secret=secret))
    user.totp_enabled = True
    session.add(user)
    session.commit()
    return {"status": "ok"}


@router.post("/verify")
def verify_totp(
    tmp_token: str = Body(...),
    code: str = Body(...),
    session: Session = Depends(get_session),
):
    user = _auth_tmp(tmp_token, session)
    uid = _require_user_id(user)

    row = session.exec(select(UserTOTP).where(UserTOTP.user_id == uid)).first()
    if not row:
        raise HTTPException(status_code=404, detail="No TOTP registered")

    totp = pyotp.TOTP(row.secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Udsted “fuld” session-JWT med amr=["pwd","otp"]
    full = issue_jwt(str(uid), extra={"amr": ["pwd", "otp"]})
    return {"token": full}
