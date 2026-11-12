"""LangGraph pipeline: triage -> retrieve -> comply -> pdm -> draft -> verify,
with a bounded retry loop from the verifier back to retrieval.

Every node is a STUB that returns plausible structure. Replace the bodies with
real retrieval (BM25 + BGE-M3 + reranker), the AD rules engine, the RUL model
and a local LLM, but keep the graph shape and the retry limit.
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from aerosafe.config import get_settings
from aerosafe.nlp import triage as nlp


class CaseState(TypedDict, total=False):
    text: str
    language: str
    ata: list
    entities: list
    evidence: list          # [{"id": "[1]", "source": "ASRS", "text": "..."}]
    ad_results: list        # [{"id": "AD-2", "status": "needs_review"}]
    rul: dict | None
    draft: list             # [{"text": "...", "cites": ["[1]"]}]
    unsupported: list
    retries: int
    outcome: str            # "awaiting_approval" | "abstained"
    trace: list
    sensor_path: str | None


def _log(state: CaseState, agent: str, msg: str) -> list:
    return [*state.get("trace", []), {"agent": agent, "msg": msg}]


def triage_node(state: CaseState) -> CaseState:
    r = nlp.analyze(state["text"])
    return {"language": r.language, "ata": r.ata, "entities": r.entities,
            "retries": state.get("retries", 0), "trace": _log(state, "triage", f"ATA {r.ata[:1]}")}


def retrieve_node(state: CaseState) -> CaseState:
    # TODO: hybrid search + rerank + graph expansion. Until real retrieval exists,
    # never manufacture a source passage that could be mistaken for evidence.
    ev = []
    return {"evidence": ev, "trace": _log(state, "retrieval", f"{len(ev)} passages (retry {state.get('retries', 0)})")}


def comply_node(state: CaseState) -> CaseState:
    # TODO: parse ADs, apply deterministic applicability rules first.
    return {"ad_results": [], "trace": _log(state, "compliance", "0 directives evaluated")}


def pdm_node(state: CaseState) -> CaseState:
    # TODO: call the RUL model when state["sensor_path"] is set.
    note = "skipped, no sensor file" if not state.get("sensor_path") else "RUL model called"
    return {"rul": None, "trace": _log(state, "pdm", note)}


def draft_node(state: CaseState) -> CaseState:
    # TODO: local LLM writes claims using ONLY the evidence pack.
    # No recommendation can be drafted safely until retrieval and generation exist.
    return {"draft": [], "trace": _log(state, "draft", "skipped: retrieval and drafting are not implemented")}


def verify_node(state: CaseState) -> CaseState:
    # TODO: entailment check of each claim against its cited passage.
    evidence_ids = {e.get("id") for e in state.get("evidence", []) if e.get("id") and e.get("text")}
    # Fail closed while the entailment checker is a stub. A citation alone does not
    # prove that its source supports a claim.
    bad = [
        c.get("text", "")
        for c in state.get("draft", [])
        if not c.get("text") or not c.get("cites") or not set(c["cites"]).issubset(evidence_ids)
    ]
    if not state.get("evidence") or not state.get("draft"):
        bad.append("No validated evidence-backed recommendation is available.")
    else:
        # Citation membership is not entailment. Keep the gate closed until a real
        # claim-to-source verifier replaces this stub.
        bad.append("Claim entailment verification is not implemented.")
    return {"unsupported": bad, "trace": _log(state, "verifier", f"{len(bad)} unsupported claims")}


def bump_retry_node(state: CaseState) -> CaseState:
    return {"retries": state.get("retries", 0) + 1, "trace": _log(state, "verifier", "retrying retrieval")}


def gate_node(state: CaseState) -> CaseState:
    return {"outcome": "awaiting_approval", "trace": _log(state, "gate", "waiting for reviewer")}


def abstain_node(state: CaseState) -> CaseState:
    return {"outcome": "abstained", "trace": _log(state, "verifier", "abstained: insufficient evidence")}


def route_after_verify(state: CaseState) -> str:
    if not state.get("unsupported"):
        return "done"
    return "retry" if state.get("retries", 0) < get_settings().max_retries else "abstain"


def build_graph():
    g = StateGraph(CaseState)
    for name, fn in [("triage", triage_node), ("retrieve", retrieve_node), ("comply", comply_node),
                     ("pdm", pdm_node), ("draft", draft_node), ("verify", verify_node),
                     ("bump_retry", bump_retry_node), ("gate", gate_node), ("abstain", abstain_node)]:
        g.add_node(name, fn)
    g.set_entry_point("triage")
    for a, b in [("triage", "retrieve"), ("retrieve", "comply"), ("comply", "pdm"),
                 ("pdm", "draft"), ("draft", "verify"), ("bump_retry", "retrieve"),
                 ("gate", END), ("abstain", END)]:
        g.add_edge(a, b)
    g.add_conditional_edges("verify", route_after_verify,
                            {"retry": "bump_retry", "abstain": "abstain", "done": "gate"})
    return g.compile()
