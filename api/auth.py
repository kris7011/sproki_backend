# api/auth.py
# pyright: reportGeneralTypeIssues=none, reportAttributeAccessIssue=none, reportCallIssue=none
# Minimal auth layer.
# In dev, set REQUIRE_SUPABASE=0 to bypass Supabase and auto-create a local LEDER user.

from __future__ import annotations

import os
import datetime
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlmodel import Session, select

from .settings import settings
from .db import engine
from .models_user import User as UserModel, Role as RoleEnum

# In dev we allow missing Authorization header (auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class JWKSCache:
    def __init__(self) -> None:
        self.keys: Optional[Dict[str, Any]] = None
        self.expires_at: float = 0.0


_jwks_cache = JWKSCache()


async def _fetch_jwks() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(settings.supabase_jwks_url)
        r.raise_for_status()
        data: Dict[str, Any] = r.json()
        keys = data.get("keys") if isinstance(data, dict) else None
        if not keys:
            raise HTTPException(status_code=500, detail="Invalid JWKS payload")
        return data


def _now_epoch() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


async def get_jwks() -> Dict[str, Any]:
    now = _now_epoch()
    if _jwks_cache.keys and _jwks_cache.expires_at > now:
        return _jwks_cache.keys  # type: ignore[return-value]
    data = await _fetch_jwks()
    _jwks_cache.keys = data
    _jwks_cache.expires_at = now + 3600
    return data


def _select_jwk_for_token(token: str, jwks: Dict[str, Any]) -> Dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = jwks.get("keys")
    if not kid:
        if isinstance(keys, list) and keys:
            return keys[0]
        raise HTTPException(status_code=500, detail="JWKS has no keys")
    if isinstance(keys, list):
        for k in keys:
            if isinstance(k, dict) and k.get("kid") == kid:
                return k
    raise HTTPException(
        status_code=401,
        detail="No matching JWK for token 'kid'",
    )


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserModel:
    # Dev bypass
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        with Session(engine) as session:
            u = session.exec(
                select(UserModel).where(UserModel.id == "dev-user")
            ).first()
            if not u:
                u = UserModel(
                    id="dev-user",
                    email="dev@sproki.local",
                    role=RoleEnum.LEDER,
                )
                session.add(u)
                session.commit()
                session.refresh(u)
            return u

    # Real auth path
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = creds.credentials
    jwks = await get_jwks()
    jwk = _select_jwk_for_token(token, jwks)

    try:
        claims = jwt.decode(
            token,
            jwk,  # python-jose accepts a JWK dict directly
            algorithms=["RS256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    sub = claims.get("sub")
    user_meta = claims.get("user_metadata") or {}
    email = (claims.get("email") or user_meta.get("email") or "")
    email = email.lower() if email else email
    if not sub or not email:
        raise HTTPException(
            status_code=401,
            detail="Token missing required claims",
        )

    with Session(engine) as session:
        u = session.exec(
            select(UserModel).where(UserModel.id == sub)
        ).first()
        if not u:
            default_role = getattr(RoleEnum, "FORAELDER",
                                   None) or RoleEnum.LEDER
            u = UserModel(id=sub, email=email, role=default_role)
            session.add(u)
            session.commit()
            session.refresh(u)
        return u


def require_roles(*allowed_roles: RoleEnum):
    def _dep(user: UserModel = Depends(get_current_user)) -> UserModel:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep
