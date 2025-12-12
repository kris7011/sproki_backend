# app/report_analysis.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Set

from sqlmodel import Session, select

from .models_report import Domain, Threshold, ChildReport, ChildReportScore


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


def _get_threshold_for_domain_and_age(
    session: Session,
    domain_id: int,
    age_months: int,
) -> Optional[Threshold]:
    statement = (
        select(Threshold)
        .where(Threshold.domain_id == domain_id)
        .where(Threshold.min_age_months <= age_months)
        .where(Threshold.max_age_months >= age_months)
    )
    return session.exec(statement).first()


def compute_report_analysis(
    session: Session,
    report: ChildReport,
) -> ReportAnalysisResult:
    # Load all scores for this report
    scores_stmt = select(ChildReportScore).where(
        ChildReportScore.report_id == report.id
    )
    scores = list(session.exec(scores_stmt))

    # Collect domain ids
    domain_ids: Set[int] = {s.domain_id for s in scores}

    # If no scores, return empty result
    if not domain_ids:
        assert report.id is not None, "Report must have an id before analysis"
        return ReportAnalysisResult(
            report_id=report.id,
            child_id=report.child_id,
            age_months=report.age_months,
            domains=[],
        )

    # Load all domains and filter in Python instead of using .in_ (Pylance doesn't like .in_)
    all_domains = list(session.exec(select(Domain)))
    domains_by_id: Dict[int, Domain] = {
        d.id: d for d in all_domains if d.id is not None and d.id in domain_ids
    }

    domain_results: List[DomainAnalysisResult] = []

    for score in scores:
        domain = domains_by_id.get(score.domain_id)
        if domain is None:
            domain_results.append(
                DomainAnalysisResult(
                    domain_code="unknown",
                    domain_name="Unknown domain",
                    raw_score=score.raw_score,
                    zone="no_threshold",
                    points_to_green=None,
                )
            )
            continue

        # Pylance ser domain.id som int | None, så vi gør det eksplicit
        domain_id = domain.id
        if domain_id is None:
            domain_results.append(
                DomainAnalysisResult(
                    domain_code=domain.code,
                    domain_name=domain.name,
                    raw_score=score.raw_score,
                    zone="no_threshold",
                    points_to_green=None,
                )
            )
            continue

        threshold = _get_threshold_for_domain_and_age(
            session=session,
            domain_id=domain_id,
            age_months=report.age_months,
        )

        if threshold is None:
            # No threshold configured for this age/domain
            domain_results.append(
                DomainAnalysisResult(
                    domain_code=domain.code,
                    domain_name=domain.name,
                    raw_score=score.raw_score,
                    zone="no_threshold",
                    points_to_green=None,
                )
            )
            continue

        # Determine zone
        raw = score.raw_score

        if raw >= threshold.green_min:
            zone = "green"
            points_to_green: Optional[int] = 0
        elif raw >= threshold.yellow_min:
            zone = "yellow"
            points_to_green = threshold.green_min - raw
        else:
            zone = "red"
            points_to_green = threshold.green_min - raw

        domain_results.append(
            DomainAnalysisResult(
                domain_code=domain.code,
                domain_name=domain.name,
                raw_score=raw,
                zone=zone,
                points_to_green=points_to_green,
            )
        )

    assert report.id is not None, "Report must have an id before analysis"

    return ReportAnalysisResult(
        report_id=report.id,
        child_id=report.child_id,
        age_months=report.age_months,
        domains=domain_results,
    )
