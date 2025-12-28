# api/main.py
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import Response
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


@app.get("/")
def root():
    return {"ok": True, "service": "sproki-backend"}


@app.head("/")
def root_head():
    return Response(status_code=200)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    return {"version": "f150943"}


@app.on_event("startup")
def _startup():
    # Always init DB (tables etc.)
    init_db()

    # Optional seed (only when explicitly enabled)
    if os.getenv("SEED_ON_STARTUP", "0") == "1":
        try:
            # local import to avoid import-time side effects
            from app.seed import seed_initial_data
            seed_initial_data()
        except Exception as e:
            # Don't crash startup on Render – log and continue.
            print("SEED_ON_STARTUP failed:", repr(e))


app.include_router(routes_reports.router)
app.include_router(routes_exercises.router)
app.include_router(routes_parents.router)
app.include_router(routes_ppr.router)
