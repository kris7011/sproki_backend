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

# Common error message constant (for Sonar / duplication)
INSTITUTION_NOT_FOUND = "Institution not found"


# ---------- Pydantic schemas ----------

class InstitutionCreate(BaseModel):
    name: str


class InstitutionPatch(BaseModel):
    name: Optional[str] = None


# ---------- Routes ----------

@router.post("/", response_model=Institution)
def create_institution(body: InstitutionCreate) -> Institution:
    # Create a new institution
    with get_session() as session:
        inst = Institution(name=body.name)
        session.add(inst)
        session.commit()
        session.refresh(inst)
        return inst


@router.get("/", response_model=List[Institution])
def list_institutions() -> List[Institution]:
    # Return all institutions
    with get_session() as session:
        stmt = select(Institution)
        results = session.exec(stmt).all()
        return results


@router.get("/{institution_id}", response_model=Institution)
def get_institution(institution_id: int) -> Institution:
    # Return a single institution by id
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(
                status_code=404,
                detail=INSTITUTION_NOT_FOUND,
            )
        return inst


@router.patch("/{institution_id}", response_model=Institution)
def update_institution(
    institution_id: int,
    body: InstitutionPatch,
) -> Institution:
    # Simple partial update – right now only name
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(
                status_code=404,
                detail=INSTITUTION_NOT_FOUND,
            )

        if body.name is not None:
            inst.name = body.name

        session.add(inst)
        session.commit()
        session.refresh(inst)
        return inst


@router.delete("/{institution_id}")
def delete_institution(institution_id: int) -> dict:
    # Delete an institution
    with get_session() as session:
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(
                status_code=404,
                detail=INSTITUTION_NOT_FOUND,
            )

        session.delete(inst)
        session.commit()
        return {"ok": True}
