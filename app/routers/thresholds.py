# === FILE: app/routers/thresholds.py
from __future__ import annotations

import csv
import io
from typing import Annotated, Generator, Awaitable, cast

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, select
from app.models_learning import DomainThreshold
from app.auth import require_role, User

router = APIRouter(prefix="/thresholds", tags=["thresholds"])

# Eksplicit suffix-typed konstant så Pyright accepterer endswith-argumentet
CSV_SUFFIXES: tuple[str, ...] = (".csv", ".txt")


def get_session() -> Generator[Session, None, None]:
    # Delegate to the real DB dependency which itself yields a Session
    from app.db import get_session as _gs
    yield from _gs()


@router.post("/import")
async def import_thresholds(
    user: Annotated[User, Depends(require_role(["leader"]))],
    session: Annotated[Session, Depends(get_session)],
    csv_file: UploadFile = File(...),
):
    # Defensive check: handle None filename
    filename = csv_file.filename or ""
    if not filename.lower().endswith(CSV_SUFFIXES):
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    try:
        # Pyright shim: cast coroutine til Awaitable[bytes] før await
        raw = await cast(Awaitable[bytes], csv_file.read())
    except Exception as ex:
        raise HTTPException(
            status_code=400, detail=f"Failed to read file: {ex}"
        )

    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    required = {"domain", "age_years", "age_months", "yellow_min", "green_min"}
    header_fields = set(reader.fieldnames or [])
    if not required.issubset(header_fields):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain: {sorted(required)}; found: {sorted(header_fields)}",
        )

    count = 0
    for row in reader:
        try:
            th = DomainThreshold(
                domain=row["domain"].strip(),
                age_years=int(row["age_years"]),
                age_months=int(row["age_months"]),
                yellow_min=int(row["yellow_min"]),
                green_min=int(row["green_min"]),
            )
        except Exception as ex:
            raise HTTPException(
                status_code=400, detail=f"Invalid row: {row} ({ex})"
            )

        session.add(th)
        count += 1

    session.commit()
    return {"imported": count}


@router.get("/", response_model=list[DomainThreshold])
def list_thresholds(
    user: Annotated[User, Depends(require_role(["leader", "ppr", "staff", "parent"]))],
    session: Annotated[Session, Depends(get_session)],
):
    return session.exec(select(DomainThreshold)).all()
