from __future__ import annotations

from typing import Dict, Optional, List
from datetime import datetime
from io import BytesIO
import os
import math

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PField, ConfigDict
from sqlmodel import SQLModel, Field, Session, create_engine, select

# ---------- Domæne-konstanter ----------
D_SPROGFORSTAELSE = "sprogforståelse"
D_ORDFORRAD = "ordforråd"
D_KOMM_STRAT = "kommunikativeStrategier"
D_RIM = "rim"
D_OPM_SKRIFT = "opmærksomhedPåSkrift"

DOMAINS = [
    D_SPROGFORSTAELSE,
    D_ORDFORRAD,
    D_KOMM_STRAT,
    D_RIM,
    D_OPM_SKRIFT,
]

RECS: Dict[str, list[str]] = {
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

# ---------- Tærskler/zoner ----------
class Thresholds:
    red_upper = 20.0
    yellow_upper = 40.0
    green_lower = 40.0

    @staticmethod
    def zone(score: float) -> str:
        if score < Thresholds.red_upper:
            return "rød"
        if score < Thresholds.yellow_upper:
            return "gul"
        return "grøn"

    @staticmethod
    def dist_to_green(score: float) -> float:
        return max(0.0, Thresholds.green_lower - score)


def analyze_single_report(age_months: int, scores: Dict[str, float]) -> Dict:
    items = []
    for d in DOMAINS:
        s = float(scores.get(d, 0.0))
        z = Thresholds.zone(s)
        dist = Thresholds.dist_to_green(s)
        delta = min(10.0, max(4.0, dist / 2))  # 4..10 point
        goal = min(Thresholds.green_lower, s + delta)
        items.append(
            {
                "domain": d,
                "score": round(s, 1),
                "zone": z,
                "distToGreen": round(dist, 1),
                "shortTermGoal": round(goal, 1),
                "tips": RECS.get(d, []),
            }
        )

    rank = {"rød": 0, "gul": 1, "grøn": 2}
    items.sort(key=lambda x: (rank[x["zone"]], -x["distToGreen"], x["score"]))

    recs = [
        {"domain": i["domain"], "tips": i["tips"]}
        for i in items
        if i["zone"] != "grøn"
    ][:3]

    return {
        "priorityAreas": items,
        "recommendations": recs,
        "meta": {"ageMonths": age_months, "mode": "deterministic"},
    }


# ---------- DB modeller ----------
class Child(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    childId: str = Field(index=True)
    ageMonths: int
    sprogforståelse: float
    ordforråd: float
    kommunikativeStrategier: float
    rim: float
    opmærksomhedPåSkrift: float
    createdAt: datetime = Field(default_factory=datetime.utcnow)


# ---------- DB engine (Render/Local) ----------
# Brug DATABASE_URL hvis sat (Render), ellers lokal SQLite-fil.
# check_same_thread=False for SQLite i webservere med flere tråde.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sproki_reports.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


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


# ---------- Pydantic schemas ----------
class Scores(BaseModel):
    sprogforståelse: float
    ordforråd: float
    kommunikativeStrategier: float
    rim: float
    opmærksomhedPåSkrift: float


class ReportIn(BaseModel):
    # JSON: ageMonths (alias) → Python: age_months
    age_months: int = PField(ge=0, le=120, alias="ageMonths")
    scores: Scores
    model_config = ConfigDict(populate_by_name=True)


class ReportOut(BaseModel):
    id: int
    createdAt: datetime
    ageMonths: int
    scores: Dict[str, float]


# ---------- Basis-ruter ----------
@app.get("/")
def root():
    return {"message": "Sproki backend kører. Se /health og /docs"}


@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


# ---------- Child & Report CRUD ----------
@app.post("/children/{child_id}")
def upsert_child(child_id: str, name: Optional[str] = None) -> Dict:
    with Session(engine) as session:
        c = session.get(Child, child_id)
        if not c:
            c = Child(id=child_id, name=name)
            session.add(c)
        else:
            if name is not None:
                c.name = name
        session.commit()
        return {"ok": True, "childId": c.id, "name": c.name}


@app.post("/children/{child_id}/reports")
def add_report(child_id: str, payload: ReportIn) -> Dict:
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
        return {"ok": True, "reportId": r.id, "createdAt": r.createdAt.isoformat()}


@app.get("/children/{child_id}/plan")
def get_plan(child_id: str) -> Dict:
    with Session(engine) as session:
        stmt = (
            select(Report)
            .where(Report.childId == child_id)
            .order_by(Report.createdAt.desc())
        )
        r = session.exec(stmt).first()
        if not r:
            raise HTTPException(status_code=404, detail="No report for child")
        scores = {
            D_SPROGFORSTAELSE: r.sprogforståelse,
            D_ORDFORRAD: r.ordforråd,
            D_KOMM_STRAT: r.kommunikativeStrategier,
            D_RIM: r.rim,
            D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
        }
        return analyze_single_report(r.ageMonths, scores)


@app.post("/children/{child_id}/analyze")
def analyze_and_store(
    child_id: str, payload: ReportIn, name: Optional[str] = None
) -> Dict:
    """Upsert barn, gem rapport og returnér plan i ét kald."""
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

        scores = {
            D_SPROGFORSTAELSE: r.sprogforståelse,
            D_ORDFORRAD: r.ordforråd,
            D_KOMM_STRAT: r.kommunikativeStrategier,
            D_RIM: r.rim,
            D_OPM_SKRIFT: r.opmærksomhedPåSkrift,
        }
        return analyze_single_report(r.ageMonths, scores)


# ---------- Historik & enkeltrapporter ----------
@app.get("/children/{child_id}/reports", response_model=List[ReportOut])
def list_reports(child_id: str):
    with Session(engine) as session:
        rows = session.exec(
            select(Report)
            .where(Report.childId == child_id)
            .order_by(Report.createdAt.desc())
        ).all()
        return [
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
            for r in rows
        ]


@app.get("/children/{child_id}/reports/{report_id}", response_model=ReportOut)
def get_report(child_id: str, report_id: int):
    with Session(engine) as session:
        r = session.get(Report, report_id)
        if not r or r.childId != child_id:
            raise HTTPException(status_code=404, detail="Report not found")
        return ReportOut(
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


# ---------- PDF upload & parsing ----------
from .pdf_parser import parse_scores_from_text


@app.post("/children/{child_id}/reports/upload")
async def upload_report(child_id: str, file: UploadFile = File(...)) -> Dict:
    # Lazy import, så resten af API'et virker uden pdfplumber ved normal drift
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pdfplumber er ikke installeret i miljøet. Kør: pip install pdfplumber",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Kun PDF understøttes")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Tom fil")

    try:
        text = ""
        with pdfplumber.open(BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Kunne ikke læse PDF: {e}")

    scores = parse_scores_from_text(text)

    # Float-sikker “alle ~nul”-kontrol (ingen direkte lighed med floats)
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

    return {
        "ok": True,
        "reportId": r.id,
        "createdAt": r.createdAt.isoformat(),
        "scores": scores,
        "plan": plan,
    }
