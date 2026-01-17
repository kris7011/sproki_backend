# api/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _clean_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


def _resolve_jwks_url(project_url: str, explicit_jwks_url: str) -> str:
    # Prefer explicitly configured URL (Render env var), but auto-fix common wrong endpoint.
    jwks = _clean_url(explicit_jwks_url)

    # Some setups used /auth/v1/keys historically, but your Supabase returns 404 there.
    # The working endpoint is /auth/v1/.well-known/jwks.json
    if jwks.endswith("/auth/v1/keys") or jwks.endswith("/auth/v1/keys/"):
        base = jwks[: -len("/auth/v1/keys")]
        jwks = f"{base}/auth/v1/.well-known/jwks.json"
        return jwks

    if jwks:
        return jwks

    proj = _clean_url(project_url)
    if proj:
        return f"{proj}/auth/v1/.well-known/jwks.json"

    return ""


def _resolve_issuer(project_url: str, explicit_issuer: str) -> str:
    issr = _clean_url(explicit_issuer)
    if issr:
        return issr

    proj = _clean_url(project_url)
    if proj:
        return f"{proj}/auth/v1"

    return ""


def _debug_print_settings(jwks: str, issuer: str, audience: str) -> None:
    if os.getenv("AUTH_DEBUG", "0") != "1":
        return
    print(f"[AUTH] JWKS URL = {jwks}")
    print(f"[AUTH] ISSUER   = {issuer}")
    print(f"[AUTH] AUDIENCE = {audience}")


@dataclass(frozen=True)
class Settings:
    database_url: str
    sql_echo: bool
    cors_origins: list[str]

    # Supabase/JWT
    supabase_project_url: str
    supabase_jwks_url: str
    supabase_jwt_issuer: str
    supabase_jwt_audience: str

    # Supabase keys
    supabase_anon_key: str
    supabase_service_role_key: str


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

    database_url = os.getenv("DATABASE_URL", "sqlite:///./sproki.db")
    sql_echo = os.getenv("SQL_ECHO", "0") == "1"

    cors = _split_csv(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    proj = _clean_url(os.getenv("SUPABASE_PROJECT_URL", ""))

    jwks = _resolve_jwks_url(
        project_url=proj,
        explicit_jwks_url=os.getenv("SUPABASE_JWKS_URL", ""),
    )

    issuer = _resolve_issuer(
        project_url=proj,
        explicit_issuer=os.getenv("SUPABASE_JWT_ISSUER", ""),
    )

    audience = (os.getenv("SUPABASE_JWT_AUDIENCE",
                "authenticated") or "").strip()

    anon_key = (os.getenv("SUPABASE_ANON_KEY", "") or "").strip()
    service_role = (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()

    _debug_print_settings(jwks=jwks, issuer=issuer, audience=audience)

    return Settings(
        database_url=database_url,
        sql_echo=sql_echo,
        cors_origins=cors,
        supabase_project_url=proj,
        supabase_jwks_url=jwks,
        supabase_jwt_issuer=issuer,
        supabase_jwt_audience=audience,
        supabase_anon_key=anon_key,
        supabase_service_role_key=service_role,
    )


settings = load_settings()
