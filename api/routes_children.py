# api/routes_children.py
from __future__ import annotations

from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from .auth import get_current_user
from .db import get_session
from .models_user import User as UserModel, Role
from .models_access import ChildAccess

from app.models import Child  # keep if this is your single source-of-truth model

from app.services.training import (
    analyze_domain_scores,
    build_training_plan,
    ensure_assignments_for_child,
)

router = APIRouter(prefix="/children", tags=["children"])

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
    domain_code: str
    score: int


class AnalyzeRequest(BaseModel):
    scores: List[DomainScoreInput]


class AnalyzeResponse(BaseModel):
    analysis: Dict[str, Dict]
    plan: Dict[str, Dict]


def _is_staff(user: UserModel) -> bool:
    return user.role in (Role.LEDER, Role.PERSONALE, Role.PPR)


def _get_child_for_user(
    session: Session,
    user: UserModel,
    child_id: int,
) -> Child:
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND_MSG)

    has_access = False

    if _is_staff(user):
        if user.institution_id is None:
            raise HTTPException(
                status_code=403, detail="Institution is not set for user")
        has_access = child.institution_id == user.institution_id
    else:
        stmt = (
            select(ChildAccess)
            .where(ChildAccess.user_id == user.id)
            .where(ChildAccess.child_id == child.id)
        )
        has_access = session.exec(stmt).first() is not None

    if not has_access:
        raise HTTPException(status_code=403, detail="No access to child")

    return child


@router.get("/", response_model=List[ChildRead])
def list_children(
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[Child]:
    if _is_staff(user):
        if user.institution_id is None:
            return []
        stmt = select(Child).where(Child.institution_id == user.institution_id)
        return list(session.exec(stmt).all())

    # FORAELDER -> only children via access table
    stmt = (
        select(Child)
        .join(ChildAccess, ChildAccess.child_id == Child.id)
        .where(ChildAccess.user_id == user.id)
    )
    return list(session.exec(stmt).all())


@router.get("/{child_id}", response_model=ChildRead)
def get_child(
    child_id: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Child:
    child = _get_child_for_user(session, user, child_id)
    return child


@router.post("/", response_model=ChildRead)
def create_child(
    body: ChildCreate,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Child:
    # Only staff can create children (parents get access via invite flow)
    if not _is_staff(user):
        raise HTTPException(
            status_code=403, detail="Only staff can create children")

    if user.institution_id is None:
        raise HTTPException(
            status_code=403, detail="Institution is not set for user")

    # Enforce: staff can only create children in their own institution
    if body.institution_id != user.institution_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot create child in another institution",
        )

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


@router.patch("/{child_id}", response_model=ChildRead)
def update_child(
    child_id: int,
    body: ChildPatch,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Child:
    # Only staff can update child master-data
    if not _is_staff(user):
        raise HTTPException(
            status_code=403, detail="Only staff can update children")

    child = _get_child_for_user(session, user, child_id)

    if body.name is not None:
        child.name = body.name
    if body.age_years is not None:
        child.age_years = body.age_years
    if body.age_months is not None:
        child.age_months = body.age_months
    if body.institution_id is not None:
        # keep it safe: must remain inside staff institution
        if user.institution_id is None or body.institution_id != user.institution_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot move child to another institution",
            )
        child.institution_id = body.institution_id
    if body.ppr_consent is not None:
        child.ppr_consent = body.ppr_consent

    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@router.delete("/{child_id}")
def delete_child(
    child_id: int,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    # Only leader can delete (adjust if you want)
    if user.role != Role.LEDER:
        raise HTTPException(
            status_code=403, detail="Only leader can delete children")

    child = _get_child_for_user(session, user, child_id)

    session.delete(child)
    session.commit()
    return {"ok": True}


@router.post("/{child_id}/analyze-and-plan", response_model=AnalyzeResponse)
def analyze_and_plan(
    child_id: int,
    body: AnalyzeRequest,
    user: UserModel = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AnalyzeResponse:
    # Allowed for staff in institution AND parents with access
    child = _get_child_for_user(session, user, child_id)

    domain_scores: Dict[str, int] = {
        entry.domain_code: entry.score for entry in body.scores
    }

    analysis = analyze_domain_scores(session, child, domain_scores)
    ensure_assignments_for_child(session, child, analysis)
    plan = build_training_plan(session, child)

    session.commit()

    return AnalyzeResponse(
        analysis=analysis,
        plan=plan,
    )
