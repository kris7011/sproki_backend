# api/main.py
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, cast

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field as PField
from sqlalchemy import asc, desc
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .pdf_parser import parse_scores_from_text


# ---------- Domæne-konstanter ----------
D_SPROGFORSTAELSE = "sprogforståelse"
D_ORDFORRAD = "ordforråd"
D_KOMM_STRAT = "kommunikativeStrategier"
D_RIM = "rim"
D_OPM_SKRIFT = "opmærksomhedPåSkrift"

DOMAINS: List[str] = [
    D_SPROGFORSTAELSE,
    D_ORDFORRAD,
    D_KOMM_STRAT,
    D_RIM,
    D_OPM_SKRIFT,
]

RECS: Dict[str, List[str]] = {
    D_RIM: [
        "Leg dagligt med rim-par (kat–hat, bil–pil).",
        "Syng remser med tydelig slutlyd og lad barnet fuldende.",
        "Rim-lotto med billeder/ord der rimer.",
    ],
    D_SPROGFORSTAELSE: [
        "Giv flerstegs-instruktioner i leg.",
        "Hvem/hvad/hvorfor-spørgsmål til billedbøger.",
        "Byg/tegn efter mundtlige beskrivelser.",
    ],
    D_ORDFORRAD: [
        "Temauge med 5–10 ord, brug dem dagligt.",
        "Udvid barnets ytringer (‘bil kører’ → ‘den røde bil kører hurtigt’).",
        "Kontraster: stor/lille, tung/let – vis konkret.",
    ],
    D_OPM_SKRIFT: [
        "Navnejagt: find bogstaver fra barnets navn.",
        "Peg-med-læsning (venstre→højre) under højtlæsning.",
        "Bogstav–lyd kobling (‘M’ som ‘mælk’).",
    ],
    D_KOMM_STRAT: [
        "Rollespil med turtagning (turbrik).",
        "Samtalekort: øv at spørge/svare.",
        "Fælles problemløsning i leg.",
    ],
}


# ---------- Enums ----------
class Zone(str, Enum):
    ROED = "rød"
    GUL = "gul"
    GROEN = "grøn"


class Outcome(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"


# ---------- DB modeller ----------
class Child(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: Optional[str] = None
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    childId: str = Field(index=True)
    ageMonths: int
    sprogforståelse: float
    ordforråd: float
    kommunikativeStrategier: float
    rim: float
    opmærksomhedPåSkrift: float
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class PracticeEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    childId: str = Field(index=True)
    domain: str = Field(index=True)   # skal matche DOMAINS
    exerciseId: str                   # klient-slug/id
    outcome: str                      # "success" | "fail" (gemmes som str)
    score: Optional[float] = None     # 0..1
    meta: Optional[str] = None        # JSON-string
    occurredAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


# ---------- Tærskler/zoner ----------
class Cutoff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(index=True)        # fx "rim"
    ageMinMonths: int = Field(index=True)  # inklusiv
    ageMaxMonths: int = Field(index=True)  # inklusiv
    greenMin: float                        # mindstescore for grøn
    # mindstescore for gul (under -> rød)
    yellowMin: float
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class _Threshold:
    yellow_min: float
    green_min: float


# ---------- Response modeller ----------
class PriorityItemModel(BaseModel):
    domain: str
    score: float
    zone: Zone
    distToGreen: float
    shortTermGoal: float
    tips: List[str]


class RecommendationItemModel(BaseModel):
    domain: str
    tips: List[str]


class PlanResponseModel(BaseModel):
    priorityAreas: List[PriorityItemModel]
    recommendations: List[RecommendationItemModel]
    meta: Dict[str, Any]


class OkResponse(BaseModel):
    ok: bool = True


class UpsertChildResponse(OkResponse):
    childId: str
    name: Optional[str] = None


class CreateReportResponse(OkResponse):
    reportId: int
    createdAt: str


class PracticeEventsResult(OkResponse):
    accepted: int


class UploadReportResponse(OkResponse):
    reportId: int
    createdAt: str
    scores: Dict[str, float]
    plan: PlanResponseModel
    storedPdfPath: str


# ---------- Hjælpere ----------
def _lookup_threshold(session: Session, domain: str, age_months: int) -> _Threshold:
    stmt = (
        select(Cutoff)
        .where(Cutoff.domain == domain)
        .order_by(asc(Cutoff.ageMinMonths), asc(Cutoff.ageMaxMonths))
    )
    rows = cast(List[Cutoff], session.exec(stmt).all())
    if not rows:
        return _Threshold(yellow_min=20.0, green_min=40.0)  # fallback

    for r in rows:
        if r.ageMinMonths <= age_months <= r.ageMaxMonths:
            return _Threshold(yellow_min=r.yellowMin, green_min=r.greenMin)

    last = rows[-1]
    return _Threshold(yellow_min=last.yellowMin, green_min=last.greenMin)


def _zone_for(score: float, th: _Threshold) -> Zone:
    if score < th.yellow_min:
        return Zone.ROED
    if score < th.green_min:
        return Zone.GUL
    return Zone.GROEN


def _dist_to_green(score: float, th: _Threshold) -> float:
    return max(0.0, th.green_min - score)


def analyze_single_report(age_months: int, scores: Dict[str, float]) -> PlanResponseModel:
    items: List[PriorityItemModel] = []
    rank: Dict[Zone, int] = {Zone.ROED: 0, Zone.GUL: 1, Zone.GROEN: 2}

    # NB: Analyzer åbner sin egen Session (read-only queries)
    with Session(engine) as session:
        for d in DOMAINS:
            s = float(scores.get(d, 0.0))
            th = _lookup_threshold(session, d, age_months)
            z = _zone_for(s, th)
            dist = _dist_to_green(s, th)

            # Kortsigtet mål: 4..10 point, maks til green_min
            delta = min(10.0, max(4.0, dist / 2.0))
            goal = min(th.green_min, s + delta)

            items.append(
                PriorityItemModel(
                    domain=d,
                    score=round(s, 1),
                    zone=z,
                    distToGreen=round(dist, 1),
                    shortTermGoal=round(goal, 1),
                    tips=RECS.get(d, []),
                )
            )

    items.sort(key=lambda i: (rank[i.zone], -i.distToGreen, i.score))

    recs: List[RecommendationItemModel] = [
        RecommendationItemModel(domain=i.domain, tips=i.tips)
        for i in items
        if i.zone != Zone.GROEN
    ][:3]

    return PlanResponseModel(
        priorityAreas=items,
        recommendations=recs,
        meta={"ageMonths": age_months, "mode": "age_cutoffs"},
    )


# ---------- DB engine ----------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sproki_reports.db")
connect_args: Dict[str, Any] = {
    "check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine: Engine = create_engine(
    DATABASE_URL, echo=False, connect_args=connect_args)


def _seed_default_cutoffs(session: Session) -> None:
    has_any = session.exec(select(Cutoff).limit(1)).first()
    if has_any:
        return

    defaults: List[Cutoff] = []
    for dom in DOMAINS:
        defaults += [
            Cutoff(domain=dom, ageMinMonths=48, ageMaxMonths=59,
                   greenMin=40.0, yellowMin=20.0),
            Cutoff(domain=dom, ageMinMonths=60, ageMaxMonths=71,
                   greenMin=45.0, yellowMin=25.0),
        ]
    for row in defaults:
        session.add(row)
    session.commit()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        _seed_default_cutoffs(s)


# ---------- Upload-mappe ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.abspath(
    os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "..", "uploads")))
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- FastAPI app ----------
app = FastAPI(title="Sproki Report Analyzer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# ---------- Pydantic schemas (request/response) ----------
class Scores(BaseModel):
    sprogforståelse: float
    ordforråd: float
    kommunikativeStrategier: float
    rim: float
    opmærksomhedPåSkrift: float


class ReportIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    age_months: int = PField(ge=0, le=120, alias="ageMonths")
    scores: Scores


class ReportOut(BaseModel):
    id: int
    createdAt: datetime
    ageMonths: int
    scores: Dict[str, float]


class PracticeEventIn(BaseModel):
    childId: str
    domain: str
    exerciseId: str
    outcome: Outcome
    score: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None
    occurredAt: Optional[datetime] = None


class PracticeEventsIn(BaseModel):
    events: List[PracticeEventIn]


# ---------- Routes ----------
@app.get("/", response_model=Dict[str, str])
def root() -> Dict[str, str]:
    return {"message": "Sproki backend kører. Se /health og /docs"}


@app.get("/health", response_model=OkResponse)
def health() -> OkResponse:
    return OkResponse(ok=True)


@app.post("/children/{child_id}", response_model=UpsertChildResponse)
def upsert_child(child_id: str, name: Optional[str] = None) -> UpsertChildResponse:
    with Session(engine) as session:
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id, name=name)
            session.add(c)
        else:
            if name is not None:
                c.name = name
        session.commit()
        return UpsertChildResponse(ok=True, childId=c.id, name=c.name)


@app.post("/children/{child_id}/reports", response_model=CreateReportResponse)
def add_report(child_id: str, payload: ReportIn) -> CreateReportResponse:
    with Session(engine) as session:
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id)
            session.add(c)
            session.commit()

        r = Report(
            childId=child_id,
            ageMonths=payload.age_months,
            sprogforståelse=payload.scores.sprogforståelse,
            ordforråd=payload.scores.ordforråd,
            kommunikativeStrategier=payload.scores.kommunikativeStrategier,
            rim=payload.scores.rim,
            opmærksomhedPåSkrift=payload.scores.opmærksomhedPåSkrift,
        )
        session.add(r)
        session.commit()
        session.refresh(r)
        return CreateReportResponse(ok=True, reportId=int(r.id or 0), createdAt=r.createdAt.isoformat())


@app.get("/children/{child_id}/plan", response_model=PlanResponseModel)
def get_plan(child_id: str) -> PlanResponseModel:
    with Session(engine) as session:
        stmt = select(Report).where(Report.childId ==
                                    child_id).order_by(desc(Report.createdAt))
        r = cast(Optional[Report], session.exec(stmt).first())
        if not r:
            raise HTTPException(status_code=404, detail="No report for child")
        scores: Dict[str, float] = {
            D_SPROGFORSTAELSE: r.sprogforståelse,
            D_ORDFORRAD: r.ordforråd,
            D_KOMM_STRAT: r.kommunikativeStrategier,
            D_RIM: r.rim,
            D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
        }
        return analyze_single_report(r.ageMonths, scores)


@app.post("/children/{child_id}/analyze", response_model=PlanResponseModel)
def analyze_and_store(child_id: str, payload: ReportIn, name: Optional[str] = None) -> PlanResponseModel:
    with Session(engine) as session:
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id, name=name)
            session.add(c)
            session.commit()
        else:
            if name is not None:
                c.name = name

        r = Report(
            childId=child_id,
            ageMonths=payload.age_months,
            sprogforståelse=payload.scores.sprogforståelse,
            ordforråd=payload.scores.ordforråd,
            kommunikativeStrategier=payload.scores.kommunikativeStrategier,
            rim=payload.scores.rim,
            opmærksomhedPåSkrift=payload.scores.opmærksomhedPåSkrift,
        )
        session.add(r)
        session.commit()
        # r.id og r.createdAt er sat efter commit

        scores: Dict[str, float] = {
            D_SPROGFORSTAELSE: r.sprogforståelse,
            D_ORDFORRAD: r.ordforråd,
            D_KOMM_STRAT: r.kommunikativeStrategier,
            D_RIM: r.rim,
            D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
        }
        return analyze_single_report(r.ageMonths, scores)


# ---------- PDF upload & parsing ----------
@app.post("/children/{child_id}/reports/upload", response_model=UploadReportResponse)
async def upload_report(child_id: str, file: UploadFile = File(...)) -> UploadReportResponse:
    try:
        import pdfplumber  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"pdfplumber er ikke installeret i miljøet: {e}",
        ) from e

    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Kun PDF understøttes")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Tom fil")

    safe_name = filename.replace("/", "_").replace("\\", "_")
    stamp = int(datetime.now(timezone.utc).timestamp())
    dest_path = os.path.join(UPLOAD_DIR, f"{child_id}_{stamp}_{safe_name}")
    try:
        async with aiofiles.open(dest_path, "wb") as fh:
            await fh.write(raw)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] Kunne ikke gemme upload: {e}")

    try:
        text = ""
        with pdfplumber.open(BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=422, detail=f"Kunne ikke læse PDF: {e}") from e

    scores = parse_scores_from_text(text)

    EPS = 1e-9
    if all(math.isclose(v, 0.0, abs_tol=EPS) for v in scores.values()):
        raise HTTPException(
            status_code=422,
            detail="Kunne ikke udlede scorer fra PDF. Kontroller at rapporten er tekstbaseret.",
        )

    with Session(engine) as session:
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id)
            session.add(c)
            session.commit()

        r = Report(
            childId=child_id,
            ageMonths=-1,  # ukendt fra PDF – kan sættes senere
            sprogforståelse=scores[D_SPROGFORSTAELSE],
            ordforråd=scores[D_ORDFORRAD],
            kommunikativeStrategier=scores[D_KOMM_STRAT],
            rim=scores[D_RIM],
            opmærksomhedPåSkrift=scores[D_OPM_SKRIFT],
        )
        session.add(r)
        session.commit()
        session.refresh(r)

        plan = analyze_single_report(
            r.ageMonths,
            {
                D_SPROGFORSTAELSE: r.sprogforståelse,
                D_ORDFORRAD: r.ordforråd,
                D_KOMM_STRAT: r.kommunikativeStrategier,
                D_RIM: r.rim,
                D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
            },
        )

    return UploadReportResponse(
        ok=True,
        reportId=int(r.id or 0),
        createdAt=r.createdAt.isoformat(),
        scores=scores,
        plan=plan,
        storedPdfPath=dest_path,
    )


@app.get("/children/{child_id}/reports", response_model=List[ReportOut])
def list_reports(child_id: str) -> List[ReportOut]:
    with Session(engine) as session:
        stmt = select(Report).where(Report.childId ==
                                    child_id).order_by(desc(Report.createdAt))
        rows = cast(List[Report], session.exec(stmt).all())

        result: List[ReportOut] = []
        for r in rows:
            if r.id is None:
                # defensive, men burde ikke ske efter commit
                continue
            result.append(
                ReportOut(
                    id=r.id,
                    createdAt=r.createdAt,
                    ageMonths=r.ageMonths,
                    scores={
                        D_SPROGFORSTAELSE: r.sprogforståelse,
                        D_ORDFORRAD: r.ordforråd,
                        D_KOMM_STRAT: r.kommunikativeStrategier,
                        D_RIM: r.rim,
                        D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
                    },
                )
            )
        return result


# ---------- Practice events endpoint ----------
ALLOWED_OUTCOMES: set[str] = {Outcome.SUCCESS.value, Outcome.FAIL.value}


def _validate_practice_event(e: PracticeEventIn, expected_child_id: str) -> None:
    if e.childId != expected_child_id:
        raise HTTPException(
            status_code=400, detail="childId in body must match path parameter")
    if e.domain not in DOMAINS:
        raise HTTPException(
            status_code=400, detail=f"Unknown domain '{e.domain}'. Must be one of {DOMAINS}")
    if e.outcome.value not in ALLOWED_OUTCOMES:
        raise HTTPException(
            status_code=400, detail="outcome must be 'success' or 'fail'")
    if e.score is not None and not (0.0 <= e.score <= 1.0):
        raise HTTPException(
            status_code=400, detail="score must be between 0.0 and 1.0")


@app.post("/children/{child_id}/practice-events", response_model=PracticeEventsResult)
def add_practice_events(child_id: str, payload: PracticeEventsIn) -> PracticeEventsResult:
    """Modtag batch af øvelseshændelser fra appen."""
    if not payload.events:
        raise HTTPException(status_code=400, detail="No events provided")

    for e in payload.events:
        _validate_practice_event(e, child_id)

    with Session(engine) as session:
        # Sikre barn findes
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id)
            session.add(c)
            session.commit()

        # Indsæt rækker
        now_utc = datetime.now(timezone.utc)
        for e in payload.events:
            session.add(
                PracticeEvent(
                    childId=child_id,
                    domain=e.domain,
                    exerciseId=e.exerciseId,
                    outcome=e.outcome.value,
                    score=e.score,
                    meta=json.dumps(e.meta) if e.meta else None,
                    occurredAt=e.occurredAt or now_utc,
                )
            )
        session.commit()

    return PracticeEventsResult(ok=True, accepted=len(payload.events))
