# Interactive prototype feature specification

This document defines the working contract for the case graph, sensor trend explorer, and
baseline evaluation view. These are prototype tools; none can authorize maintenance work.

## Case export

- A user can download the selected case as JSON from the triage result.
- Format version: `aerosafe-case-export/v1`; includes export timestamp, case ID, complete
  stored analysis payload, and explicit implementation/data limitations.
- The browser creates the file locally; no case is sent to a new service. Exporting is optional
  and does not persist case history in the API.
- The file is a prototype analysis artifact, not an approved maintenance record or instruction.

## Persistent case library

- Cases are stored in a local SQLite database at `AEROSAFE_CASES_PATH`; Docker defaults to
  `/data/cases.sqlite3` on the mounted `data/` volume. Local development defaults to
  `data/cases.sqlite3`.
- Case payloads include the entered description, language, ranked ATA tags, extracted keyword
  entities, pipeline trace, evidence/draft state, outcome, creation time, and any reviewer fields.
- `GET /cases` supports `q`, `outcome`, `ata`, `limit` (1-100), and `offset` filters. Search covers
  case ID, description, extracted tags, and all ranked ATA chapters. Results sort newest first.
- `GET /cases/{case_id}` and `/graph` read from durable storage. A service restart must preserve
  case history; a missing ID returns 404.
- The browser case board provides search, status filtering, and paging. Search is debounced and
  does not create cases. The newest case is restored on initial load when no case is selected.
- Optional case context includes aircraft model, aircraft serial/MSN, component, part number, and
  component serial (each at most 100 characters). The API trims values, stores them as
  `source=user_supplied` and `verified=false`, exposes them in detail/list responses, and indexes
  them for case search. Blank values are omitted. Revising a case copies these fields into the new
  case. Context is descriptive only and is not passed into triage or applicability decisions.
- Storage is local to a single service instance. There is no authentication, multi-user isolation,
  retention policy, backup process, or concurrent multi-worker coordination in this prototype.

## Case relationship graph

- Source: the selected durable case returned by `POST /cases` and stored in local SQLite.
- Endpoint: `GET /cases/{case_id}/graph`.
- Nodes: one case node, each ATA ranking, and deduplicated symptom, component, and phase tags.
- Edges: `ranked` from case to ATA and `tagged` from case to extracted keyword tag.
- Interactions: choose a case, select nodes by mouse or keyboard, and inspect the selected
  node's explanation and source label.
- Data boundary: this view does not contain ASRS/BEA passages, airworthiness directives, parts,
  aircraft configuration, or relationships inferred from an external knowledge base. Tags come
  from the keyword baseline and are not verified findings.
- Persistence: the graph can be rebuilt from the stored case after an API restart.

## Explainable keyword triage

- Each positive ATA ranking contains its one-based rank, relative match share, and all configured
  matching phrase/count pairs.
- The share is a normalized count of keyword hits across the matched chapters; it is not calibrated
  confidence or probability. Overlapping phrases can count shared words more than once.
- At most three positive ATA chapters are returned. No match is represented as an empty ranking and
  an abstention, never as a “no defect” result.
- The case’s Triage signals tab explains this calculation and shows the matched phrases. It does not
  infer causal relationships or recommended maintenance.

## Sensor trend and illustrative RUL estimate

- Endpoint: `POST /rul/analyze?threshold=0.2` as `multipart/form-data` with a `file` field.
- File type: UTF-8 CSV, maximum 1 MB, with headers `cycle,health_index`.
- Rows: at least three; cycle values must be numeric and strictly increasing. Health index must
  be finite and in the range 0 to 1. The threshold must be finite and in the range 0 inclusive
  to 1 exclusive.
- Calculation: ordinary least-squares slope of health index against cycle. The endpoint rejects
  flat or rising trends. Remaining cycles are `ceil((last health index - threshold) / -slope)`,
  floored at zero.
- Returned values: observed series, slope, threshold, last reading, estimated remaining cycles,
  method, and a warning. The UI plots the observed readings and a dashed trend projection.
- Limits: this is not a trained prognostics model. It assumes a normalized monotonic health score,
  linear degradation, a meaningful user-provided threshold, and comparable cycles. It does not
  estimate uncertainty or account for maintenance events, sensor calibration, aircraft type,
  or operating context. It must not be used to plan or approve maintenance.

## ATA baseline evaluation

- Endpoint: `GET /evaluation`; source fixture: `eval/ata_smoke.csv`.
- Dataset: 14 project-authored synthetic text examples with an expected ATA code across seven
  supported categories.
- Metrics: top-ranked ATA accuracy, top-3 coverage, and macro-F1 (computed from unrounded class scores, then rounded
  to three decimals in the response), with per-class support, precision, recall, and F1. Macro-F1
  averages the union of expected and predicted labels; a missing prediction is counted as a
  `__no_match__` prediction and contributes a false negative to its expected class.
- The response includes a raw-count confusion matrix over expected/predicted labels; its cell total
  must equal the fixture sample count.
- Retrieval recall@k, RUL RMSE, unsupported-claim rate, and voice WER remain unavailable because
  this repository does not yet include the corresponding labeled data or model outputs.
- The UI gives prerequisites for those measures in one compact section and does not render empty
  placeholder score tiles.
- Limits: examples are not real maintenance narratives, independently labeled, held out, or
  representative of fleet operations. The displayed metrics are a wiring/sanity check only and
  must not be described as model performance on aviation data.
