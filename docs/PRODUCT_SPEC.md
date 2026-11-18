# AeroSafe product specification

**Document status:** implementation baseline for the local portfolio prototype  
**Audience:** maintainers, reviewers, and demo users  
**Last updated:** 2026-11-16

## Product goal

Provide a local, inspectable workspace for turning a free-text maintenance report into a saved
case, showing transparent keyword triage signals, and examining the prototype pipeline. The product
is a software engineering and evaluation showcase. It is not an aircraft maintenance decision
system.

## Users and primary workflow

1. A demo user enters or transcribes a reported defect.
2. AeroSafe saves the report, detected language, ATA keyword ranking, extracted keyword entities,
   pipeline trace, abstention state, and timestamp to the local case database.
3. The user inspects why each ATA category ranked, explores the case-local relationship graph,
   searches or filters the case library, and optionally downloads a JSON case artifact.
4. The user can explore a separately uploaded normalized sensor CSV with an explicitly illustrative
   linear trend estimator, verify the append-only hash-chained audit log, and inspect smoke-set
   evaluation results.

No automated recommendation is generated. No maintenance approval is enabled from normal pipeline
results. An empty retrieval or directive view means “not evaluated,” never “no evidence exists” or
“not applicable.”

## Feature contract

| Area | Working behavior | Not represented |
|---|---|---|
| Triage | English/French hint, ATA keyword ranking, matched terms, basic symptom/component/phase tags | Calibrated probability, fault diagnosis, severity, aircraft-specific result |
| Case library | Local SQLite persistence, text/ATA/status filters, paging, case restore, JSON export | Accounts, access control, multi-operator tenancy, cloud sync, retention/backup service |
| Source library | Bounded PDF/TXT/MD extraction, local SQLite chunks, lexical BM25 search, source IDs and exact quotations | OCR, semantic/vector retrieval, external repositories, document authorization checks |
| Agentic investigation | Explicit opt-in OpenAI Agents SDK lead and read-only source scout; max five turns; structured brief; exact quote checked against local chunks | Diagnosis, maintenance actions, directive applicability, semantic entailment verification, external write tools |
| Knowledge graph | Case, ATA ranks, and keyword tags from a stored case | External reports, parts, aircraft configuration, inferred causal links |
| Directives | Clear unavailable state | Directive content, serial applicability, compliance determination |
| Sensor explorer | CSV validation and least-squares health-index threshold extrapolation | Validated prognostics, uncertainty, sensor feed, case-linked RUL |
| Audit | Local hash-chain append, verify, and verified-record display | User identity, remote immutable storage, regulated electronic signature |
| Evaluation | Top-1 accuracy, top-3 coverage, macro-F1, per-class scores, and confusion matrix on the bundled fixture | Fleet performance, held-out results, retrieval quality, verified claim rate, validated RUL accuracy |

The top-level aircraft context remains “not connected”: optional case fields are user-entered notes,
not a connected aircraft profile or configuration source. They are labeled unverified and are not
passed to triage, directive applicability, or safety decisions. Keyword shares must not be called
confidence or probability.

## Case library requirements

- Every case receives a unique ID and UTC creation timestamp. Case text and analysis payload persist
  in a local SQLite database configured by `AEROSAFE_CASES_PATH`.
- `POST /cases` optionally accepts aircraft model, aircraft serial/MSN, component, part number,
  and component serial. Non-empty values are stored under `aircraft_context` with
  `source=user_supplied` and `verified=false`; values are not sent to triage or used for safety
  decisions. Each value is trimmed and limited to 100 characters.
- `GET /cases` accepts `q`, `outcome`, `ata`, `limit`, and `offset`. Query filters are combined with
  AND semantics; text search matches the case ID, original description, extracted tags, returned
  ATA rankings, and user-supplied context values. Newest cases appear first.
- `GET /cases/{case_id}` returns the saved analysis payload; `GET /cases/{case_id}/graph` rebuilds
  the graph from that payload after restart. Missing IDs return 404.
- `POST /cases` defaults to `mode=baseline`. `mode=agentic` is an explicit opt-in that sends the
  report and matching source excerpts to the configured OpenAI model. A missing key or provider
  failure is surfaced in the saved result; the keyword baseline remains intact.
- `POST /sources` accepts PDF, TXT, or MD uploads up to 8 MiB; PDFs are limited to 120 pages and
  extracted content to 250,000 characters. Scanned PDF OCR is unavailable. Source files and chunks
  persist locally at `AEROSAFE_SOURCES_PATH`; `GET /sources` returns metadata, `DELETE /sources/{id}`
  removes a source and its chunks. Local search is lexical, not semantic.
- The agent tools are read-only and bounded to five turns. Each returned finding must refer to a
  source/chunk actually retrieved in that run, and its quotation must match the stored chunk exactly.
  This check verifies quotation identity, not whether the text supports the AI statement. Agent SDK
  cloud tracing is disabled; the app stores stage/status counts without prompts or completion text.
- The browser supports search (including user-entered aircraft/component context), status filter,
  50-case pages, clear no-result states, and restores the newest case on first load. Filtering must
  not submit or mutate case data.
- Case JSON export format `aerosafe-case-export/v1` includes export timestamp, ID, payload, and
  explicit limits. Exporting creates a local download and does not transmit case data.
- Revising a selected case pre-fills its original text and user-supplied context but creates a new
  case ID and audit entries; the source record is immutable through this UI action.

## Triage signal definitions

- Per-ATA raw count is the total number of occurrences of configured baseline phrases in the input.
- `relative_match_share = chapter raw count / total raw count across matched chapters`.
- The returned ATA ranking is limited to the top three chapters with positive counts. Ties use the
  configured ATA keyword-map order.
- Matched phrase counts and relative share are explanatory baseline outputs only. They are not
  calibrated; overlapping phrases can count the same underlying words more than once.
- When no configured keyword matches, the case remains saved, the result displays an explicit
  no-match state, and the system abstains.

## Evaluation definitions

- Top-1 accuracy is correct top-ranked ATA predictions divided by fixture rows.
- Top-3 coverage is the fraction of fixture rows where the expected ATA appears in the three
  returned ranked chapters.
- Per-class precision, recall, F1, and macro-F1 use the union of expected and predicted labels.
  A missing match is `__no_match__`; all values are calculated from raw counts before rounding.
- The confusion matrix contains raw integer counts, includes the no-match label when present, and
  totals exactly the fixture size.
- The included 14-row project-authored fixture is synthetic and is only a wiring/sanity check. Its
  observed score is not an operational benchmark.

## Non-functional requirements

- **Fail closed:** unsupported evidence, missing retrieval, or unimplemented claim verification must
  never yield an actionable draft or a reviewer approval gate.
- **Explainable:** show source category and matched terms for baseline rankings; show limitations
  adjacent to demo estimates and smoke metrics.
- **Local-first:** case, audit, and source stores remain on the host volume. No document/report leaves
  the machine unless the user explicitly selects agentic mode; then only the report and matching
  excerpts are sent to OpenAI. Optional Whisper model acquisition is documented separately.
- **Input bounds:** 10,000 characters per defect, 25 MiB voice upload, 1 MiB sensor CSV, and bounded
  case query/pagination parameters.
- **Accessible:** keyboard-operable controls, visible focus, semantic headings/labels, readable
  status text, and responsive layouts without horizontal page overflow.
- **Resilient:** malformed records produce readable errors; SQLite transactions close promptly;
  audit corruption prevents records from being displayed as trusted.

## Release acceptance

1. Start with Docker Compose and verify a healthy `/health` response.
2. Create both a matching and a no-match case; confirm each is saved and abstains without evidence.
3. Restart the API container and confirm case search, detail, and graph still work.
4. Search by description, ATA, and aircraft/component context; filter by outcome; page through more
   than 50 cases; and choose a case beyond the first 100 in the knowledge graph.
5. Export a case and validate its schema version, timestamp, ID, saved text, and limitations.
6. Confirm signal-share math with overlapping and unmatched keywords.
7. Confirm top-1, top-3, class metrics, and confusion-matrix total against the exact CSV fixture.
8. Exercise valid/invalid sensor files, invalid audio, unknown cases, audit tampering, desktop and
   narrow-screen navigation.
9. Review all visible placeholders against the feature contract; no unimplemented integration may
   be presented as operational data or a completed check.
10. Upload and delete bounded source documents; verify restart persistence and exact local chunk retrieval.
11. With an API key configured, opt in to an agent run against a synthetic document and confirm the
    resulting brief quotes only retrieved local source text. Without a key, baseline remains usable.

## Next implementation priorities

1. Integrate an authoritative aircraft configuration source before enabling serial applicability.
2. Integrate approved read-only source datasets with record IDs, licenses, retrieval citations, and
   a reviewed relevance set before enabling evidence-backed drafts.
3. Build deterministic directive applicability only after obtaining authoritative directive text
   and aircraft/part/serial inputs; test unknown/missing context as “needs review.”
4. Develop retrieval, speech, and RUL measures only with documented labeled datasets and fixed
   train/validation/test splits.
5. Add authentication, roles, retention, backup, and deployment hardening only if the project moves
   beyond a single-user local demo.
