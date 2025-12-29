# api/routes_reports.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import require_role, User
from app.models import Domain as DomainModel
from app.models_report import ChildReport, ChildReportScore
from app.report_analysis import ReportAnalysisResult, compute_report_analysis

from .db import get_session

router = APIRouter(prefix="/reports", tags=["reports"])


# ---------- Pydantic schemas ----------

class ReportScoreInput(BaseModel):
    domain_code: str
    raw_score: int


class ChildReportCreate(BaseModel):
    source: str
    age_months: int
    scores: List[ReportScoreInput]


class DomainAnalysisResponse(BaseModel):
    domain_code: str
    domain_name: str
    raw_score: int
    zone: str
    points_to_green: int | None


class ChildReportAnalysisResponse(BaseModel):
    report_id: int
    child_id: int
    age_months: int
    domains: List[DomainAnalysisResponse]


# ---------- Helper functions ----------

def _get_domain_by_code(session: Session, code: str) -> DomainModel:
    statement = select(DomainModel).where(DomainModel.code == code)
    domain = session.exec(statement).first()
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown domain code: {code}",
        )
    return domain


def _convert_analysis_to_response(analysis: ReportAnalysisResult) -> ChildReportAnalysisResponse:
    return ChildReportAnalysisResponse(
        report_id=analysis.report_id,
        child_id=analysis.child_id,
        age_months=analysis.age_months,
        domains=[
            DomainAnalysisResponse(
                domain_code=d.domain_code,
                domain_name=d.domain_name,
                raw_score=d.raw_score,
                zone=d.zone,
                points_to_green=d.points_to_green,
            )
            for d in analysis.domains
        ],
    )


# ---------- Endpoints ----------

@router.post(
    "/children/{child_id}",
    response_model=ChildReportAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_child_report(
    child_id: int,
    payload: ChildReportCreate,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_session),
):
    report = ChildReport(
        child_id=child_id,
        source=payload.source,
        age_months=payload.age_months,
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    assert report.id is not None, "Report must have id after commit"

    for s in payload.scores:
        domain = _get_domain_by_code(session, s.domain_code)
        assert domain.id is not None, "Domain must have id in DB"

        score = ChildReportScore(
            report_id=report.id,
            domain_id=domain.id,
            raw_score=s.raw_score,

            # nice-to-have: keep legacy fields aligned
            domain=domain.code,
            score=s.raw_score,
        )
        session.add(score)

    session.commit()

    analysis = compute_report_analysis(session=session, report=report)
    return _convert_analysis_to_response(analysis)


@router.get(
    "/children/{child_id}/latest",
    response_model=ChildReportAnalysisResponse,
)
def get_latest_child_report_analysis(
    child_id: int,
    user: User = Depends(require_role(["leader", "staff", "parent", "ppr"])),
    session: Session = Depends(get_session),
):
    statement = (
        select(ChildReport)
        .where(ChildReport.child_id == child_id)
        .order_by(desc(ChildReport.created_at))
    )
    report = session.exec(statement).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report found for this child",
        )

    analysis = compute_report_analysis(session=session, report=report)
    return _convert_analysis_to_response(analysis)
