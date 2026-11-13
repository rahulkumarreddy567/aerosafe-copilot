# Architecture

Input (text or voice) -> Whisper (optional) -> Triage (NLP) -> Retrieval -> Compliance ->
Predictive maintenance -> Draft -> Verifier -> Human approval -> Audit log.

The verifier can send the case back to Retrieval at most `AEROSAFE_MAX_RETRIES` times.
If claims are still unsupported, the system abstains and nothing is recommended.
Every step and every reviewer decision is written to the hash-chained audit log.

The browser knowledge graph is a case-local view of the ATA rankings and keyword entities
emitted by triage; it does not represent retrieved evidence. The separate RUL explorer accepts
a normalized `cycle,health_index` CSV and extrapolates its least-squares trend to a configurable
threshold. The evaluation endpoint computes ATA classification metrics against a small synthetic
fixture. These demo views do not change the maintenance decision gate.
