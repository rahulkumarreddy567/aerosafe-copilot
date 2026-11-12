"""FastAPI app: voice upload, case analysis, human decision, audit verification."""
import tempfile
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aerosafe.agents.graph import build_graph
from aerosafe.audit.chain import AuditLog
from aerosafe.config import get_settings

@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    AuditLog(settings.audit_path)
    yield


app = FastAPI(title="AeroSafe Copilot", version="0.1.0",
              description="Prototype on public data. Not approved maintenance data.", lifespan=lifespan)
WEB_STATIC = Path(__file__).resolve().parents[1] / "static"
WEB_INDEX = WEB_STATIC / "index.html"
app.mount("/static", StaticFiles(directory=WEB_STATIC), name="static")
CASES: dict[str, dict] = {}
CASES_LOCK = RLock()
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@lru_cache(maxsize=1)
def _graph():
    return build_graph()


def _audit() -> AuditLog:
    return AuditLog(get_settings().audit_path)


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10_000)

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
    return {"status": "ok"}


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
            from aerosafe.speech.whisper_service import transcribe

            t = transcribe(tmp.name)
        except ImportError as exc:  # optional faster-whisper dependency
            raise HTTPException(501, "Install the speech extra: pip install -e '.[speech]'") from exc
    return {"text": t.text, "language": t.language, "language_probability": t.language_probability}


@app.post("/cases")
def create_case(req: CaseRequest):
    case_id = f"case-{uuid.uuid4().hex}"
    result = _graph().invoke({"text": req.text})
    audit = _audit()
    for event in result.get("trace", []):
        audit.append(event["agent"], event["msg"], {"case": case_id})
    audit.append("system", "case_analyzed",
                 {"case": case_id, "outcome": result["outcome"], "retries": result["retries"]})
    with CASES_LOCK:
        CASES[case_id] = result
    return {"case_id": case_id, **result}


@app.get("/cases")
def list_cases():
    with CASES_LOCK:
        return [
            {
                "case_id": case_id,
                "outcome": {"approve": "approved", "reject": "rejected"}.get(
                    case.get("decision"), case.get("outcome", "unknown")
                ),
                "language": case.get("language"),
                "ata": case.get("ata", []),
            }
            for case_id, case in reversed(list(CASES.items()))
        ]


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    with CASES_LOCK:
        if case_id not in CASES:
            raise HTTPException(404, "unknown case")
        return CASES[case_id]


@app.post("/cases/{case_id}/decision")
def decide(case_id: str, d: Decision):
    with CASES_LOCK:
        case = CASES.get(case_id)
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
