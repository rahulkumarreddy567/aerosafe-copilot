"""Small SQLite repository for durable local case history."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class CaseStore:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    ata_code TEXT NOT NULL DEFAULT '',
                    search_text TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS cases_created_idx ON cases(created_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS cases_outcome_idx ON cases(outcome)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _search_text(payload: dict) -> str:
        tags = [value for _, value in payload.get("entities", [])]
        ata = [f"{code} {name}" for code, name, *_ in payload.get("ata", [])]
        return " ".join([payload.get("text", ""), *tags, *ata]).casefold()

    def save(self, case_id: str, payload: dict, created_at: str):
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        status = payload.get("decision") or payload.get("outcome", "unknown")
        status = {"approve": "approved", "reject": "rejected"}.get(status, status)
        rankings = payload.get("ata") or []
        ata_code = ",".join(str(item[0]) for item in rankings)
        with self._connect() as db:
            db.execute("""
                INSERT INTO cases(case_id, created_at, updated_at, outcome, ata_code, search_text, payload)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    outcome=excluded.outcome,
                    ata_code=excluded.ata_code,
                    search_text=excluded.search_text,
                    payload=excluded.payload
            """, (case_id, created_at, created_at, status, ata_code, self._search_text(payload), serialized))

    def get(self, case_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, query: str = "", outcome: str = "", ata: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        clauses, values = [], []
        if query.strip():
            clauses.append("(instr(lower(case_id), ?) > 0 OR instr(search_text, ?) > 0)")
            needle = query.strip().casefold()
            values.extend((needle, needle))
        if outcome:
            clauses.append("outcome = ?")
            values.append(outcome)
        if ata:
            clauses.append("(',' || ata_code || ',') LIKE ?")
            values.append(f"%,{ata},%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.extend((limit, offset))
        with self._connect() as db:
            rows = db.execute(f"""
                SELECT case_id, created_at, outcome, ata_code, payload FROM cases
                {where} ORDER BY created_at DESC, case_id DESC LIMIT ? OFFSET ?
            """, values).fetchall()
        results = []
        for row in rows:
            payload = json.loads(row["payload"])
            results.append({
                "case_id": row["case_id"],
                "created_at": row["created_at"],
                "outcome": row["outcome"],
                "language": payload.get("language"),
                "ata": payload.get("ata", []),
                "text": payload.get("text", ""),
            })
        return results
