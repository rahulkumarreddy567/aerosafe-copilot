from fastapi.testclient import TestClient
import pytest

from aerosafe.api.main import app


def test_case_flow_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    page = c.get("/")
    assert page.status_code == 200
    assert "New case" in page.text
    assert "Audit log" in page.text
    response = c.post("/cases", json={"text": "hydraulic pressure drop on landing gear retraction"})
    assert response.status_code == 200
    r = response.json()
    assert r["outcome"] == "abstained"
    assert r["evidence"] == []
    assert r["draft"] == []
    assert c.get(f"/cases/{r['case_id']}").json()["outcome"] == "abstained"
    assert c.get("/audit/verify").json() == {"intact": True, "first_bad_index": None}


def test_abstained_case_cannot_be_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    r = c.post("/cases", json={"text": "unclear"}).json()
    assert r["outcome"] == "abstained"
    assert c.post(f"/cases/{r['case_id']}/decision", json={"decision": "approve"}).status_code == 409


def test_rejects_invalid_or_blank_case_and_decision_values():
    c = TestClient(app)
    assert c.post("/cases", json={"text": "   "}).status_code == 422
    assert c.post("/cases", json={"text": "defect", "unexpected": True}).status_code == 422
    assert c.post("/cases/case-unknown/decision", json={"decision": "maybe"}).status_code == 422


def test_case_decision_is_one_time_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    # Exercise the decision lifecycle against an explicitly mocked safe gate.
    from aerosafe.api import main

    case_id = "case-reviewable"
    main.CASES[case_id] = {"outcome": "awaiting_approval"}
    first = c.post(f"/cases/{case_id}/decision", json={"decision": "reject"})
    second = c.post(f"/cases/{case_id}/decision", json={"decision": "approve"})
    assert first.status_code == 200
    assert first.json()["decision"] == "reject"
    assert second.status_code == 409
    assert main.CASES[case_id]["decision"] == "reject"
    del main.CASES[case_id]


def test_transcription_reports_missing_optional_dependency(monkeypatch):
    from aerosafe.speech import whisper_service

    def missing_extra(*args, **kwargs):
        raise ImportError("faster-whisper is not installed")

    monkeypatch.setattr(whisper_service, "transcribe", missing_extra)
    c = TestClient(app)
    response = c.post("/transcribe", files={"file": ("clip.wav", b"audio data", "audio/wav")})
    assert response.status_code == 501


def test_transcription_rejects_oversize_upload(monkeypatch):
    from aerosafe.api import main

    monkeypatch.setattr(main, "MAX_AUDIO_BYTES", 4)
    c = TestClient(app)
    response = c.post("/transcribe", files={"file": ("clip.wav", b"12345", "audio/wav")})
    assert response.status_code == 413


def test_transcription_reports_invalid_audio_as_client_error(monkeypatch):
    from aerosafe.speech import whisper_service
    from aerosafe.speech.whisper_service import InvalidAudioError

    def invalid_audio(*args, **kwargs):
        raise InvalidAudioError("The uploaded file is not valid or supported audio.")

    monkeypatch.setattr(whisper_service, "transcribe", invalid_audio)
    c = TestClient(app)
    response = c.post("/transcribe", files={"file": ("clip.bin", b"not audio", "application/octet-stream")})
    assert response.status_code == 422
    assert response.json()["detail"] == "The uploaded file is not valid or supported audio."


def test_invalid_runtime_configuration_fails_at_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_MAX_RETRIES", "not-a-number")
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    with pytest.raises(ValueError, match="AEROSAFE_MAX_RETRIES"):
        with TestClient(app):
            pass
