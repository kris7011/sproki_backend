# api/main.py
from __future__ import annotations

import os
import sqlite3

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from .settings import settings
from .db import init_db, engine
from . import routes_reports
from . import routes_exercises
from . import routes_parents
from . import routes_ppr

app = FastAPI(title="Sproki API")


def _get_allow_origins():
    # I dev (REQUIRE_SUPABASE=0) tillader vi alle origins for at undgå CORS-problemer
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        return ["*"]

    return settings.cors_origins or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"ok": True, "service": "sproki-backend"}


@app.head("/")
def root_head():
    # Render health probe often does HEAD /
    return Response(status_code=200)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    # optional: set this via env in CI later
    return {"version": os.getenv("GIT_SHA", "local")}


@app.get("/debug/db")
def debug_db():
    # Helps us verify Render DB + tables without needing logs
    url = str(engine.url)
    out = {
        "database_url": url,
        "seed_on_startup": os.getenv("SEED_ON_STARTUP", "0"),
        "tables": [],
        "exercise_count": None,
        "childreport_count": None,
    }

    if url.startswith("sqlite"):
        # engine.url typically: sqlite:///./sproki.db  OR sqlite:////data/sproki.db
        db_path = url.replace("sqlite:///", "")
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        out["tables"] = [r[0] for r in cur.fetchall()]

        # Best-effort counts (won't crash if tables are missing)
        try:
            cur.execute("SELECT COUNT(*) FROM exercise;")
            out["exercise_count"] = cur.fetchone()[0]
        except Exception:
            pass

        try:
            cur.execute("SELECT COUNT(*) FROM childreport;")
            out["childreport_count"] = cur.fetchone()[0]
        except Exception:
            pass

        con.close()

    return out


@app.on_event("startup")
def _startup():
    # Always init DB (tables etc.)
    try:
        init_db()
        print("startup: init_db OK, database_url =", str(engine.url))
    except Exception as e:
        print("startup: init_db FAILED:", repr(e))

    # Optional seed (only when explicitly enabled)
    if os.getenv("SEED_ON_STARTUP", "0") == "1":
        try:
            from app.seed import seed_initial_data  # local import to avoid side effects
            seed_initial_data()
            print("startup: seed_initial_data OK")
        except Exception as e:
            # Don't crash startup on Render – log and continue.
            print("startup: SEED_ON_STARTUP failed:", repr(e))


app.include_router(routes_reports.router)
app.include_router(routes_exercises.router)
app.include_router(routes_parents.router)
app.include_router(routes_ppr.router)
