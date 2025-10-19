import csv
import io
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session
from app.models_learning import DomainThreshold
from app.auth import require_role, User

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.post("/import")
async def import_thresholds(
    csv_file: UploadFile = File(...),
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    if not csv_file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    text = (await csv_file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    required = {"domain", "age_years", "age_months", "yellow_min", "green_min"}

    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400, detail=f"CSV must contain: {sorted(required)}")

    count = 0
    for row in reader:
        th = DomainThreshold(
            domain=row["domain"].strip(),
            age_years=int(row["age_years"]),
            age_months=int(row["age_months"]),
            yellow_min=int(row["yellow_min"]),
            green_min=int(row["green_min"]),
        )
        session.add(th)
        count += 1
    session.commit()
    return {"imported": count}
