# api/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.settings import settings
from api.db import init_db
from api.routes_reports import router as reports_router
from api.routes_exercises import router as exercises_router
from api.routes_parents import router as parents_router
from api.routes_ppr import router as ppr_router

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


app.include_router(reports_router)
app.include_router(exercises_router)
app.include_router(parents_router)
app.include_router(ppr_router)
