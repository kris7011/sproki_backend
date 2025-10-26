# === FILE: app/security.py
import time
from typing import Any, Dict, Optional
from argon2 import PasswordHasher
from jose import jwt
from app.config import settings

_ph = PasswordHasher()  # sensible defaults; tune if needed


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, h: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except Exception:
        return False


def issue_jwt(sub: str, extra: Optional[Dict[str, Any]] = None, minutes: Optional[int] = None) -> str:
    now = int(time.time())
    exp_min = minutes if minutes is not None else settings.JWT_EXPIRE_MIN
    payload: Dict[str, Any] = {
        "iss": settings.JWT_ISS,
        "aud": settings.JWT_AUD,
        "iat": now,
        "nbf": now,
        "exp": now + exp_min * 60,
        "sub": sub,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_jwt(token: str) -> Dict[str, Any]:
    # Always verify signature + standard claims
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.JWT_AUD,
        issuer=settings.JWT_ISS,
        options={"require_sub": True, "verify_at_hash": False},
    )
