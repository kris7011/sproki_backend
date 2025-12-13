# app/routers/children.py
from __future__ import annotations

from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import select

from app.db import get_session
from app.models import Child
from app.services.training import (
    analyze_domain_scores,
    build_training_plan,
    ensure_assignments_for_child,
)

router = APIRouter(
    prefix="/children",
    tags=["children"],
)

CHILD_NOT_FOUND_MSG = "Child not found"


class ChildCreate(BaseModel):
    name: str
    age_years: int
    age_months: int
    institution_id: int
    ppr_consent: bool = False


class ChildPatch(BaseModel):
    name: Optional[str] = None
    age_years: Optional[int] = None
    age_months: Optional[int] = None
    institution_id: Optional[int] = None
    ppr_consent: Optional[bool] = None


class ChildRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age_years: int
    age_months: int
    institution_id: int
    ppr_consent: bool


class DomainScoreInput(BaseModel):
    domain_code: str  # fx "rim", "ordforraad"
    score: int


class AnalyzeRequest(BaseModel):
    scores: List[DomainScoreInput]


class AnalyzeResponse(BaseModel):
    analysis: Dict[str, Dict]
    plan: Dict[str, Dict]


@router.post("/", response_model=ChildRead)
def create_child(body: ChildCreate) -> Child:
    with get_session() as session:
        child = Child(
            name=body.name,
            age_years=body.age_years,
            age_months=body.age_months,
            institution_id=body.institution_id,
            ppr_consent=body.ppr_consent,
        )
        session.add(child)
        session.commit()
        session.refresh(child)
        return child


@router.get("/", response_model=List[ChildRead])
def list_children() -> List[Child]:
    with get_session() as session:
        stmt = select(Child)
        return session.exec(stmt).all()


@router.get("/{child_id}", response_model=ChildRead)
def get_child(child_id: int) -> Child:
    with get_session() as session:
        child = session.get(Child, child_id)
        if not child:
            raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND_MSG)
        return child


@router.patch("/{child_id}", response_model=ChildRead)
def update_child(child_id: int, body: ChildPatch) -> Child:
    with get_session() as session:
        child = session.get(Child, child_id)
        if not child:
            raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND_MSG)

        if body.name is not None:
            child.name = body.name
        if body.age_years is not None:
            child.age_years = body.age_years
        if body.age_months is not None:
            child.age_months = body.age_months
        if body.institution_id is not None:
            child.institution_id = body.institution_id
        if body.ppr_consent is not None:
            child.ppr_consent = body.ppr_consent

        session.add(child)
        session.commit()
        session.refresh(child)
        return child


@router.delete("/{child_id}")
def delete_child(child_id: int) -> dict:
    with get_session() as session:
        child = session.get(Child, child_id)
        if not child:
            raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND_MSG)

        session.delete(child)
        session.commit()
        return {"ok": True}


@router.post("/{child_id}/analyze-and-plan", response_model=AnalyzeResponse)
def analyze_and_plan(child_id: int, body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Input: domænescorer fra sprogvurderings-rapporten.
    Output:
      - analysis: farve + missing_to_green pr. domain_code
      - plan: hvilke kategorier/øvelser barnet skal træne
    """
    with get_session() as session:
        child = session.get(Child, child_id)
        if not child:
            raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND_MSG)

        domain_scores: Dict[str, int] = {
            entry.domain_code: entry.score for entry in body.scores
        }

        analysis = analyze_domain_scores(session, child, domain_scores)
        ensure_assignments_for_child(session, child, analysis)
        plan = build_training_plan(session, child)

        return AnalyzeResponse(
            analysis=analysis,
            plan=plan,
        )
