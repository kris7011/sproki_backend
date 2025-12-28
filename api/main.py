# api/main.py
from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import routes_exercises, routes_parents, routes_ppr, routes_reports
from .db import engine, init_db, seed_minimal_data
from .settings import settings


def _get_allow_origins() -> list[str]:
    # In dev allow all to avoid CORS pain
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        return ["*"]

    return settings.cors_origins or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _is_debug_enabled() -> bool:
    # Debug endpoints are only enabled when explicitly allowed
    return os.getenv("ALLOW_DEBUG", "0") == "1"


def _sqlite_db_path() -> Optional[str]:
    # Most reliable way for sqlite:/// + sqlite://// urls
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return None

    return engine.url.database


def _sqlite_connect(db_path: str) -> sqlite3.Connection:
    # Nice-to-have: open read-only so debug endpoints don't lock the DB
    # (works with absolute paths, and avoids "database is locked" in some cases)
    try:
        if os.path.isabs(db_path):
            uri = f"file:{db_path}?mode=ro"
            return sqlite3.connect(uri, uri=True)
    except Exception:
        pass

    # Fallback
    return sqlite3.connect(db_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    if os.getenv("SEED_ON_STARTUP", "0") == "1":
        try:
            result = seed_minimal_data()
            print("SEED_ON_STARTUP:", result)
        except Exception as e:
            # Don't crash startup on Render – log and continue
            print("SEED_ON_STARTUP failed:", repr(e))

    yield

    # Shutdown: nothing needed


app = FastAPI(title="Sproki API", lifespan=lifespan)

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


@app.head("/health")
def health_head():
    # Nice-to-have: some providers probe /health via HEAD
    return Response(status_code=200)


@app.get("/version")
def version():
    # Optional: set GIT_SHA in Render env to see which build is running
    return {"version": os.getenv("GIT_SHA", "local")}


@app.get("/debug/db")
def debug_db() -> Dict[str, Any]:
    if not _is_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    url = str(engine.url)
    db_path = _sqlite_db_path()

    out: Dict[str, Any] = {
        "database_url": url,
        "sqlite_db_path": db_path,
        "seed_on_startup": os.getenv("SEED_ON_STARTUP", "0"),
        "allow_debug": os.getenv("ALLOW_DEBUG", "0"),
        "tables": [],
        "exercise_count": None,
        "childreport_count": None,
    }

    if not db_path:
        return out

    try:
        con = _sqlite_connect(db_path)
        cur = con.cursor()

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        out["tables"] = [r[0] for r in cur.fetchall()]

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

    except Exception as e:
        # Nice-to-have: don't 500 with plain text - show what failed in JSON
        out["error"] = repr(e)
        return out


@app.post("/debug/seed")
def debug_seed() -> Dict[str, Any]:
    # Manual seed so you're not blocked by env vars / redeploys
    if not _is_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    try:
        return seed_minimal_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"seed failed: {repr(e)}")


app.include_router(routes_reports.router)
app.include_router(routes_exercises.router)
app.include_router(routes_parents.router)
app.include_router(routes_ppr.router)
