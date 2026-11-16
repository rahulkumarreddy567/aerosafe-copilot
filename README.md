# AeroSafe Copilot

A maintenance and safety-intelligence **portfolio prototype** for aviation, built on public data.
It accepts a defect description (typed or spoken, English or French) and returns triage with a
case trace. Recommendations are disabled until evidence retrieval and verification are implemented.
Inference runs locally; Whisper downloads its model on first use and then caches it locally.

> Prototype on public data. Not certified, not connected to any operator system, and not a
> substitute for approved maintenance procedures.

## Working features and implementation limits

| Part | Status |
|---|---|
| FastAPI service (`/cases`, `/transcribe`, guarded reviewer endpoint, audit verification) | Working; ordinary triage remains abstained |
| Durable case library | SQLite-backed; search, ATA/status filters, paging, and restart persistence |
| LangGraph pipeline with a bounded retry loop | Working; currently fails closed and abstains because retrieval and verification are not implemented |
| Hash-chained audit log with tamper detection | Working, tested |
| Whisper speech-to-text (local, faster-whisper, FR/EN auto-detect) | Docker includes the speech extra; local installs need it |
| NLP triage (ATA ranking, entity tags) | Keyword baseline, to be replaced by a fine-tuned model |
| Triage explainability | Matched phrase counts and relative ATA match share; explicitly not confidence |
| Evidence retrieval, directive rules, local LLM, entailment verifier | TODO (see roadmap); recommendations remain disabled |
| Knowledge graph | Working case graph built from keyword triage tags. It does not connect external reports, directives, or aircraft configuration. |
| RUL view | Working CSV trend explorer with linear threshold-crossing extrapolation. This is a demo estimator, not a trained model or maintenance prediction. |
| Evaluation view | Top-1 accuracy, top-3 coverage, macro-F1, per-class report, and confusion matrix for a 14-row synthetic smoke set; not a benchmark |
| Browser console | Triage, case board, agent map, interactive graph, illustrative parts map, directives status, RUL, audit, and evaluation views at `/`. |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ",speech" for Whisper
make test
make run                            # http://localhost:8000/docs
```

Open `http://localhost:8000/` for the browser interface or `/docs` for the API explorer.
The Docker image installs the speech extra; the local quick start can add it with
`pip install -e ".[dev,speech]"`.
Compose keeps Whisper's downloaded model in a named volume between container restarts. Cases and
the audit log are stored under `data/` and survive API container restarts. Set
`AEROSAFE_CASES_PATH` and `AEROSAFE_AUDIT_PATH` to choose alternate local paths.

Docker launch:

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

```bash
curl -s localhost:8000/cases -H 'content-type: application/json' \
  -d '{"text":"Intermittent hydraulic pressure drop during landing gear retraction"}'
curl -s localhost:8000/audit/verify
curl -s 'localhost:8000/cases?q=hydraulic&ata=29&limit=20'
```

Until real retrieval and claim verification are implemented, `/cases` returns an abstention
with no recommendation. This is intentional: placeholder evidence must not be treated as support.

## Interactive graph, RUL, and evaluation

- The graph screen uses `GET /cases/{case_id}/graph` and only draws the case, ATA rankings,
  and keyword entities already returned by triage.
- The RUL screen accepts CSV files with `cycle,health_index` columns (health index from 0 to 1,
  increasing cycles, at least three rows). `POST /rul/analyze` fits an ordinary least-squares
  trend and estimates crossing a user-selected threshold. The sample file is available at
  `/static/demo_sensor.csv`.
- The evaluation screen calls `GET /evaluation` and reports top-1 accuracy, top-3 coverage,
  macro-F1, per-class scores, and a confusion matrix for `eval/ata_smoke.csv`. This set is synthetic and intentionally small. Retrieval,
  RUL model accuracy, claim verification, and voice WER still require real labeled data.

The full product contract, release checklist, and roadmap are in [`docs/PRODUCT_SPEC.md`](docs/PRODUCT_SPEC.md).
Input formats, calculations, and known limits are documented in [`docs/feature-spec.md`](docs/feature-spec.md).
Screen behavior, visual language, responsive rules, accessibility requirements, and acceptance
checks are documented in [`docs/ui-spec.md`](docs/ui-spec.md).

Voice note (needs `pip install -e ".[speech]"`):

```bash
curl -s -F file=@clip.wav localhost:8000/transcribe
```

## Layout

```
src/aerosafe/
  speech/whisper_service.py   local Whisper wrapper (lazy model load)
  nlp/triage.py               language, ATA ranking, entities (baseline)
  agents/graph.py             LangGraph pipeline and retry loop
  audit/chain.py              hash-chained audit log
  case_store.py               SQLite case repository and filter queries
  api/main.py                 FastAPI app
eval/wer.py                   word error rate for your own aviation phrases
tests/                        audit chain, retry loop, API flow
```

## Roadmap

1. Ingest ASRS, BEA, EASA/FAA ADs and C-MAPSS; write `DATA_CARD.md` with sources and licences.
2. Replace `nlp/triage.py` with a fine-tuned CamemBERT/ModernBERT classifier plus NER; keep the keyword version as the baseline row.
3. Hybrid retrieval (BM25 + BGE-M3 + reranker) and a Neo4j graph; measure recall@k on a hand-labelled gold set.
4. Rules-first AD applicability checker; report false NOT_APPLICABLE count.
5. RUL model on C-MAPSS (LSTM/TCN vs XGBoost baseline).
6. Local LLM (vLLM or Ollama) in `draft` and an entailment check in `verify`; only then allow cases to reach human approval.
7. Whisper evaluation: record 50+ aviation phrases, run `python eval/wer.py eval/aviation_phrases.csv`, report WER and end-to-end ATA accuracy for voice vs typed input.
8. Add accounts, roles, retention, backup, or multi-user deployment only if the project moves beyond
   its documented single-user local prototype.

Only publish numbers you measured yourself.

The evaluation CSV contains references only. Record the ignored local clips under `eval/clips/`
before running WER; relative `audio_path` values resolve from the CSV's directory.
