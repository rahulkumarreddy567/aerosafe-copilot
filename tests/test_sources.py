from fastapi.testclient import TestClient
import pytest
import asyncio
from types import SimpleNamespace

from aerosafe.api.main import app
from aerosafe.sources import MAX_SOURCE_BYTES, SourceStore, parse_source


def test_source_store_exact_chunks_search_and_delete(tmp_path):
    content = b"Hydraulic pump inspection note. Confirm pressure trend and document leakage observations."
    kind, pages = parse_source("maintenance-note.txt", content)
    store = SourceStore(str(tmp_path / "source.sqlite3"))
    source = store.add("maintenance-note.txt", kind, content, pages)
    found = store.search("hydraulic pressure", limit=3)
    assert found and found[0]["source_id"] == source["source_id"]
    chunk = store.get_chunk(source["source_id"], found[0]["chunk_id"])
    assert "hydraulic" in chunk["text"].lower()
    assert store.delete(source["source_id"])
    assert store.get_chunk(source["source_id"], found[0]["chunk_id"]) is None


def test_source_parse_limits_and_invalid_types():
    with pytest.raises(ValueError, match="PDF, TXT"):
        parse_source("payload.exe", b"data")
    with pytest.raises(ValueError, match="UTF-8"):
        parse_source("bad.txt", b"\xff")
    with pytest.raises(ValueError, match="empty"):
        parse_source("empty.txt", b"")
    with pytest.raises(ValueError, match="250,000"):
        parse_source("large.txt", b"x" * 250_001)
    assert MAX_SOURCE_BYTES == 8 * 1024 * 1024


def test_source_api_upload_list_delete_and_bounds(tmp_path, monkeypatch):
    monkeypatch.setenv("AEROSAFE_SOURCES_PATH", str(tmp_path / "source.sqlite3"))
    c = TestClient(app)
    added = c.post("/sources", files={"file": ("note.md", b"Hydraulic pump service note.", "text/markdown")})
    assert added.status_code == 200
    item = added.json()
    assert item["filename"] == "note.md" and item["chunk_count"] == 1
    assert c.get("/sources").json()[0]["source_id"] == item["source_id"]
    assert c.delete(f"/sources/{item['source_id']}").json()["deleted"]
    assert c.delete(f"/sources/{item['source_id']}").status_code == 404
    assert c.post("/sources", files={"file": ("script.py", b"bad", "text/plain")}).status_code == 422


def test_agentic_brief_keeps_only_quotes_from_retrieved_chunks(tmp_path, monkeypatch):
    import agents
    from aerosafe.agentic import investigate

    store = SourceStore(str(tmp_path / "source.sqlite3"))
    raw = b"Synthetic note: record the observed hydraulic pressure reading."
    kind, pages = parse_source("synthetic.txt", raw)
    source = store.add("synthetic.txt", kind, raw, pages)
    chunk = store.search("hydraulic pressure", limit=1)[0]
    good = {"statement": "The note says to record a reading.", "source_id": source["source_id"],
            "chunk_id": chunk["chunk_id"], "quote": "record the observed hydraulic pressure reading"}
    bad = {**good, "statement": "Unsupported statement.", "quote": "the source says the part is unserviceable"}

    class FakeAgent:
        scout_tool = None
        def __init__(self, name, **kwargs):
            if name == "Evidence Scout":
                FakeAgent.scout_tool = kwargs["tools"][0]
            self.name = name
        def as_tool(self, **kwargs):
            return self

    class FakeRunner:
        @staticmethod
        async def run(*args, **kwargs):
            FakeAgent.scout_tool("hydraulic pressure")
            output = SimpleNamespace(model_dump=lambda: {"summary": "Synthetic brief", "findings": [good, bad], "unknowns": []})
            return SimpleNamespace(final_output=output)

    monkeypatch.setattr(agents, "Agent", FakeAgent)
    monkeypatch.setattr(agents, "Runner", FakeRunner)
    monkeypatch.setattr(agents, "RunConfig", lambda **kwargs: kwargs)
    monkeypatch.setattr(agents, "function_tool", lambda fn: fn)
    result = asyncio.run(investigate("synthetic defect", [], store, "test-model"))
    assert result["status"] == "complete"
    assert len(result["brief"]["findings"]) == 1
    assert result["brief"]["findings"][0]["quote_checked"] is True
    assert result["trace"][-1]["validated_quotes"] == 1
