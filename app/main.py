# app/main.py
from fastapi import FastAPI
from app.db import init_db

from app.routers.children import router as children_router
from app.routers.institutions import router as institutions_router
from app.routers.exercises import router as exercises_router
from app.routers.thresholds import router as thresholds_router
from app.routers.admin import router as admin_router
from app.routers.progress import router as progress_router
from app.routers.ppr import router as ppr_router
from app.routers.reports import router as reports_router
from app.routers.leader import router as leader_router
from app.routers.invites import router as invites_router

app = FastAPI(title="Sproki API")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(children_router)
app.include_router(institutions_router)
app.include_router(exercises_router)
app.include_router(thresholds_router)
app.include_router(progress_router)
app.include_router(ppr_router)
app.include_router(reports_router)
app.include_router(leader_router)
app.include_router(invites_router)
app.include_router(admin_router)
