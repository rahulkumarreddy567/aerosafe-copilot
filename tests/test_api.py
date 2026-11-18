from fastapi.testclient import TestClient
import pytest

from aerosafe.api.main import app


@pytest.fixture(autouse=True)
def isolate_local_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("AEROSAFE_CASES_PATH", str(tmp_path / "cases.sqlite3"))
    monkeypatch.setenv("AEROSAFE_SOURCES_PATH", str(tmp_path / "sources.sqlite3"))


def test_case_flow_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    health = c.get("/health").json()
    assert health["status"] == "ok"
    assert isinstance(health["agentic_configured"], bool)
    assert health["source_count"] == 0
    page = c.get("/")
    assert page.status_code == 200
    assert "NeuralMech" in page.text
    assert "Evidence-grounded investigation workbench" in page.text
    assert "Run AI investigation" in page.text
    assert "data-view=\"sources\"" in page.text
    assert "three.min.js" not in page.text
    response = c.post("/cases", json={"text": "hydraulic pressure drop on landing gear retraction"})
    assert response.status_code == 200
    r = response.json()
    assert r["outcome"] == "abstained"
    assert r["evidence"] == []
    assert r["draft"] == []
    assert r["signals"]
    assert c.get(f"/cases/{r['case_id']}").json()["outcome"] == "abstained"
    assert c.get("/audit/verify").json() == {"intact": True, "first_bad_index": None}
    assert c.get(f"/cases/{r['case_id']}/suggest").status_code == 404


def test_case_context_is_saved_searchable_and_not_used_as_triage_input():
    c = TestClient(app)
    response = c.post("/cases", json={
        "text": "hydraulic pressure drop during landing gear retraction",
        "aircraft_context": {
            "aircraft_model": " A320 ", "aircraft_serial": " MSN-2048 ",
            "component": "Hydraulic pump", "part_number": "PN-42", "component_serial": "SN-9",
        },
    })
    assert response.status_code == 200
    case = response.json()
    assert case["aircraft_context"] == {
        "source": "user_supplied", "verified": False,
        "fields": {
            "aircraft_model": "A320", "aircraft_serial": "MSN-2048",
            "component": "Hydraulic pump", "part_number": "PN-42", "component_serial": "SN-9",
        },
    }
    assert c.get(f"/cases/{case['case_id']}").json()["aircraft_context"] == case["aircraft_context"]
    assert c.get("/cases?q=msn-2048").json()[0]["case_id"] == case["case_id"]
    assert c.get("/cases?q=pn-42").json()[0]["aircraft_context"] == case["aircraft_context"]
    assert case["ata"] == c.post("/cases", json={"text": "hydraulic pressure drop during landing gear retraction"}).json()["ata"]


def test_case_context_rejects_unknown_fields_and_oversize_values():
    c = TestClient(app)
    assert c.post("/cases", json={"text": "defect", "aircraft_context": {"unknown": "x"}}).status_code == 422
    assert c.post("/cases", json={"text": "defect", "aircraft_context": {"part_number": "x" * 101}}).status_code == 422


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


def test_agentic_mode_without_key_saves_baseline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = TestClient(app)
    response = c.post("/cases", json={"text": "hydraulic pressure report", "mode": "agentic"})
    assert response.status_code == 200
    case = response.json()
    assert case["agentic"]["status"] == "unavailable"
    assert c.get(f"/cases/{case['case_id']}").json()["agentic"]["status"] == "unavailable"


def test_invalid_provider_key_is_reported_without_losing_baseline(monkeypatch):
    from aerosafe.api import main
    class AuthenticationError(Exception):
        pass
    async def reject_key(*args, **kwargs):
        raise AuthenticationError("credential details must not be returned")
    monkeypatch.setattr(main.agentic, "available", lambda: True)
    monkeypatch.setattr(main.agentic, "investigate", reject_key)
    c = TestClient(app)
    response = c.post("/cases", json={"text": "hydraulic pressure report", "mode": "agentic"})
    case = response.json()
    assert response.status_code == 200
    assert case["agentic"]["status"] == "failed"
    assert "invalid_api_key" in case["agentic"]["message"]
    assert "credential details" not in case["agentic"]["message"]
    assert c.get(f"/cases/{case['case_id']}").json()["signals"]


def test_case_decision_is_one_time_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    # Exercise the decision lifecycle against an explicitly mocked safe gate.
    from aerosafe.api import main

    case_id = "case-reviewable"
    main._case_store().save(case_id, {"outcome": "awaiting_approval"}, "2026-01-01T00:00:00+00:00")
    first = c.post(f"/cases/{case_id}/decision", json={"decision": "reject"})
    second = c.post(f"/cases/{case_id}/decision", json={"decision": "approve"})
    assert first.status_code == 200
    assert first.json()["decision"] == "reject"
    assert second.status_code == 409
    assert main._case_store().get(case_id)["decision"] == "reject"


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


def test_case_graph_is_built_from_real_triage_signals(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    c = TestClient(app)
    created = c.post("/cases", json={"text": "Hydraulic pressure drop during landing gear retraction"}).json()
    response = c.get(f"/cases/{created['case_id']}/graph")
    assert response.status_code == 200
    graph = response.json()
    assert graph["source"] == "local_keyword_triage"
    assert {node["kind"] for node in graph["nodes"]} >= {"case", "ata", "symptom", "component", "phase"}
    assert graph["edges"]
    assert "No external reports" in graph["limitations"]
    assert c.get("/cases/unknown/graph").status_code == 404


def test_case_history_persists_and_supports_search_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_CASES_PATH", str(tmp_path / "durable.sqlite3"))
    with TestClient(app) as first_client:
        created = first_client.post("/cases", json={"text": "Hydraulic pressure drop on landing gear"}).json()
        case_id = created["case_id"]
        assert first_client.get("/cases?q=hydraulic&ata=32").json()[0]["case_id"] == case_id
        assert first_client.get("/cases?outcome=approved").json() == []

    # A fresh app lifespan reopens the same local database, like a service restart.
    with TestClient(app) as restarted_client:
        restored = restarted_client.get(f"/cases/{case_id}")
        assert restored.status_code == 200
        assert restored.json()["created_at"] == created["created_at"]
        assert restarted_client.get("/cases?q=landing").json()[0]["case_id"] == case_id


def test_case_paging_is_bounded_and_deterministic(tmp_path, monkeypatch):
    from aerosafe.api import main

    store = main._case_store()
    for index in range(53):
        case_id = f"case-page-{index:03d}"
        store.save(case_id, {"text": f"case {index}", "outcome": "abstained", "ata": []}, f"2026-01-01T00:00:{index:02d}+00:00")
    c = TestClient(app)
    first = c.get("/cases?limit=50")
    second = c.get("/cases?limit=50&offset=50")
    assert first.status_code == second.status_code == 200
    assert len(first.json()) == 50
    assert len(second.json()) == 3
    assert c.get("/cases?limit=101").status_code == 422


def test_rul_csv_endpoint_and_evaluation_endpoints():
    c = TestClient(app)
    response = c.post(
        "/rul/analyze?threshold=0.2",
        files={"file": ("sensor.csv", b"cycle,health_index\n0,1\n10,0.8\n20,0.6\n", "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["estimate_cycles"] == 20
    assert c.post(
        "/rul/analyze",
        files={"file": ("bad.csv", b"cycle,temperature\n0,1\n1,2\n2,3\n", "text/csv")},
    ).status_code == 422

    evaluation = c.get("/evaluation").json()
    assert evaluation["sample_count"] == 14
    assert evaluation["accuracy"] == 1
    assert evaluation["macro_f1"] == 1
    assert evaluation["top3_accuracy"] == 1
    assert sum(map(sum, evaluation["confusion_matrix"]["rows"])) == evaluation["sample_count"]
    assert "synthetic" in evaluation["warning"].lower()
    dataset = c.get("/evaluation/data")
    assert dataset.status_code == 200
    assert "expected_ata" in dataset.text
