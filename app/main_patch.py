from fastapi import FastAPI
from app.db import init_db
from app.routers import institutions, children, thresholds, exercises, ppr, leader
from app import auth_oidc

app = FastAPI(title="Sproki API – Sprint 1+2")

init_db()

app.include_router(institutions.router)
app.include_router(children.router)
app.include_router(thresholds.router)
app.include_router(exercises.router)
app.include_router(ppr.router)
app.include_router(leader.router)
app.include_router(auth_oidc.router)

# Run: uvicorn app.main_patch:app --reload
