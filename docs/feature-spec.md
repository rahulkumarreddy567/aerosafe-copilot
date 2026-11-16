# Interactive prototype feature specification

This document defines the working contract for the case graph, sensor trend explorer, and
baseline evaluation view. These are prototype tools; none can authorize maintenance work.

## Case export

- A user can download the selected case as JSON from the triage result.
- Format version: `aerosafe-case-export/v1`; includes export timestamp, case ID, complete
  in-memory analysis payload, and explicit implementation/data limitations.
- The browser creates the file locally; no case is sent to a new service. Exporting is optional
  and does not persist case history in the API.
- The file is a prototype analysis artifact, not an approved maintenance record or instruction.

## Case relationship graph

- Source: the selected in-memory case returned by `POST /cases`.
- Endpoint: `GET /cases/{case_id}/graph`.
- Nodes: one case node, each ATA ranking, and deduplicated symptom, component, and phase tags.
- Edges: `ranked` from case to ATA and `tagged` from case to extracted keyword tag.
- Interactions: choose a case, select nodes by mouse or keyboard, and inspect the selected
  node's explanation and source label.
- Data boundary: this view does not contain ASRS/BEA passages, airworthiness directives, parts,
  aircraft configuration, or relationships inferred from an external knowledge base. Tags come
  from the keyword baseline and are not verified findings.
- Persistence: cases are held in process memory; the graph disappears when the API restarts.

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
- Metrics: top-ranked ATA accuracy and macro-F1 (computed from unrounded class scores, then rounded
  to three decimals in the response), with per-class support, precision, recall, and F1. Macro-F1
  averages the union of expected and predicted labels; a missing prediction is counted as a
  `__no_match__` prediction and contributes a false negative to its expected class.
- Retrieval recall@k, RUL RMSE, unsupported-claim rate, and voice WER remain unavailable because
  this repository does not yet include the corresponding labeled data or model outputs.
- The UI gives prerequisites for those measures in one compact section and does not render empty
  placeholder score tiles.
- Limits: examples are not real maintenance narratives, independently labeled, held out, or
  representative of fleet operations. The displayed metrics are a wiring/sanity check only and
  must not be described as model performance on aviation data.
