# api/main.py
from __future__ import annotations

import os
import sqlite3
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import routes_admin, routes_me, routes_children
from . import routes_exercises, routes_parents, routes_ppr, routes_reports
from .db import engine, init_db, seed_minimal_data
from .settings import settings


def _get_allow_origins() -> list[str]:
    if os.getenv("REQUIRE_SUPABASE", "0") == "0":
        return ["*"]

    return settings.cors_origins or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _is_debug_enabled() -> bool:
    return os.getenv("ALLOW_DEBUG", "0") == "1"


def _sqlite_db_path() -> Optional[str]:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return None
    return engine.url.database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    if os.getenv("SEED_ON_STARTUP", "0") == "1":
        try:
            result = seed_minimal_data()
            print("SEED_ON_STARTUP:", result)
        except Exception as e:
            print("SEED_ON_STARTUP failed:", repr(e))

    yield


app = FastAPI(title="Sproki API", lifespan=lifespan)

allow_origins = _get_allow_origins()

# Browser/CORS rule:
# If allow_origins contains "*", we MUST set allow_credentials=False.
allow_credentials = False if "*" in allow_origins else True

# Only use regex when we are NOT using "*"
allow_origin_regex = None
if "*" not in allow_origins:
    # Optional helper for local dev if you whitelist origins
    allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace = traceback.format_exc()
    print("UNHANDLED_EXCEPTION:", request.method, request.url.path)
    print(trace)

    if _is_debug_enabled():
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "error": repr(exc),
                "path": request.url.path,
                "method": request.method,
                "trace": trace,
            },
        )

    return Response(
        status_code=500,
        content="Internal Server Error",
        media_type="text/plain",
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
    return {"version": os.getenv("GIT_SHA", "local")}


@app.get("/debug/db")
def debug_db() -> Dict[str, Any]:
    if not _is_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    url = str(engine.url)
    out: Dict[str, Any] = {
        "database_url": url,
        "sqlite_db_path": _sqlite_db_path(),
        "seed_on_startup": os.getenv("SEED_ON_STARTUP", "0"),
        "allow_debug": os.getenv("ALLOW_DEBUG", "0"),
        "tables": [],
        "exercise_count": None,
        "childreport_count": None,
    }

    db_path = out["sqlite_db_path"]
    if not db_path:
        return out

    con = sqlite3.connect(db_path)
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


@app.post("/debug/seed")
def debug_seed() -> Dict[str, Any]:
    if not _is_debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    return seed_minimal_data()


app.include_router(routes_reports.router)
app.include_router(routes_exercises.router)
app.include_router(routes_parents.router)
app.include_router(routes_ppr.router)
app.include_router(routes_me.router)
app.include_router(routes_admin.router)
app.include_router(routes_children.router)
