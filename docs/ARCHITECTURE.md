# Architecture

## Current request path

Text or optional voice input -> keyword triage -> retrieval stub -> compliance stub ->
predictive-maintenance stub -> draft stub -> fail-closed verifier -> abstain.

The bounded retry loop is configurable with `AEROSAFE_MAX_RETRIES`. The current retrieval stub
returns no sources, so ordinary cases abstain and no draft or approval action is made available.
The guarded reviewer API is testable but cannot be reached through the current case path. Case
analysis and reviewer decisions are appended to the local hash-chained audit log.

## Case storage and browser

Case payloads are stored in local SQLite (`AEROSAFE_CASES_PATH`) and survive API restarts. The
single-process prototype does not provide accounts, access control, multi-worker coordination,
retention, or automated backups. The case board queries by description, ID, tags, ATA, and outcome
with bounded offset pagination.

The browser graph displays only the selected case, its ranked ATA chapters, and keyword tags. It
does not show retrieved reports or causal links. Triage signal shares explain keyword hits; they are
not calibrated confidence scores. The top bar says the aircraft context is not connected.

## Standalone tools

- The sensor explorer accepts a normalized `cycle,health_index` CSV and extrapolates its
  least-squares trend to a configurable threshold. It is a demo estimator, not a validated RUL
  model, and is not attached to a case or sensor feed.
- The evaluation endpoint computes top-1 accuracy, top-3 coverage, per-class metrics, macro-F1,
  and a confusion matrix against a small synthetic fixture.
- The hash-chain audit log is local and tamper-evident, but does not identify authenticated users or
  provide remote immutable storage.

These demo tools do not change the maintenance decision gate.
