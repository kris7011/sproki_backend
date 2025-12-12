# api/config.py
from __future__ import annotations

import os


def get_database_url() -> str:
    # Standard til lokal udvikling
    return os.getenv("DATABASE_URL", "sqlite:///./sproki.db")
