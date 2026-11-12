# Architecture

Input (text or voice) -> Whisper (optional) -> Triage (NLP) -> Retrieval -> Compliance ->
Predictive maintenance -> Draft -> Verifier -> Human approval -> Audit log.

The verifier can send the case back to Retrieval at most `AEROSAFE_MAX_RETRIES` times.
If claims are still unsupported, the system abstains and nothing is recommended.
Every step and every reviewer decision is written to the hash-chained audit log.
