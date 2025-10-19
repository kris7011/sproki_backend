# === FILE: app/main_patch.py
from fastapi import FastAPI
from app.db import init_db
from app.routers import institutions, children

app = FastAPI(title="Sproki API – Sprint 1")

# Initialize DB schema (temporary, Alembic for production)
init_db()

# Register routers
app.include_router(institutions.router)
app.include_router(children.router)

# Run: uvicorn app.main_patch:app --reload
