from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from .settings import settings


async def invite_user(email: str, invite_token: str) -> Dict[str, Any]:
    if not settings.supabase_project_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase admin config missing")

    url = f"{settings.supabase_project_url}/auth/v1/invite"

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "email": email,
        "data": {
            "invite_token": invite_token,
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()
