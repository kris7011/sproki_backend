# api/auth.py
# pyright: reportGeneralTypeIssues=none, reportAttributeAccessIssue=none, reportCallIssue=none
# Minimal auth layer.
# In dev, set REQUIRE_SUPABASE=0 to bypass Supabase and auto-create a local LEDER user.

from __future__ import annotations

import os
import datetime
from typing import Any, Dict, Optional, List

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlmodel import Session, select

from .settings import settings
from .db import engine
from .models_user import User as UserModel, Role as RoleEnum

bearer_scheme = HTTPBearer(auto_error=True)


class JWKSCache:
    def __init__(self) -> None:
        self.keys: Optional[Dict[str, Any]] = None
        self.expires_at: float = 0.0


_jwks_cache = JWKSCache()


def _now_epoch() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


async def _fetch_jwks() -> Dict[str, Any]:
    if not settings.supabase_jwks_url:
        raise HTTPException(
            status_code=500, detail="SUPABASE_JWKS_URL is not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(settings.supabase_jwks_url)
            r.raise_for_status()

            data: Dict[str, Any] = r.json()
            keys = data.get("keys") if isinstance(data, dict) else None
            if not keys:
                raise HTTPException(
                    status_code=500, detail="Invalid JWKS payload")
            return data

    except httpx.RequestError as e:
        # DNS / connect / timeout
        raise HTTPException(
            status_code=503, detail=f"Auth JWKS unreachable: {repr(e)}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=503, detail=f"Auth JWKS HTTP error: {e.response.status_code}")


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
        status_code=401, detail="No matching JWK for token 'kid'")


def _require_token(creds: Optional[HTTPAuthorizationCredentials]) -> str:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return creds.credentials


def _decode_and_verify(token: str, jwk: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer algorithm from JWKS (avoids "unverified header" warning from Sonar)
    jwk_alg = (jwk.get("alg") or "").upper()
    allowed_algs: List[str] = ["ES256", "RS256"]

    if jwk_alg:
        if jwk_alg not in allowed_algs:
            raise HTTPException(
                status_code=401, detail=f"Unsupported JWK alg: {jwk_alg}")
        algs = [jwk_alg]
    else:
        # Some JWKS don't include "alg". Supabase tokens are typically ES256.
        algs = allowed_algs

    try:
        return jwt.decode(
            token,
            jwk,  # python-jose accepts a JWK dict directly
            algorithms=algs,
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


def _ensure_user(sub: str, email: str) -> UserModel:
    with Session(engine) as session:
        u = session.exec(select(UserModel).where(UserModel.id == sub)).first()
        if u:
            return u

        default_role = getattr(RoleEnum, "FORAELDER", None) or RoleEnum.LEDER
        u = UserModel(id=sub, email=email, role=default_role)
        session.add(u)
        session.commit()
        session.refresh(u)
        return u


def _get_or_create_dev_user() -> UserModel:
    with Session(engine) as session:
        u = session.exec(select(UserModel).where(
            UserModel.id == "dev-user")).first()
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


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserModel:
    # Dev bypass
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        return _get_or_create_dev_user()

    token = _require_token(creds)

    jwks = await get_jwks()
    jwk = _select_jwk_for_token(token, jwks)
    claims = _decode_and_verify(token, jwk)

    sub = claims.get("sub")
    user_meta = claims.get("user_metadata") or {}
    email = (claims.get("email") or user_meta.get("email") or "")
    email = email.lower() if email else email

    if not sub or not email:
        raise HTTPException(
            status_code=401, detail="Token missing required claims")

    return _ensure_user(sub, email)


def require_roles(*allowed_roles: RoleEnum):
    def _dep(user: UserModel = Depends(get_current_user)) -> UserModel:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep
