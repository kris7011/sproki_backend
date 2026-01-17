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


def _jwks_headers() -> Dict[str, str]:
    # Supabase JWKS endpoint can require an apikey header
    key = settings.supabase_anon_key or settings.supabase_service_role_key
    if not key:
        return {}
    return {"apikey": key}


async def _fetch_jwks() -> Dict[str, Any]:
    url = settings.supabase_jwks_url
    if not url:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_JWKS_URL is not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=_jwks_headers())
            r.raise_for_status()

            data: Dict[str, Any] = r.json()
            keys = data.get("keys") if isinstance(data, dict) else None
            if not keys:
                raise HTTPException(
                    status_code=500, detail="Invalid JWKS payload")
            return data

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Auth JWKS unreachable: {repr(e)} | url={url}",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Auth JWKS HTTP error: {e.response.status_code} | url={url}",
        )


async def get_jwks() -> Dict[str, Any]:
    now = _now_epoch()
    if _jwks_cache.keys and _jwks_cache.expires_at > now:
        return _jwks_cache.keys  # type: ignore[return-value]

    data = await _fetch_jwks()
    _jwks_cache.keys = data
    _jwks_cache.expires_at = now + 3600
    return data


def _jwks_key_list(jwks: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys = jwks.get("keys")
    if isinstance(keys, list):
        out: List[Dict[str, Any]] = []
        for k in keys:
            if isinstance(k, dict):
                out.append(k)
        return out
    return []


def _ensure_dev_user() -> UserModel:
    with Session(engine) as session:
        u = session.exec(select(UserModel).where(
            UserModel.id == "dev-user")).first()
        if u:
            return u

        u = UserModel(
            id="dev-user",
            email="dev@sproki.local",
            role=RoleEnum.LEDER,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        return u


def _upsert_user(sub: str, email: str) -> UserModel:
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


def _decode_claims_with_jwks(token: str, jwks: Dict[str, Any]) -> Dict[str, Any]:
    # We avoid reading unverified token headers (Sonar S5659).
    # Instead we try verifying the signature with each JWK until one succeeds.
    keys = _jwks_key_list(jwks)
    if not keys:
        raise HTTPException(status_code=500, detail="JWKS has no keys")

    allowed_algs = ["ES256", "RS256"]
    last_error: str | None = None

    for jwk in keys:
        try:
            claims = jwt.decode(
                token,
                jwk,
                algorithms=allowed_algs,
                audience=settings.supabase_jwt_audience,
                issuer=settings.supabase_jwt_issuer,
                options={"verify_at_hash": False},
            )
            if isinstance(claims, dict):
                return claims
            last_error = "Decoded claims were not a dict"
        except JWTError as e:
            last_error = str(e)
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid token: {last_error or 'Signature verification failed'}",
    )


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserModel:
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        return _ensure_dev_user()

    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = creds.credentials
    jwks = await get_jwks()
    claims = _decode_claims_with_jwks(token, jwks)

    sub = claims.get("sub")
    user_meta = claims.get("user_metadata") or {}
    email = (claims.get("email") or user_meta.get("email") or "")
    email = email.lower() if email else email

    if not sub or not email:
        raise HTTPException(
            status_code=401, detail="Token missing required claims")

    return _upsert_user(sub=sub, email=email)


def require_roles(*allowed_roles: RoleEnum):
    def _dep(user: UserModel = Depends(get_current_user)) -> UserModel:
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep
