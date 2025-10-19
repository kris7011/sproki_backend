# === FILE: app/routers/children.py
import os
import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Iterable
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select

from app.auth import require_role, User
from app.models_institution import (
    Child,
    Institution,
    Parent,
    ChildParentLink,
    Staff,
    ChildStaffLink,
)
from app.services.mailer import mailer, MailMessage

# optional async file lib
try:
    import aiofiles  # type: ignore
except Exception:
    aiofiles = None

router = APIRouter(prefix="/children", tags=["children"])

UPLOAD_BASE = Path(os.getenv("SPROKI_UPLOAD_DIR", "./uploads"))


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


# ---------- Helpers (low cyclomatic/cognitive complexity in main handler) ----------

def _require_institution(session: Session, institution_id: int) -> Institution:
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst


def _create_child_entity(
    session: Session,
    name: str,
    age_years: int,
    age_months: int,
    institution_id: int,
    ppr_consent: bool,
) -> Child:
    child = Child(
        name=name,
        age_years=age_years,
        age_months=age_months,
        institution_id=institution_id,
        ppr_consent=ppr_consent,
    )
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


def _upsert_parents_and_link(
    session: Session,
    child_id: int,
    parent_emails: Iterable[str],
) -> None:
    for email in parent_emails:
        parent = session.exec(select(Parent).where(
            Parent.email == email)).first()
        if not parent:
            parent = Parent(name=email.split("@")[0], email=email)
            session.add(parent)
            session.commit()
            session.refresh(parent)
        session.add(ChildParentLink(child_id=child_id, parent_id=parent.id))
    session.commit()


def _link_staff(
    session: Session,
    child_id: int,
    staff_ids: Iterable[int],
) -> None:
    for sid in staff_ids:
        if session.get(Staff, sid):
            session.add(ChildStaffLink(child_id=child_id, staff_id=sid))
    session.commit()


async def _save_report_async(child: Child, report_file: UploadFile) -> Optional[Path]:
    content = await report_file.read()
    original = report_file.filename or "report.bin"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    child_dir = UPLOAD_BASE / "reports" / str(child.id)
    child_dir.mkdir(parents=True, exist_ok=True)
    out_path = child_dir / f"{ts}_{safe_name}"

    if aiofiles:
        async with aiofiles.open(out_path, "wb") as f:
            await f.write(content)
    else:
        await asyncio.to_thread(out_path.write_bytes, content)

    # Persist reference on child (if attributes exist on model)
    if hasattr(child, "report_path"):
        child.report_path = str(out_path)
    if hasattr(child, "report_filename"):
        child.report_filename = original
    return out_path


def _notify_parents(child: Child, parent_emails: Iterable[str]) -> None:
    for email in parent_emails:
        mailer.send(
            MailMessage(
                to=email,
                subject="Dit barn er oprettet i Sproki",
                html=(f"<p>Hej! Dit barn '{child.name}' er oprettet. "
                      "Log ind med MitID via appen for at komme i gang.</p>"),
            )
        )


def _notify_ppr_if_needed(child: Child, institution_id: int, ppr_consent: bool) -> None:
    if not ppr_consent:
        return
    mailer.send(
        MailMessage(
            to="ppr@example.com",
            subject=f"PPR-tilknytning: {child.name}",
            html=(f"<p>Barnet '{child.name}' er markeret til PPR. "
                  f"Institution ID: {institution_id}</p>"),
        )
    )


# ---------------------------- Route handler (refactored) ----------------------------

@router.post("/", response_model=Child)
async def create_child(
    name: str = Form(...),
    age_years: int = Form(...),
    age_months: int = Form(...),
    institution_id: int = Form(...),
    ppr_consent: bool = Form(False),
    parent_emails: List[str] = Form([]),
    staff_ids: List[int] = Form([]),
    report_file: UploadFile = File(None),
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    _require_institution(session, institution_id)

    child = _create_child_entity(
        session,
        name=name,
        age_years=age_years,
        age_months=age_months,
        institution_id=institution_id,
        ppr_consent=ppr_consent,
    )

    _upsert_parents_and_link(session, child_id=child.id,
                             parent_emails=parent_emails)
    _link_staff(session, child_id=child.id, staff_ids=staff_ids)

    if report_file is not None:
        out_path = await _save_report_async(child, report_file)
        if out_path is not None:
            session.add(child)
            session.commit()
            session.refresh(child)
            print(f"[REPORT-UPLOAD] child={child.id} path={out_path}")

    _notify_parents(child, parent_emails)
    _notify_ppr_if_needed(child, institution_id, ppr_consent)

    return child
