from aerosafe.agents.graph import build_graph, route_after_verify, verify_node


def test_pipeline_abstains_until_real_evidence_and_verification_exist():
    out = build_graph().invoke({"text": "Intermittent hydraulic pressure drop on landing gear retraction"})
    assert out["outcome"] == "abstained"
    assert out["retries"] == 2
    assert out["evidence"] == []
    assert out["draft"] == []
    assert out["ata"][0][0] in {"32", "29"}


def test_abstains_after_bounded_retries(monkeypatch):
    monkeypatch.setenv("AEROSAFE_MAX_RETRIES", "2")
    out = build_graph().invoke({"text": "unclear defect"})
    assert out["outcome"] == "abstained"
    assert out["retries"] == 2


def test_citations_alone_cannot_pass_stub_verifier(monkeypatch):
    monkeypatch.setenv("AEROSAFE_MAX_RETRIES", "0")
    state = {
        "evidence": [{"id": "[1]", "source": "fixture", "text": "An arbitrary passage."}],
        "draft": [{"text": "An unrelated claim.", "cites": ["[1]"]}],
    }
    update = verify_node(state)
    merged = {**state, **update}
    assert update["unsupported"]
    assert route_after_verify(merged) == "abstain"
