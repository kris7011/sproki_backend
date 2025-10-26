# === FILE: app/services/reporting.py
from __future__ import annotations

from typing import Tuple
from sqlmodel import Session, select
from app.models import Domain, DomainThreshold, Child


def _child_age_in_months(child: Child) -> int:
    return child.age_years * 12 + child.age_months


def _range_contains(age_months: int, y_min: int, m_min: int, y_max: int, m_max: int) -> bool:
    lo = y_min * 12 + m_min
    hi = y_max * 12 + m_max
    return lo <= age_months <= hi


def classify_domain_score(
    session: Session, *, domain_code: str, child: Child, score: int
) -> Tuple[str, int]:
    """
    Returnerer (color, missing_points_to_green)
    color ∈ {"green","yellow","red"}
    missing_points_to_green >= 0 (hvor mange point barnet mangler for grøn; 0 hvis allerede grøn)
    """
    color: str = "yellow"
    missing: int = 0

    domain = session.exec(select(Domain).where(
        Domain.code == domain_code)).first()
    if not domain:
        # Ukendt domain => neutral "yellow"
        return (color, missing)

    age_m = _child_age_in_months(child)
    rows = session.exec(
        select(DomainThreshold).where(DomainThreshold.domain_id == domain.id)
    ).all()

    applicable: DomainThreshold | None = None
    for r in rows:
        if _range_contains(age_m, r.age_years_min, r.age_months_min, r.age_years_max, r.age_months_max):
            applicable = r
            break

    if not applicable:
        # ingen threshold for alderen → konservativt "yellow"
        return (color, missing)

    if score >= applicable.score_min_green:
        color = "green"
        missing = 0
    elif score >= applicable.score_min_yellow:
        color = "yellow"
        missing = max(0, applicable.score_min_green - score)
    else:
        color = "red"
        missing = max(0, applicable.score_min_green - score)

    return (color, missing)
