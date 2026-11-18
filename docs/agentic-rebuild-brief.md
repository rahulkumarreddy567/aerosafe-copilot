# Agentic rebuild brief

## Confirmed repository facts

- The tracked application is AeroSafe: FastAPI, LangGraph, SQLite case history, local keyword ATA triage,
  an illustrative RUL estimator, an audit hash chain, and a synthetic evaluation fixture.
- The current working tree contains an uncommitted NeuralMech UI redesign. It adds a Three.js CDN,
  anomaly/agent screens, similar-case and action-suggestion endpoints, and case context controls.
- Action suggestions currently come from fixed ATA-score thresholds; they are not model generated.
  The draft UI advertises the AI core as online even without a model health check.
- Product docs have intentionally excluded real directive applicability, aircraft configuration,
  and operational maintenance recommendations.
- The user wants a stronger resume project with real AI agents, a more distinctive 3D interface,
  a complete feature/spec review, and a working local Docker run.
- The user chose to reuse the existing process `OPENAI_API_KEY`. Do not copy it into tracked files or
  display its value. The `.env` file is ignored by Git, but no destination approval has been requested.

## Product direction (inference from the request)

Keep the aviation domain and reposition AeroSafe as an **agentic maintenance investigation workbench**.
It should orchestrate focused intake, source retrieval, analysis, and verification agents around a
human-reviewed case brief. Its value is transparent evidence handling and agent observability, not
an autonomous maintenance decision.

## Proposed build decisions

- Use the OpenAI Agents SDK for a server-owned, bounded agent run, with explicit deterministic tools
  and persisted agent events. Keep the current SQLite case store and FastAPI surface.
- Ground the workflow in operator-uploaded source files and the case library. Every returned claim
  must carry source IDs and quotations; otherwise it is marked unsupported. No invented compliance,
  severity, or maintenance action.
- Keep the existing keyword triage as a baseline. Distinguish local heuristics from live model output
  in labels, status, and evaluation.
- Replace decorative “AI online” claims, duplicate panels, remote Three.js/font dependencies, and
  unused CSS-writing scripts with explicit capability states and a coherent 3D cockpit UI.
- Preserve local Docker operation. The OpenAI key is runtime configuration supplied by the existing
  process environment; do not write a copy to disk without asking the user to confirm its destination.
- Add deterministic tests around tools, evidence citations, refusal/abstention behavior, run states,
  case persistence, and provider-unavailable behavior. Keep live calls opt-in and separately marked.

## Validation boundary

An API-backed agent can improve document search and produce cited case summaries. It cannot establish
aircraft configuration, directive applicability, airworthiness, or approval to perform maintenance.
Those require authoritative operator data and qualified human review, which are outside this rebuild.
