# app/models_report.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from app.models import FK_CHILD_ID, FK_EXERCISEITEM_ID

# Keep this alias because report_analysis imports Domain
Domain = str

# (Optional) If you like DomainStr naming, keep it too
DomainStr = str


class Threshold(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    domain: DomainStr = Field(index=True)

    age_months_from: int = Field(index=True)
    age_months_to: int = Field(index=True)

    green_min: int = Field(default=0)
    yellow_min: int = Field(default=0)

    note: Optional[str] = None


class ChildReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    child_id: int = Field(foreign_key=FK_CHILD_ID, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # NEW (API expects these)
    source: str = Field(default="unknown", index=True)
    age_months: int = Field(default=0, index=True)

    # Existing/legacy fields (keep for now)
    report_type: str = Field(default="standard")
    total_score: int = Field(default=0)
    level: Optional[str] = None
    pdf_path: Optional[str] = None


class ChildReportScore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    report_id: int = Field(foreign_key="childreport.id", index=True)

    # LEGACY: was required before. We make it optional in the model (DB migration handles NOT NULL)
    item_id: Optional[int] = Field(
        default=None,
        foreign_key=FK_EXERCISEITEM_ID,
        index=True,
    )

    # NEW: preferred analysis keys
    domain_id: Optional[int] = Field(
        default=None,
        foreign_key="domain.id",
        index=True,
    )
    raw_score: int = Field(default=0)

    # LEGACY (keep, but don’t use going forward)
    domain: DomainStr = Field(default="unknown", index=True)
    score: int = Field(default=0)
    max_score: int = Field(default=1)

    note: Optional[str] = None
