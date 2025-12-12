# app/models_report.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from app.models import FK_CHILD_ID, FK_EXERCISEITEM_ID


class ChildReport(SQLModel, table=True):
    """
    Simpel rapport pr. barn.
    Vi holder den bevidst uden Relationship-felter for at undgå
    SQLAlchemy/typing problemer med Optional[...] og list[...] generics.
    """
    id: Optional[int] = Field(default=None, primary_key=True)

    # Hvilket barn rapporten hører til
    child_id: int = Field(foreign_key=FK_CHILD_ID, index=True)

    # Hvornår rapporten blev lavet
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Evt. type / label på rapporten
    report_type: str = Field(default="standard")

    # Evt. samlet score / niveau – kan du bruge eller lade være
    total_score: int = Field(default=0)
    level: Optional[str] = None

    # Hvis du på et tidspunkt vil gemme sti til genereret pdf
    pdf_path: Optional[str] = None


class ChildReportScore(SQLModel, table=True):
    """
    Enkelt-score pr. opgave/øvelse i en rapport.
    Igen: ingen Relationship(...) for at undgå generics-problemer.
    """
    id: Optional[int] = Field(default=None, primary_key=True)

    # FK til ChildReport
    report_id: int = Field(foreign_key="childreport.id", index=True)

    # FK til ExerciseItem (den konkrete øvelse)
    item_id: int = Field(foreign_key=FK_EXERCISEITEM_ID, index=True)

    # Selve scoren – tilpas felter efter hvad du reelt bruger
    score: int = Field(default=0)
    max_score: int = Field(default=1)

    note: Optional[str] = None
