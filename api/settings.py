# Simple settings loader with sane defaults for local dev.
# Reads a .env if present; otherwise uses environment or defaults.

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

    # Supabase/JWT (optional in dev)
    supabase_project_url: str
    supabase_jwks_url: str
    supabase_jwt_issuer: str
    supabase_jwt_audience: str

    # Supabase Admin (service role) + bootstrap leader
    supabase_service_role_key: str
    initial_leader_email: str


def load_settings() -> Settings:
    # optionally load .env (best-effort)
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()  # does nothing if missing
    except Exception:
        pass

    database_url = os.getenv("DATABASE_URL", "sqlite:///./sproki.db")
    sql_echo = os.getenv("SQL_ECHO", "0") == "1"

    cors = _split_csv(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Supabase (only needed when REQUIRE_SUPABASE=1)
    proj = os.getenv("SUPABASE_PROJECT_URL", "")
    jwks = os.getenv("SUPABASE_JWKS_URL",
                     f"{proj}/auth/v1/keys" if proj else "")
    issr = os.getenv("SUPABASE_JWT_ISSUER", f"{proj}/auth/v1" if proj else "")
    audi = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")

    # Supabase Admin + bootstrap leader
    service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    initial_leader_email = os.getenv(
        "INITIAL_LEADER_EMAIL", "").strip().lower()

    return Settings(
        database_url=database_url,
        sql_echo=sql_echo,
        cors_origins=cors,
        supabase_project_url=proj,
        supabase_jwks_url=jwks,
        supabase_jwt_issuer=issr,
        supabase_jwt_audience=audi,
        supabase_service_role_key=service_role,
        initial_leader_email=initial_leader_email,
    )


settings = load_settings()
