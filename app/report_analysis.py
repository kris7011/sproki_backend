# app/report_analysis.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sqlmodel import Session, select

from app.models import Domain, DomainThreshold
from app.models_report import ChildReport, ChildReportScore


@dataclass
class DomainAnalysisResult:
    domain_code: str
    domain_name: str
    raw_score: int
    zone: str  # "green" | "yellow" | "red" | "no_threshold"
    points_to_green: Optional[int]


@dataclass
class ReportAnalysisResult:
    report_id: int
    child_id: int
    age_months: int
    domains: List[DomainAnalysisResult]


def _find_threshold_for_domain_and_age(
    session: Session,
    domain_id: int,
    age_months: int,
) -> Optional[DomainThreshold]:
    target_total = age_months

    thresholds = list(
        session.exec(
            select(DomainThreshold).where(
                DomainThreshold.domain_id == domain_id)
        )
    )

    for t in thresholds:
        min_total = (t.age_years_min * 12) + t.age_months_min
        max_total = (t.age_years_max * 12) + t.age_months_max
        if min_total <= target_total <= max_total:
            return t

    return None


def _get_score_value(score: ChildReportScore) -> int:
    raw = getattr(score, "raw_score", None)
    if isinstance(raw, int):
        return raw
    legacy = getattr(score, "score", 0)
    return int(legacy or 0)


def _resolve_domain(
    score: ChildReportScore,
    domains_by_id: Dict[int, Domain],
    domains_by_code: Dict[str, Domain],
) -> Optional[Domain]:
    if score.domain_id is not None:
        return domains_by_id.get(score.domain_id)

    code = getattr(score, "domain", "unknown")
    return domains_by_code.get(code)


def _no_threshold_result(raw: int) -> DomainAnalysisResult:
    return DomainAnalysisResult(
        domain_code="unknown",
        domain_name="Unknown domain",
        raw_score=raw,
        zone="no_threshold",
        points_to_green=None,
    )


def _zone_and_points(
    raw: int,
    green_min: int,
    yellow_min: int,
) -> Tuple[str, Optional[int]]:
    if raw >= green_min:
        return "green", 0
    if raw >= yellow_min:
        return "yellow", green_min - raw
    return "red", green_min - raw


def _analyze_score(
    session: Session,
    report_age_months: int,
    score: ChildReportScore,
    domains_by_id: Dict[int, Domain],
    domains_by_code: Dict[str, Domain],
) -> DomainAnalysisResult:
    raw = _get_score_value(score)

    domain_obj = _resolve_domain(score, domains_by_id, domains_by_code)
    if domain_obj is None or domain_obj.id is None:
        return _no_threshold_result(raw)

    threshold = _find_threshold_for_domain_and_age(
        session=session,
        domain_id=domain_obj.id,
        age_months=report_age_months,
    )
    if threshold is None:
        return DomainAnalysisResult(
            domain_code=domain_obj.code,
            domain_name=domain_obj.name,
            raw_score=raw,
            zone="no_threshold",
            points_to_green=None,
        )

    zone, points = _zone_and_points(
        raw=raw,
        green_min=threshold.score_min_green,
        yellow_min=threshold.score_min_yellow,
    )

    return DomainAnalysisResult(
        domain_code=domain_obj.code,
        domain_name=domain_obj.name,
        raw_score=raw,
        zone=zone,
        points_to_green=points,
    )


def compute_report_analysis(session: Session, report: ChildReport) -> ReportAnalysisResult:
    assert report.id is not None, "Report must have an id before analysis"

    scores = list(
        session.exec(
            select(ChildReportScore).where(
                ChildReportScore.report_id == report.id)
        )
    )

    domain_ids: Set[int] = {
        s.domain_id for s in scores if s.domain_id is not None}
    legacy_domain_codes: Set[str] = {
        s.domain for s in scores if (s.domain_id is None and getattr(s, "domain", None))
    }

    if not domain_ids and not legacy_domain_codes:
        return ReportAnalysisResult(
            report_id=report.id,
            child_id=report.child_id,
            age_months=report.age_months,
            domains=[],
        )

    all_domains = list(session.exec(select(Domain)))

    domains_by_id: Dict[int, Domain] = {
        d.id: d for d in all_domains if d.id is not None and d.id in domain_ids
    }
    domains_by_code: Dict[str, Domain] = {
        d.code: d for d in all_domains if getattr(d, "code", None)
    }

    results = [
        _analyze_score(
            session=session,
            report_age_months=report.age_months,
            score=s,
            domains_by_id=domains_by_id,
            domains_by_code=domains_by_code,
        )
        for s in scores
    ]

    return ReportAnalysisResult(
        report_id=report.id,
        child_id=report.child_id,
        age_months=report.age_months,
        domains=results,
    )
