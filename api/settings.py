# api/settings.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


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

    proj = (os.getenv("SUPABASE_PROJECT_URL", "") or "").strip().rstrip("/")
    jwks = (os.getenv("SUPABASE_JWKS_URL", "") or "").strip()
    if not jwks and proj:
        jwks = f"{proj}/auth/v1/keys"

    issr = (os.getenv("SUPABASE_JWT_ISSUER", "") or "").strip()
    if not issr and proj:
        issr = f"{proj}/auth/v1"

    audi = (os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated") or "").strip()

    anon_key = (os.getenv("SUPABASE_ANON_KEY", "") or "").strip()
    service_role = (os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()

    return Settings(
        database_url=database_url,
        sql_echo=sql_echo,
        cors_origins=cors,
        supabase_project_url=proj,
        supabase_jwks_url=jwks,
        supabase_jwt_issuer=issr,
        supabase_jwt_audience=audi,
        supabase_anon_key=anon_key,
        supabase_service_role_key=service_role,
    )


settings = load_settings()
