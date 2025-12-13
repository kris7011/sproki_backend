# app/routers/institutions.py
from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.db import get_session
from app.models import Institution

router = APIRouter(
    prefix="/institutions",
    tags=["institutions"],
)

INSTITUTION_NOT_FOUND = "Institution not found"


class InstitutionCreate(BaseModel):
    name: str


class InstitutionPatch(BaseModel):
    name: Optional[str] = None


@router.post("/", response_model=Institution)
def create_institution(body: InstitutionCreate) -> Institution:
    with get_session() as session:
        inst = Institution(name=body.name)
        session.add(inst)
        session.commit()
        session.refresh(inst)
        return inst


@router.get("/", response_model=List[Institution])
def list_institutions() -> List[Institution]:
    with get_session() as session:
        stmt = select(Institution)
        return session.exec(stmt).all()


@router.get("/{institution_id}", response_model=Institution)
def get_institution(institution_id: int) -> Institution:
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)
        return inst


@router.patch("/{institution_id}", response_model=Institution)
def update_institution(institution_id: int, body: InstitutionPatch) -> Institution:
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)

        if body.name is not None:
            inst.name = body.name

        session.add(inst)
        session.commit()
        session.refresh(inst)
        return inst


@router.delete("/{institution_id}")
def delete_institution(institution_id: int) -> dict:
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)

        session.delete(inst)
        session.commit()
        return {"ok": True}
