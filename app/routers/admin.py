# === FILE: app/routers/admin.py
from __future__ import annotations

import json
from typing import Any, cast, Iterable, Optional, Tuple, List, Dict, TypeVar, Type, Mapping

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import require_role, User
from app.db import get_session as get_db_session

# Institution/børn/staff/forældre
from app.models_institution import (
    Institution,
    Staff,
    Child,
    Parent,
    ChildParentLink,
    ChildStaffLink,
)

# Øvelser og thresholds (matcher din øvrige kodebase)
from app.models_learning import Exercise, DomainThreshold

router = APIRouter(prefix="/admin", tags=["admin"])

INSTITUTION_NOT_FOUND = "Institution not found"
CHILD_NOT_FOUND = "Child not found"
PARENT_NOT_FOUND = "Parent not found"
STAFF_NOT_FOUND = "Staff not found"

T = TypeVar("T")


def _get_or_create(
    session: Session,
    model: Type[T],
    where: Iterable[Any],
    defaults: Mapping[str, Any],
) -> Tuple[T, bool]:
    row: Optional[T] = session.exec(select(model).where(*where)).first()
    if row is not None:
        return row, False
    # Konstruktion af model-objektet
    new_row = cast(T, model(**defaults))  # type: ignore[arg-type]
    session.add(new_row)
    session.commit()
    session.refresh(new_row)
    return new_row, True


def _id_or_500(val: Optional[int], what: str) -> int:
    if val is None:
        raise RuntimeError(f"{what} has no id yet")
    return val


# ----------------------- Small, focused helpers -----------------------

def _seed_institution(session: Session) -> Tuple[Institution, bool, int]:
    inst, created = _get_or_create(
        session,
        Institution,
        where=[Institution.name == "Solstrålen Børnehave"],
        defaults={
            "name": "Solstrålen Børnehave",
            "address": "Solsikkevej 12",
            "zip_code": "2100",
            "city": "København Ø",
            "country": "DK",
            "phone": "+45 12 34 56 78",
            "email": "kontakt@solstraalen.dk",
        },
    )
    return inst, created, _id_or_500(inst.id, "Institution")


def _seed_staff(session: Session, inst_id: int) -> Tuple[List[Staff], int]:
    specs: List[Dict[str, Any]] = [
        {
            "where": [Staff.email == "paedagog1@solstraalen.dk"],
            "defaults": {
                "institution_id": inst_id,
                "name": "Pædagog 1",
                "email": "paedagog1@solstraalen.dk",
                "role": "staff",
            },
        },
        {
            "where": [Staff.email == "paedagog2@solstraalen.dk"],
            "defaults": {
                "institution_id": inst_id,
                "name": "Pædagog 2",
                "email": "paedagog2@solstraalen.dk",
                "role": "staff",
            },
        },
    ]
    staff_list: List[Staff] = []
    created_count = 0
    for s in specs:
        staff, created = _get_or_create(
            session, Staff, s["where"], cast(Mapping[str, Any], s["defaults"])
        )
        staff_list.append(staff)
        if created:
            created_count += 1
    return staff_list, created_count


def _seed_children(session: Session, inst_id: int) -> Tuple[List[Child], int]:
    specs: List[Dict[str, Any]] = [
        {
            "where": [Child.name == "Alma"],
            "defaults": {
                "name": "Alma",
                "age_years": 4,
                "age_months": 3,
                "institution_id": inst_id,
                "ppr_consent": False,
            },
        },
        {
            "where": [Child.name == "Noah"],
            "defaults": {
                "name": "Noah",
                "age_years": 5,
                "age_months": 1,
                "institution_id": inst_id,
                "ppr_consent": True,
            },
        },
    ]
    children: List[Child] = []
    created_count = 0
    for c in specs:
        child, created = _get_or_create(
            session, Child, c["where"], cast(Mapping[str, Any], c["defaults"])
        )
        children.append(child)
        if created:
            created_count += 1
    return children, created_count


def _ensure_parent_links(session: Session, pairs: List[Tuple[Child, str, str]]) -> int:
    created = 0
    for (child, pmail, pname) in pairs:
        parent, _ = _get_or_create(
            session, Parent, where=[Parent.email == pmail], defaults={"name": pname, "email": pmail}
        )
        child_id = _id_or_500(child.id, "Child")
        parent_id = _id_or_500(parent.id, "Parent")
        link = session.exec(
            select(ChildParentLink).where(
                ChildParentLink.child_id == child_id, ChildParentLink.parent_id == parent_id
            )
        ).first()
        if not link:
            session.add(ChildParentLink(child_id=child_id, parent_id=parent_id))
            session.commit()
            created += 1
    return created


def _ensure_staff_links(session: Session, pairs: List[Tuple[int, int]]) -> int:
    created = 0
    for (child_id, staff_id) in pairs:
        link = session.exec(
            select(ChildStaffLink).where(
                ChildStaffLink.child_id == child_id, ChildStaffLink.staff_id == staff_id
            )
        ).first()
        if not link:
            session.add(ChildStaffLink(child_id=child_id, staff_id=staff_id))
            session.commit()
            created += 1
    return created


def _ensure_exercises(session: Session) -> int:
    defs: List[Dict[str, Any]] = [
        {
            "domain": "rim",
            "title": "Rim: kat-hat",
            "payload": {"type": "rim", "prompt": "Find ord der rimer på 'kat'"},
        },
        {
            "domain": "rim",
            "title": "Rim: sol-bol",
            "payload": {"type": "rim", "prompt": "Hvilke ord rimer på 'sol'?"},
        },
        {
            "domain": "ordforraad",
            "title": "Ord: frugt",
            "payload": {"type": "ordforraad", "prompt": "Peg på en banan"},
        },
        {
            "domain": "ordforraad",
            "title": "Ord: dyr",
            "payload": {"type": "ordforraad", "prompt": "Vis mig en hest"},
        },
    ]
    created = 0
    for d in defs:
        dom = cast(str, d["domain"])
        payload_dict = cast(dict, d["payload"])
        existing = None
        if hasattr(Exercise, "title"):
            existing = session.exec(
                select(Exercise).where(
                    Exercise.domain == dom,
                    getattr(Exercise, "title") == cast(
                        str, d["title"]  # type: ignore[attr-defined]
                    ),
                )
            ).first()
        else:
            existing = session.exec(select(Exercise).where(Exercise.domain == dom)).first()
        if existing:
            continue
        ex = Exercise(domain=dom, payload_json=json.dumps(payload_dict))
        if hasattr(ex, "title"):
            setattr(ex, "title", cast(str, d["title"]))
        session.add(ex)
        session.commit()
        created += 1
    return created


def _ensure_thresholds(session: Session) -> int:
    th_defs: List[Tuple[str, int, int, int, int]] = [
        ("rim", 4, 0, 35, 50),
        ("rim", 4, 6, 40, 55),
        ("rim", 5, 0, 45, 60),
        ("ordforraad", 4, 0, 40, 55),
        ("ordforraad", 4, 6, 45, 60),
        ("ordforraad", 5, 0, 50, 65),
    ]
    created = 0
    for dom, yy, mm, y_min, g_min in th_defs:
        exists = session.exec(
            select(DomainThreshold).where(
                DomainThreshold.domain == dom,
                DomainThreshold.age_years == yy,
                DomainThreshold.age_months == mm,
            )
        ).first()
        if exists:
            continue
        session.add(
            DomainThreshold(
                domain=dom,
                age_years=yy,
                age_months=mm,
                yellow_min=y_min,
                green_min=g_min,
            )
        )
        session.commit()
        created += 1
    return created


# ----------------------- Orchestrator (reduced CC) -----------------------

@router.post("/seed-demo-data")
def seed_demo_data(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    """
    Opretter enkle demo-data, idempotent-ish.
    """

    # Institution
    _, inst_created, inst_id = _seed_institution(session)  # <- inst erstattet af "_"

    # Staff
    staff_list, staff_created = _seed_staff(session, inst_id)
    s1_id = _id_or_500(staff_list[0].id, "Staff")
    s2_id = _id_or_500(staff_list[1].id, "Staff")

    # Children
    children, children_created = _seed_children(session, inst_id)
    c1_id = _id_or_500(children[0].id, "Child")
    c2_id = _id_or_500(children[1].id, "Child")

    # Parent links (brug præcis type for at tilfredsstille Pyright)
    parent_pairs: List[Tuple[Child, str, str]] = [
        (children[0], "mor.alma@example.com", "Almas Mor"),
        (children[0], "far.alma@example.com", "Almas Far"),
        (children[1], "mor.noah@example.com", "Noahs Mor"),
    ]
    links_parent_created = _ensure_parent_links(session, parent_pairs)

    # Staff links (brug præcis type for at tilfredsstille Pyright)
    staff_pairs: List[Tuple[int, int]] = [(c1_id, s1_id), (c1_id, s2_id), (c2_id, s2_id)]
    links_staff_created = _ensure_staff_links(session, staff_pairs)

    # Exercises
    exercises_created = _ensure_exercises(session)

    # Thresholds
    thresholds_created = _ensure_thresholds(session)

    return {
        "seeded": True,
        "institution": {"id": inst_id, "created": inst_created},
        "children": {"ids": [c1_id, c2_id], "created": children_created},
        "staff": {"ids": [s1_id, s2_id], "created": staff_created},
        "links": {"parents_created": links_parent_created, "staff_created": links_staff_created},
        "exercises_created": exercises_created,
        "thresholds_created": thresholds_created,
    }


@router.post("/clear-demo-data")
def clear_demo_data(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    """Sletter alle demo-data (uden at ødelægge andre tabeller)."""
    deleted_counts: Dict[str, int] = {}

    def _delete(model: Any) -> int:
        rows = session.exec(select(model)).all()
        for row in rows:
            session.delete(row)
        session.commit()
        return len(rows)

    deleted_counts["DomainThreshold"] = _delete(DomainThreshold)
    deleted_counts["Exercise"] = _delete(Exercise)
    deleted_counts["ChildStaffLink"] = _delete(ChildStaffLink)
    deleted_counts["ChildParentLink"] = _delete(ChildParentLink)
    deleted_counts["Parent"] = _delete(Parent)
    deleted_counts["Child"] = _delete(Child)
    deleted_counts["Staff"] = _delete(Staff)
    deleted_counts["Institution"] = _delete(Institution)

    return {"cleared": True, "deleted": deleted_counts}
