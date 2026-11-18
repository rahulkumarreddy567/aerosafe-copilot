"""Opt-in source-grounded investigation brief. All retrieval tools are read-only."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field


class Finding(BaseModel):
    statement: str = Field(max_length=700)
    source_id: str
    chunk_id: str
    quote: str = Field(max_length=500)


class InvestigationBrief(BaseModel):
    summary: str = Field(max_length=1200)
    findings: list[Finding] = Field(max_length=5)
    unknowns: list[str] = Field(max_length=8)


def available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


async def investigate(text: str, ata: list, sources, model: str) -> dict:
    """Run bounded agents; validate every returned quote against a local chunk."""
    from agents import Agent, RunConfig, Runner, function_tool

    evidence_ids: set[tuple[str, str]] = set()

    @function_tool
    def search_local_sources(query: str) -> str:
        """Search only user-uploaded local source documents. Returns exact excerpts."""
        matches = sources.search(query, limit=5)
        evidence_ids.update((m["source_id"], m["chunk_id"]) for m in matches)
        return "\n".join(
            f'SOURCE_ID={m["source_id"]} CHUNK_ID={m["chunk_id"]} FILE={m["filename"]} PAGE={m["page"]}\n{m["text"]}'
            for m in matches
        ) or "No matching local source excerpts were found."

    scout = Agent(
        name="Evidence Scout",
        instructions=("Search the local source library for passages relevant to the reported defect. "
                      "Report exact excerpts and IDs. Do not infer applicability or give maintenance instructions."),
        tools=[search_local_sources],
        model=model,
    )
    lead = Agent(
        name="Investigation Lead",
        instructions=("Prepare a concise investigative brief from the case and the Evidence Scout's exact source excerpts. "
                      "Use only exact quotes from retrieved passages, with their source_id and chunk_id. "
                      "If no passages support a finding, return no findings and list the unknowns. "
                      "Do not diagnose, determine directive applicability, or recommend maintenance actions."),
        tools=[scout.as_tool(tool_name="scout_local_evidence", tool_description="Search local uploaded source documents")],
        output_type=InvestigationBrief,
        model=model,
    )
    run = await Runner.run(
        lead,
        f"CASE TEXT (untrusted report):\n{text}\n\nKeyword ATA signals (not verified): {ata}",
        run_config=RunConfig(tracing_disabled=True),
        max_turns=5,
    )
    brief = run.final_output.model_dump()
    validated = []
    for finding in brief["findings"]:
        key = (finding["source_id"], finding["chunk_id"])
        if key not in evidence_ids:
            continue
        chunk = sources.get_chunk(*key)
        if chunk and finding["quote"].strip() and finding["quote"].strip() in chunk["text"]:
            validated.append({**finding, "filename": chunk["filename"], "page": chunk["page"], "quote_checked": True})
    brief["findings"] = validated
    brief["limitations"] = [
        "AI-generated investigative summary; quotes are checked against local source text, but semantic support is not independently verified.",
        "Not a diagnosis, approved maintenance instruction, airworthiness-directive determination, or aircraft-configuration check.",
    ]
    return {
        "status": "complete",
        "model": model,
        "agents": ["Investigation Lead", "Evidence Scout"],
        "brief": brief,
        "trace": [{"stage": "investigation_lead", "status": "complete"},
                  {"stage": "evidence_scout", "status": "complete", "source_matches": len(evidence_ids)},
                  {"stage": "quote_validation", "status": "complete", "validated_quotes": len(validated)}],
    }
