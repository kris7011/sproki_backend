# app/routers/thresholds.py
from __future__ import annotations

import csv
import io
from typing import Annotated, Awaitable, cast

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from app.auth import require_role, User
from app.db import get_session
from app.models import Domain, DomainThreshold

router = APIRouter(prefix="/thresholds", tags=["thresholds"])

CSV_SUFFIXES: tuple[str, ...] = (".csv", ".txt")


class DomainThresholdRead(SQLModel):
    id: int | None
    domain_id: int
    domain_code: str
    age_years_min: int
    age_months_min: int
    age_years_max: int
    age_months_max: int
    score_min_green: int
    score_min_yellow: int


def _to_int(row: dict[str, str], key: str) -> int:
    v = (row.get(key) or "").strip()
    if v == "":
        raise ValueError(f"Missing '{key}'")
    return int(v)


def _get_domain_by_code(session: Session, code: str) -> Domain | None:
    code = (code or "").strip().lower()
    if not code:
        return None
    return session.exec(select(Domain).where(Domain.code == code)).first()


def _detect_mode(header_fields: set[str]) -> str:
    required_a = {
        "domain_code",
        "age_years_min",
        "age_months_min",
        "age_years_max",
        "age_months_max",
        "score_min_yellow",
        "score_min_green",
    }
    required_b = {"domain", "age_years",
                  "age_months", "yellow_min", "green_min"}

    if required_a.issubset(header_fields):
        return "minmax"
    if required_b.issubset(header_fields):
        return "simple"

    raise HTTPException(
        status_code=400,
        detail=(
            "CSV header not recognized. Use either:\n"
            f"- Min/Max format: {sorted(required_a)}\n"
            f"- Simple format: {sorted(required_b)}\n"
            f"Found: {sorted(header_fields)}"
        ),
    )


def _build_threshold_minmax(session: Session, row: dict[str, str]) -> DomainThreshold:
    domain_code = (row.get("domain_code") or "").strip()
    domain = _get_domain_by_code(session, domain_code)
    if domain is None or domain.id is None:
        raise ValueError(f"Unknown domain_code '{domain_code}'")

    return DomainThreshold(
        id=None,
        domain_id=int(domain.id),
        age_years_min=_to_int(row, "age_years_min"),
        age_months_min=_to_int(row, "age_months_min"),
        age_years_max=_to_int(row, "age_years_max"),
        age_months_max=_to_int(row, "age_months_max"),
        score_min_yellow=_to_int(row, "score_min_yellow"),
        score_min_green=_to_int(row, "score_min_green"),
    )


def _build_threshold_simple(session: Session, row: dict[str, str]) -> DomainThreshold:
    domain_code = (row.get("domain") or "").strip()
    domain = _get_domain_by_code(session, domain_code)
    if domain is None or domain.id is None:
        raise ValueError(
            f"Unknown domain '{domain_code}' (expected Domain.code)")

    years = _to_int(row, "age_years")
    months = _to_int(row, "age_months")

    return DomainThreshold(
        id=None,
        domain_id=int(domain.id),
        age_years_min=years,
        age_months_min=months,
        age_years_max=years,
        age_months_max=months,
        score_min_yellow=_to_int(row, "yellow_min"),
        score_min_green=_to_int(row, "green_min"),
    )


@router.post("/import")
async def import_thresholds(
    user: Annotated[User, Depends(require_role(["leader"]))],
    session: Annotated[Session, Depends(get_session)],
    csv_file: UploadFile = File(...),
):
    filename = csv_file.filename or ""
    if not filename.lower().endswith(CSV_SUFFIXES):
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    try:
        raw = await cast(Awaitable[bytes], csv_file.read())
    except Exception as ex:
        raise HTTPException(
            status_code=400, detail=f"Failed to read file: {ex}")

    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header_fields = set(reader.fieldnames or [])

    mode = _detect_mode(header_fields)

    created = 0
    for row in reader:
        try:
            th = _build_threshold_minmax(
                session, row) if mode == "minmax" else _build_threshold_simple(session, row)
        except Exception as ex:
            raise HTTPException(
                status_code=400, detail=f"Invalid row: {row} ({ex})")

        session.add(th)
        created += 1

    session.commit()
    return {"imported": created, "mode": mode}


@router.get("/", response_model=list[DomainThresholdRead])
def list_thresholds(
    user: Annotated[User, Depends(require_role(["leader", "ppr", "staff", "parent"]))],
    session: Annotated[Session, Depends(get_session)],
):
    thresholds = session.exec(select(DomainThreshold)).all()
    domains = session.exec(select(Domain)).all()
    code_by_id = {int(d.id): d.code for d in domains if d.id is not None}

    result: list[DomainThresholdRead] = []
    for t in thresholds:
        result.append(
            DomainThresholdRead(
                id=t.id,
                domain_id=t.domain_id,
                domain_code=code_by_id.get(int(t.domain_id), ""),
                age_years_min=t.age_years_min,
                age_months_min=t.age_months_min,
                age_years_max=t.age_years_max,
                age_months_max=t.age_months_max,
                score_min_green=t.score_min_green,
                score_min_yellow=t.score_min_yellow,
            )
        )

    return result
