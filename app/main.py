# app/main.py
from fastapi import FastAPI
from app.db import init_db
from app.routers import children, institutions, exercises, thresholds, admin, progress

app = FastAPI(title="Sproki API")


@app.on_event("startup")
def on_startup():
    init_db()  # <- opretter tabeller hvis de ikke findes


app.include_router(children.router)
app.include_router(institutions.router)
app.include_router(exercises.router)
app.include_router(progress.router)
app.include_router(thresholds.router)
app.include_router(admin.router)
