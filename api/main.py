# api/main.py
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .settings import settings
from .db import init_db
from . import routes_reports
from . import routes_exercises
from . import routes_parents
from . import routes_ppr

app = FastAPI(title="Sproki API")

# I dev (REQUIRE_SUPABASE=0) tillader vi alle origins for at undgå CORS-problemer
if os.getenv("REQUIRE_SUPABASE", "0") == "0":
    allow_origins = ["*"]
else:
    allow_origins = settings.cors_origins or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def _startup():
    init_db()


# Her antager vi, at hver routes_*.py har: router = APIRouter(...)
# Pylance kan ikke altid se attribute 'router' på modulet, så vi ignorerer det for type checkeren.
app.include_router(routes_reports.router)     # type: ignore[attr-defined]
app.include_router(routes_exercises.router)   # type: ignore[attr-defined]
app.include_router(routes_parents.router)     # type: ignore[attr-defined]
app.include_router(routes_ppr.router)         # type: ignore[attr-defined]
