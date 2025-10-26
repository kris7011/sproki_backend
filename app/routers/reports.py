from __future__ import annotations

from typing import Dict, Any, Optional, Sequence, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.auth import require_role, User
from app.db import get_session as get_db_session
from app.models_learning import DomainThreshold

router = APIRouter(prefix="/reports", tags=["reports"])


class AnalyzeRequest(BaseModel):
    age_years: int = Field(..., ge=0)
    age_months: int = Field(..., ge=0, lt=12)
    scores: dict[str, int]

    @field_validator("scores")
    @classmethod
    def _non_empty(cls, v: dict[str, int]) -> dict[str, int]:
        if not v:
            raise ValueError("scores cannot be empty")
        return v


class DomainResult(BaseModel):
    domain: str
    score: int
    yellow_min: Optional[int] = None
    green_min: Optional[int] = None
    color: str  # "red" | "yellow" | "green"
    points_to_green: int


class AnalyzeResponse(BaseModel):
    age_years: int
    age_months: int
    results: list[DomainResult]


def _months_total(years: int, months: int) -> int:
    return years * 12 + months


def _pick_threshold_for_age(
    ths: Sequence[DomainThreshold], target_months: int
) -> Optional[DomainThreshold]:
    # pick the threshold with max(age) where age_months_total <= target_months
    best: Optional[DomainThreshold] = None
    best_m = -1
    for t in ths:
        m = t.age_years * 12 + t.age_months
        if m <= target_months and m >= best_m:
            best = t
            best_m = m
    return best


def _color_for(score: int, yellow_min: Optional[int], green_min: Optional[int]) -> str:
    if green_min is not None and score >= green_min:
        return "green"
    if yellow_min is not None and score >= yellow_min:
        return "yellow"
    return "red"


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_report(
    body: AnalyzeRequest,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    target_m = _months_total(body.age_years, body.age_months)

    results: list[DomainResult] = []
    for domain, score in body.scores.items():
        q = select(DomainThreshold).where(DomainThreshold.domain == domain)
        # Cast for at hjælpe typecheckeren
        all_th = cast(Sequence[DomainThreshold], session.exec(q).all())

        if not all_th:
            # Ingen thresholds → farve ud fra "ukendte grænser" (bliver rød/gul/green afh. af _color_for)
            color = _color_for(score, None, None)
            results.append(
                DomainResult(
                    domain=domain,
                    score=score,
                    yellow_min=None,
                    green_min=None,
                    color=color,
                    points_to_green=0,  # ingen kendt green_min → 0
                )
            )
            continue

        picked = _pick_threshold_for_age(all_th, target_m)
        if picked is None:
            # ingen alder <= target → fald tilbage til mindste alder
            picked = min(all_th, key=lambda t: t.age_years * 12 + t.age_months)

        yellow_min = int(
            picked.yellow_min) if picked.yellow_min is not None else None
        green_min = int(
            picked.green_min) if picked.green_min is not None else None

        color = _color_for(score, yellow_min, green_min)
        points_to_green = 0
        if green_min is not None and score < green_min:
            points_to_green = max(0, green_min - score)

        results.append(
            DomainResult(
                domain=domain,
                score=score,
                yellow_min=yellow_min,
                green_min=green_min,
                color=color,
                points_to_green=points_to_green,
            )
        )

    return AnalyzeResponse(
        age_years=body.age_years,
        age_months=body.age_months,
        results=results,
    )
