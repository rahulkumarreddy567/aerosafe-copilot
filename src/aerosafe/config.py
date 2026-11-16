"""Settings read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    audit_path: str
    cases_path: str
    max_retries: int


def get_settings() -> Settings:
    try:
        max_retries = int(os.getenv("AEROSAFE_MAX_RETRIES", "2"))
    except ValueError as exc:
        raise ValueError("AEROSAFE_MAX_RETRIES must be an integer from 0 to 10") from exc
    if not 0 <= max_retries <= 10:
        raise ValueError("AEROSAFE_MAX_RETRIES must be an integer from 0 to 10")

    return Settings(
        whisper_model=os.getenv("AEROSAFE_WHISPER_MODEL", "small").strip() or "small",
        whisper_device=os.getenv("AEROSAFE_WHISPER_DEVICE", "cpu").strip() or "cpu",
        whisper_compute_type=os.getenv("AEROSAFE_WHISPER_COMPUTE", "int8").strip() or "int8",
        audit_path=os.getenv("AEROSAFE_AUDIT_PATH", "data/audit.jsonl").strip() or "data/audit.jsonl",
        cases_path=os.getenv("AEROSAFE_CASES_PATH", "data/cases.sqlite3").strip() or "data/cases.sqlite3",
        max_retries=max_retries,
    )
