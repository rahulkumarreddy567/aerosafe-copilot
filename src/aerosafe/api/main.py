"""FastAPI app: voice upload, case analysis, human decision, audit verification."""
import tempfile
import uuid
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aerosafe.agents.graph import build_graph
from aerosafe.agents.case_graph import build_case_graph
from aerosafe.audit.chain import AuditLog
from aerosafe.case_store import CaseStore
from aerosafe.config import get_settings
from aerosafe.evaluation import EVAL_CSV, evaluate_ata_baseline
from aerosafe.sources import MAX_SOURCE_BYTES, SourceStore, parse_source
from aerosafe import agentic
from aerosafe.rul import MAX_SENSOR_CSV_BYTES, SensorCsvError, estimate_rul

@asynccontextmanager
async def lifespan(_: FastAPI):
    global CASE_STORE, CASE_STORE_PATH
    settings = get_settings()
    AuditLog(settings.audit_path)
    CASE_STORE = CaseStore(settings.cases_path)
    CASE_STORE_PATH = settings.cases_path
    SourceStore(settings.sources_path)
    yield


app = FastAPI(title="NeuralMech Investigation Workbench", version="0.2.0",
              description="Agentic, source-grounded aviation investigation prototype. Not maintenance guidance.", lifespan=lifespan)
WEB_STATIC = Path(__file__).resolve().parents[1] / "static"
WEB_INDEX = WEB_STATIC / "index.html"
app.mount("/static", StaticFiles(directory=WEB_STATIC), name="static")
CASE_STORE: CaseStore | None = None
CASE_STORE_PATH: str | None = None
CASES_LOCK = RLock()
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_SENSOR_UPLOAD_BYTES = MAX_SENSOR_CSV_BYTES


@lru_cache(maxsize=1)
def _graph():
    return build_graph()


def _audit() -> AuditLog:
    return AuditLog(get_settings().audit_path)


def _case_store() -> CaseStore:
    global CASE_STORE, CASE_STORE_PATH
    path = get_settings().cases_path
    if CASE_STORE is None or CASE_STORE_PATH != path:
        with CASES_LOCK:
            if CASE_STORE is None or CASE_STORE_PATH != path:
                CASE_STORE = CaseStore(path)
                CASE_STORE_PATH = path
    return CASE_STORE


class AircraftContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aircraft_model: str | None = Field(default=None, max_length=100)
    aircraft_serial: str | None = Field(default=None, max_length=100)
    component: str | None = Field(default=None, max_length=100)
    part_number: str | None = Field(default=None, max_length=100)
    component_serial: str | None = Field(default=None, max_length=100)

    @field_validator("aircraft_model", "aircraft_serial", "component", "part_number", "component_serial")
    @classmethod
    def trim_empty_context(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10_000)
    mode: Literal["baseline", "agentic"] = "baseline"
    aircraft_context: AircraftContext = Field(default_factory=AircraftContext)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    reviewer: str = Field(default="reviewer", min_length=1, max_length=200)
    note: str = Field(default="", max_length=2_000)

    @field_validator("reviewer")
    @classmethod
    def reviewer_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reviewer must not be blank")
        return value


@app.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "agentic_configured": agentic.available(), "agent_model": settings.agent_model,
            "source_count": _source_store().count()}


def _source_store() -> SourceStore:
    settings = get_settings()
    return SourceStore(settings.sources_path)


@app.get("/", include_in_schema=False)
def website():
    return FileResponse(WEB_INDEX, media_type="text/html")


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile):
    """Whisper speech-to-text. Needs the optional `speech` extra."""
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    if not audio:
        raise HTTPException(400, "Audio file is empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio file exceeds the 25 MiB limit")
    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp:
        tmp.write(audio)
        tmp.flush()
        try:
            from aerosafe.speech.whisper_service import InvalidAudioError, transcribe

            t = transcribe(tmp.name)
        except ImportError as exc:  # optional faster-whisper dependency
            raise HTTPException(501, "Install the speech extra: pip install -e '.[speech]'") from exc
        except InvalidAudioError as exc:
            raise HTTPException(422, str(exc)) from exc
    return {"text": t.text, "language": t.language, "language_probability": t.language_probability}


@app.post("/cases")
async def create_case(req: CaseRequest):
    case_id = f"case-{uuid.uuid4().hex}"
    result = _graph().invoke({"text": req.text})
    context_fields = req.aircraft_context.model_dump(exclude_none=True)
    if context_fields:
        result["aircraft_context"] = {"source": "user_supplied", "verified": False, "fields": context_fields}
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    result.update({"case_id": case_id, "created_at": created_at})
    audit = _audit()
    for event in result.get("trace", []):
        audit.append(event["agent"], event["msg"], {"case": case_id})
    audit.append("system", "case_analyzed",
                 {"case": case_id, "outcome": result["outcome"], "retries": result["retries"]})
    try:
        _case_store().save(case_id, result, created_at)
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(500, "Could not save the case to local storage") from exc
    if req.mode == "agentic":
        if not agentic.available():
            result["agentic"] = {"status": "unavailable", "message": "OPENAI_API_KEY is not configured; baseline result was saved."}
        else:
            try:
                result["agentic"] = await agentic.investigate(req.text, result.get("ata", []), _source_store(), get_settings().agent_model)
            except Exception as exc:
                # Store only a broad error class; never persist prompts, response bodies, or credentials.
                auth_error = type(exc).__name__ == "AuthenticationError"
                message = ("OpenAI rejected the configured key (401 invalid_api_key). Replace it with a valid API key; local baseline remains available."
                           if auth_error else "Agent run failed; local keyword baseline remains available.")
                result["agentic"] = {"status": "failed", "error_type": type(exc).__name__, "message": message}
            for stage in result["agentic"].get("trace", []):
                audit.append("agentic", stage["stage"], {"case": case_id, "status": stage["status"]})
        _case_store().save(case_id, result, created_at)
    return result


@app.get("/cases")
def list_cases(
    q: str = Query(default="", max_length=200),
    outcome: Literal["abstained", "awaiting_approval", "approved", "rejected"] | None = None,
    ata: str = Query(default="", pattern=r"^$|^\d{2}$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return _case_store().list(query=q, outcome=outcome or "", ata=ata, limit=limit, offset=offset)


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    case = _case_store().get(case_id)
    if case is None:
        raise HTTPException(404, "unknown case")
    return case


@app.get("/cases/{case_id}/graph")
def case_graph(case_id: str):
    case = _case_store().get(case_id)
    if not case:
        raise HTTPException(404, "unknown case")
    return build_case_graph(case_id, case)


@app.post("/rul/analyze")
async def analyze_rul(file: UploadFile, threshold: float = Query(default=0.2)):
    contents = await file.read(MAX_SENSOR_UPLOAD_BYTES + 1)
    if len(contents) > MAX_SENSOR_UPLOAD_BYTES:
        raise HTTPException(413, "The CSV file exceeds the 1 MB limit.")
    try:
        return estimate_rul(contents, threshold)
    except SensorCsvError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/sources")
def list_sources():
    return _source_store().list()


@app.post("/sources")
async def upload_source(file: UploadFile):
    raw = await file.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise HTTPException(413, "Source file exceeds the 8 MiB limit.")
    try:
        content_type, pages = parse_source(file.filename or "source.txt", raw)
        return _source_store().add(file.filename or "source.txt", content_type, raw, pages)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/sources/{source_id}")
def delete_source(source_id: str):
    if not _source_store().delete(source_id):
        raise HTTPException(404, "unknown source")
    return {"deleted": True, "source_id": source_id}


@app.get("/cases/{case_id}/similar")
def similar_cases(case_id: str, limit: int = Query(default=5, ge=1, le=20)):
    """Find cases with overlapping ATA rankings."""
    case = _case_store().get(case_id)
    if case is None:
        raise HTTPException(404, "unknown case")
    ata_codes = [code for code, _, _ in case.get("ata", [])]
    if not ata_codes:
        return {"case_id": case_id, "similar": [], "note": "No ATA match to compare"}
    results = []
    for code in ata_codes[:2]:
        page = _case_store().list(ata=code, limit=limit + 1)
        for item in page:
            if item["case_id"] != case_id and not any(r["case_id"] == item["case_id"] for r in results):
                results.append(item)
    return {"case_id": case_id, "similar": results[:limit], "matched_on": ata_codes[:2]}

@app.get("/evaluation")
def evaluation():
    return evaluate_ata_baseline()


@app.get("/evaluation/data", include_in_schema=False)
def evaluation_data():
    from aerosafe.evaluation import _find_eval_csv
    csv_path = EVAL_CSV if EVAL_CSV.is_file() else _find_eval_csv()
    if not csv_path.is_file():
        raise HTTPException(404, "Evaluation data file is unavailable")
    return FileResponse(csv_path, media_type="text/csv", filename="ata_smoke.csv")


@app.post("/cases/{case_id}/decision")
def decide(case_id: str, d: Decision):
    with CASES_LOCK:
        case = _case_store().get(case_id)
        if not case:
            raise HTTPException(404, "unknown case")
        if case["outcome"] != "awaiting_approval":
            raise HTTPException(409, "case is not awaiting a reviewer decision")
        if case.get("decision"):
            raise HTTPException(409, "case already has a reviewer decision")
        rec = _audit().append(d.reviewer, f"decision_{d.decision}", {"case": case_id, "note": d.note})
        case["decision"] = d.decision
        case["reviewer"] = d.reviewer
        case["reviewer_note"] = d.note
        _case_store().save(case_id, case, case.get("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds")))
        return {"logged_hash": rec["hash"], "decision": d.decision}


@app.get("/audit/verify")
def verify_audit():
    ok, bad = _audit().verify()
    return {"intact": ok, "first_bad_index": bad}


@app.get("/audit/records")
def audit_records():
    audit = _audit()
    ok, bad = audit.verify()
    if not ok:
        return {"intact": False, "first_bad_index": bad, "records": []}
    records = audit.records()
    return {
        "intact": True,
        "first_bad_index": None,
        "records": [
            {key: record.get(key) for key in ("index", "ts", "actor", "action", "prev_hash", "hash")}
            for record in records
        ],
    }
