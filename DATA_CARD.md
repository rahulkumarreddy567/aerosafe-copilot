# Data card (fill this in as you add data)

| Source | What | Retrieved on | Licence / terms | Used for |
|---|---|---|---|---|
| NASA ASRS | Safety report narratives | | | NLP, retrieval |
| BEA | Investigation reports (FR/EN) | | | Retrieval, bilingual eval |
| EASA / FAA | Airworthiness directives | | | Compliance agent |
| NASA C-MAPSS | Turbofan run-to-failure series | | | RUL model |
| Project-authored synthetic fixtures | 14 ATA phrases for baseline smoke checks | 2026-11-13 | Original project content; no external license | UI and implementation sanity checks only; not operational data |
| Project-authored synthetic fixture | Normalized cycle and health-index trend | 2026-11-13 | Original project content; no external license | Demonstrate the CSV trend explorer only; not aircraft sensor data |

Split by document or time, never by random sentence, to avoid leakage.
