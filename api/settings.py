# api/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _strip_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def _split_csv(value: str | None) -> List[str]:
    v = _clean(value)
    if not v:
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


def _normalize_supabase_project_url(raw: str) -> str:
    # Expect: https://<ref>.supabase.co
    # If user accidentally provides https://.../auth/v1, normalize back to base.
    url = _strip_trailing_slash(_clean(raw))
    if url.endswith("/auth/v1"):
        url = url[: -len("/auth/v1")]
        url = _strip_trailing_slash(url)
    return url


def _default_jwks_url(project_url: str) -> str:
    # Supabase JWKS endpoint (public)
    # https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
    if not project_url:
        return ""
    return f"{project_url}/auth/v1/.well-known/jwks.json"


def _default_issuer(project_url: str) -> str:
    if not project_url:
        return ""
    return f"{project_url}/auth/v1"


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

    # Supabase Admin
    supabase_service_role_key: str


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

    database_url = _clean(os.getenv("DATABASE_URL")) or "sqlite:///./sproki.db"
    sql_echo = _clean(os.getenv("SQL_ECHO")) == "1"

    cors = _split_csv(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Support both names. Prefer SUPABASE_PROJECT_URL if set.
    proj_raw = _clean(os.getenv("SUPABASE_PROJECT_URL")
                      ) or _clean(os.getenv("SUPABASE_URL"))
    proj = _normalize_supabase_project_url(proj_raw)

    jwks = _clean(os.getenv("SUPABASE_JWKS_URL")) or _default_jwks_url(proj)
    # jwks should not end with /, safe anyway
    jwks = _strip_trailing_slash(jwks)

    issr = _clean(os.getenv("SUPABASE_JWT_ISSUER")) or _default_issuer(proj)
    issr = _strip_trailing_slash(issr)

    audi = _clean(os.getenv("SUPABASE_JWT_AUDIENCE")) or "authenticated"
    service_role = _clean(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    return Settings(
        database_url=database_url,
        sql_echo=sql_echo,
        cors_origins=cors,
        supabase_project_url=proj,
        supabase_jwks_url=jwks,
        supabase_jwt_issuer=issr,
        supabase_jwt_audience=audi,
        supabase_service_role_key=service_role,
    )


settings = load_settings()
