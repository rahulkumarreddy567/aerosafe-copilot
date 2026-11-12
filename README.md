# AeroSafe Copilot

A multi-agent maintenance and safety-intelligence **prototype** for aviation, built on public data.
It accepts a defect description (typed or spoken, English or French) and returns triage with a
case trace. Recommendations are disabled until evidence retrieval and verification are implemented.
Inference runs locally; Whisper downloads its model on first use and then caches it locally.

> Prototype on public data. Not certified, not connected to any operator system, and not a
> substitute for approved maintenance procedures.

## What works today (starter skeleton)

| Part | Status |
|---|---|
| FastAPI service (`/cases`, `/transcribe`, decisions, audit verify) | Working |
| LangGraph pipeline with a bounded retry loop | Working; currently fails closed and abstains because retrieval and verification are not implemented |
| Hash-chained audit log with tamper detection | Working, tested |
| Whisper speech-to-text (local, faster-whisper, FR/EN auto-detect) | Docker includes the speech extra; local installs need it |
| NLP triage (ATA ranking, entity tags) | Keyword baseline, to be replaced by a fine-tuned model |
| Retrieval, directive rules, RUL model, local LLM, entailment verifier | TODO (see roadmap) |
| Browser console | Triage, case board, agent map, graph, parts, directives, RUL, audit and evaluation views at `/`; live API data is shown where available |

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
Compose keeps Whisper's downloaded model in a named volume between container restarts. Case
objects are held in memory for the lifetime of the API process; the audit log is stored under `data/`.

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
```

Until real retrieval and claim verification are implemented, `/cases` returns an abstention
with no recommendation. This is intentional: placeholder evidence must not be treated as support.

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
8. Replace the starter browser interface with a React front end if a richer client is needed.

Only publish numbers you measured yourself.

The evaluation CSV contains references only. Record the ignored local clips under `eval/clips/`
before running WER; relative `audio_path` values resolve from the CSV's directory.
