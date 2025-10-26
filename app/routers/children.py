# === FILE: app/routers/children.py
from __future__ import annotations
from typing import TypedDict, Any, cast, Awaitable, AsyncContextManager
from pydantic import BaseModel
import os
import re
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from sqlalchemy import desc  # <- til sortering i summary

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
from app.routers.reports import AnalyzeRequest, analyze_report
from app.models_progress import DomainProgress

# Brug dependency direkte fra app.db (den YIELDer en Session)
from app.db import get_session as get_db_session

# optional async file lib
try:
    import aiofiles  # type: ignore
except Exception:
    aiofiles = None

router = APIRouter(prefix="/children", tags=["children"])

# Base folder for uploads (override med env var SPROKI_UPLOAD_DIR)
UPLOAD_BASE = Path(os.getenv("SPROKI_UPLOAD_DIR", "./uploads"))

# Reusable messages
CHILD_NOT_FOUND = "Child not found"

# ---------- Small utilities ----------


def _id_or_500(val: Optional[int], what: str) -> int:
    if val is None:
        raise HTTPException(status_code=500, detail=f"{what} has no ID yet")
    return val


def _normalize_emails(values: Optional[List[str]]) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for v in values:
        if not v:
            continue
        parts = re.split(r"[,\s;]+", v.strip())
        for p in parts:
            if p:
                out.append(p.lower())
    seen: set[str] = set()
    deduped: list[str] = []
    for e in out:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return deduped

# 👇 lille helper til onclause (gør typecheckeren glad)


def _on(expr: Any) -> Any:
    return expr

# ---------- Helpers (keep main handler simple) ----------


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
        parent = session.exec(
            select(Parent).where(Parent.email == email)
        ).first()
        if not parent:
            parent = Parent(name=email.split("@")[0], email=email)
            session.add(parent)
            session.commit()
            session.refresh(parent)
        parent_id = _id_or_500(parent.id, "Parent")
        session.add(ChildParentLink(child_id=child_id, parent_id=parent_id))
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
    # widen til Awaitable[bytes] for at tilfredsstille pyright
    content = await cast(Awaitable[bytes], report_file.read())
    if not content:
        return None
    original = report_file.filename or "report.bin"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    child_dir = UPLOAD_BASE / "reports" / str(_id_or_500(child.id, "Child"))
    child_dir.mkdir(parents=True, exist_ok=True)
    out_path = child_dir / f"{ts}_{safe_name}"

    if aiofiles:
        # aiofiles.open(...) type-annoteres af nogle stubs som en coroutine,
        # så vi widener til AsyncContextManager[Any], som 'async with' forventer.
        fctx = cast(AsyncContextManager[Any], aiofiles.open(
            out_path, "wb"))  # type: ignore[arg-type]
        async with fctx as f:
            # .write(...) kan også være annoteret som coroutine; widen til Awaitable[int]
            _ = await cast(Awaitable[int], f.write(content))
    else:
        # asyncio.to_thread(...) returnerer et awaitable; widen for pyright
        _ = await cast(Awaitable[int], asyncio.to_thread(out_path.write_bytes, content))

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
                html=(
                    f"<p>Hej! Dit barn '{child.name}' er oprettet. "
                    "Log ind med MitID via appen for at komme i gang.</p>"
                ),
            )
        )


def _notify_ppr_if_needed(child: Child, institution_id: int, ppr_consent: bool) -> None:
    if not ppr_consent:
        return
    mailer.send(
        MailMessage(
            to="ppr@example.com",
            subject=f"PPR-tilknytning: {child.name}",
            html=(
                f"<p>Barnet '{child.name}' er markeret til PPR. "
                f"Institution ID: {institution_id}</p>"
            ),
        )
    )

# ---------------------------- Create route ----------------------------


@router.post("/", response_model=Child)
async def create_child(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
    name: str = Form(...),
    age_years: int = Form(...),
    age_months: int = Form(...),
    institution_id: int = Form(...),
    ppr_consent: bool = Form(False),
    parent_emails: Optional[List[str]] = Form(None),
    staff_ids: Optional[List[int]] = Form(None),
    report_file: Optional[UploadFile] = File(None),
):
    if age_years < 0 or age_months < 0 or age_months > 11:
        raise HTTPException(
            status_code=400, detail="Invalid age (years/months)"
        )

    _require_institution(session, institution_id)

    child = _create_child_entity(
        session,
        name=name,
        age_years=age_years,
        age_months=age_months,
        institution_id=institution_id,
        ppr_consent=ppr_consent,
    )

    child_id = _id_or_500(child.id, "Child")

    parent_list = _normalize_emails(parent_emails)
    if parent_list:
        _upsert_parents_and_link(
            session, child_id=child_id, parent_emails=parent_list
        )

    staff_list = staff_ids or []
    if staff_list:
        _link_staff(session, child_id=child_id, staff_ids=staff_list)

    if report_file is not None:
        out_path = await _save_report_async(child, report_file)
        if out_path is not None:
            session.add(child)
            session.commit()
            session.refresh(child)
            print(f"[REPORT-UPLOAD] child={child_id} path={out_path}")

    if parent_list:
        _notify_parents(child, parent_list)
    _notify_ppr_if_needed(child, institution_id, ppr_consent)

    return child

# ---------------------------- Read routes ----------------------------


class LatestReportMeta(BaseModel):
    filename: str
    path: str
    uploaded_at: Optional[datetime]  # UTC


@router.get("/{child_id}/latest-report", response_model=LatestReportMeta | None)
def get_latest_report_meta(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    if hasattr(child, "report_path") and getattr(child, "report_path"):
        rp = str(getattr(child, "report_path"))
        fn = os.path.basename(rp)
        return LatestReportMeta(filename=fn, path=rp, uploaded_at=_parse_report_ts(fn))

    child_dir = UPLOAD_BASE / "reports" / str(child_id)
    if not child_dir.exists():
        return None
    files = sorted(
        (p for p in child_dir.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    top = files[0]
    return LatestReportMeta(
        filename=top.name,
        path=str(top),
        uploaded_at=_parse_report_ts(top.name),
    )


@router.get("/{child_id}", response_model=Child)
def get_child(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)
    return child


@router.get("/{child_id}/parents", response_model=list[Parent])
def get_child_parents(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    if not session.get(Child, child_id):
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    q = (
        select(Parent)
        .join(ChildParentLink, _on(Parent.id == ChildParentLink.parent_id))
        .where(ChildParentLink.child_id == child_id)
    )
    return session.exec(q).all()


@router.get("/{child_id}/staff", response_model=list[Staff])
def get_child_staff(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff"])),
    session: Session = Depends(get_db_session),
):
    if not session.get(Child, child_id):
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    q = (
        select(Staff)
        .join(ChildStaffLink, _on(Staff.id == ChildStaffLink.staff_id))
        .where(ChildStaffLink.child_id == child_id)
    )
    return session.exec(q).all()


@router.get("/by-institution/{institution_id}", response_model=list[Child])
def list_children_by_institution(
    institution_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff"])),
    session: Session = Depends(get_db_session),
):
    _require_institution(session, institution_id)
    q = select(Child).where(Child.institution_id == institution_id)
    return session.exec(q).all()


def _persist_analysis_to_progress(
    session: Session,
    child_id: int,
    analyze_res,  # AnalyzeResponse
) -> None:
    if not analyze_res or not getattr(analyze_res, "results", None):
        return
    for r in analyze_res.results:
        row = DomainProgress(
            child_id=child_id,
            domain=r.domain,
            score=r.score,
            color=r.color,
        )
        session.add(row)
    session.commit()


@router.post("/{child_id}/analyze")
def analyze_for_child_and_save(
    child_id: int,
    body: AnalyzeRequest,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    res = analyze_report(body, user=user, session=session)
    _persist_analysis_to_progress(session, child_id, res)
    return res


_TS_RE = re.compile(r"^(?P<ts>\d{8}T\d{6})_")


def _parse_report_ts(filename: str) -> Optional[datetime]:
    m = _TS_RE.match(filename or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group("ts"), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


class ChildLinksResponse(TypedDict):
    parents: list[Parent]
    staff: list[Staff]


@router.delete("/{child_id}/staff/{staff_id}")
def unlink_staff(
    child_id: int,
    staff_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    staff = session.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    link = session.exec(
        select(ChildStaffLink).where(
            ChildStaffLink.child_id == child_id,
            ChildStaffLink.staff_id == staff_id,
        )
    ).first()

    if not link:
        return {"unlinked": False, "reason": "link_not_found"}

    session.delete(link)
    session.commit()
    return {"unlinked": True}


@router.delete("/{child_id}/parent/{parent_id}")
def unlink_parent(
    child_id: int,
    parent_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    parent = session.get(Parent, parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    link = session.exec(
        select(ChildParentLink).where(
            ChildParentLink.child_id == child_id,
            ChildParentLink.parent_id == parent_id,
        )
    ).first()

    if not link:
        return {"unlinked": False, "reason": "link_not_found"}

    session.delete(link)
    session.commit()
    return {"unlinked": True}


@router.get("/{child_id}/links", response_model=ChildLinksResponse)
def get_child_links(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    if not session.get(Child, child_id):
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    parents = session.exec(
        select(Parent)
        .join(ChildParentLink, _on(Parent.id == ChildParentLink.parent_id))
        .where(ChildParentLink.child_id == child_id)
    ).all()

    staff = session.exec(
        select(Staff)
        .join(ChildStaffLink, _on(Staff.id == ChildStaffLink.staff_id))
        .where(ChildStaffLink.child_id == child_id)
    ).all()

    return {"parents": parents, "staff": staff}

# ---------------------------- Summary route ----------------------------


def _ensure_parent_can_access(session: Session, user: User, child_id: int) -> None:
    """Hvis bruger er parent, må de kun se børn de er linket til."""
    if getattr(user, "role", None) != "parent":
        return
    exists = session.exec(
        select(ChildParentLink).where(
            ChildParentLink.child_id == child_id,
            ChildParentLink.parent_id == getattr(user, "id", -1),
        )
    ).first()
    if not exists:
        raise HTTPException(
            status_code=403, detail="Not allowed for this child"
        )


class ChildSummary(TypedDict):
    child: Child
    parents: list[Parent]
    staff: list[Staff]
    latest_report: LatestReportMeta | None
    recent_progress: list[DomainProgress]


@router.get("/{child_id}/summary", response_model=ChildSummary)
def get_child_summary(
    child_id: int,
    user: User = Depends(require_role(["leader", "ppr", "staff", "parent"])),
    session: Session = Depends(get_db_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail=CHILD_NOT_FOUND)

    # Forældre må kun se egne børn
    _ensure_parent_can_access(session, user, child_id)

    parents = session.exec(
        select(Parent)
        .join(ChildParentLink, _on(Parent.id == ChildParentLink.parent_id))
        .where(ChildParentLink.child_id == child_id)
    ).all()

    staff = session.exec(
        select(Staff)
        .join(ChildStaffLink, _on(Staff.id == ChildStaffLink.staff_id))
        .where(ChildStaffLink.child_id == child_id)
    ).all()

    # Seneste rapport (genbrug af helper)
    latest_report = get_latest_report_meta(
        child_id, user=user, session=session)

    # Seneste 10 progress-rækker – cast kolonner så typechecker er glad
    created_col = cast(Any, DomainProgress.created_at)
    id_col = cast(Any, DomainProgress.id)
    recent_progress = session.exec(
        select(DomainProgress)
        .where(DomainProgress.child_id == child_id)
        .order_by(desc(created_col), desc(id_col))
        .limit(10)
    ).all()

    return {
        "child": child,
        "parents": parents,
        "staff": staff,
        "latest_report": latest_report,
        "recent_progress": recent_progress,
    }


@router.get("/", response_model=list[Child])
def list_children(
    user: User = Depends(require_role(["leader", "ppr", "staff"])),
    session: Session = Depends(get_db_session),
):
    return session.exec(select(Child)).all()
