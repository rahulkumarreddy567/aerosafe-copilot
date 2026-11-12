"""Append-only, hash-chained audit log (JSON lines).

Each record stores the hash of the previous record, so editing or deleting an
earlier line breaks every hash after it. `verify()` finds the first bad line.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from threading import RLock

GENESIS = "0" * 64
_AUDIT_LOCK = RLock()


def _digest(body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def _records(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def records(self) -> list[dict]:
        """Return a consistent snapshot of the current log records."""
        with _AUDIT_LOCK:
            return self._records()

    def append(self, actor: str, action: str, payload: dict) -> dict:
        with _AUDIT_LOCK:
            recs = self._records()
            body = {
                "index": len(recs) + 1,
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "actor": actor,
                "action": action,
                "payload": payload,
                "prev_hash": recs[-1]["hash"] if recs else GENESIS,
            }
            rec = {**body, "hash": _digest(body)}
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            return rec

    def verify(self) -> tuple[bool, int | None]:
        """Return (ok, first_bad_index). first_bad_index is None when the chain is intact."""
        prev = GENESIS
        with _AUDIT_LOCK:
            if not os.path.exists(self.path):
                return True, None
            with open(self.path, encoding="utf-8", errors="replace") as f:
                line_index = 0
                for line in f:
                    if not line.strip():
                        continue
                    line_index += 1
                    try:
                        rec = json.loads(line)
                        body = {k: v for k, v in rec.items() if k != "hash"}
                        if (
                            rec.get("index") != line_index
                            or body.get("prev_hash") != prev
                            or not isinstance(rec.get("hash"), str)
                            or _digest(body) != rec["hash"]
                        ):
                            return False, line_index
                        prev = rec["hash"]
                    except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
                        return False, line_index
        return True, None
