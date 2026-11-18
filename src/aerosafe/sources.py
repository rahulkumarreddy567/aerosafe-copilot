"""Local, source-cited document library for investigation runs."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_PAGES = 120
MAX_SOURCE_CHARS = 250_000
CHUNK_SIZE = 1_100
CHUNK_OVERLAP = 160
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{1,}", re.IGNORECASE)
STOP_WORDS = {
    "about", "after", "again", "also", "are", "been", "being", "between", "case", "could",
    "from", "have", "into", "more", "most", "other", "over", "same", "some", "such", "than",
    "that", "their", "there", "these", "they", "this", "through", "under", "very", "what",
    "when", "where", "which", "while", "with", "would", "your",
}


def parse_source(filename: str, raw: bytes) -> tuple[str, list[dict]]:
    """Extract bounded text from PDF or UTF-8 text/Markdown uploads."""
    if not raw:
        raise ValueError("The source file is empty.")
    suffix = Path(filename).suffix.casefold()
    if suffix in {".txt", ".md"}:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text sources must use UTF-8 encoding.") from exc
        if len(text) > MAX_SOURCE_CHARS:
            raise ValueError("Extracted source text exceeds the 250,000 character limit.")
        if not text.strip():
            raise ValueError("The source file contains no searchable text.")
        return "text/markdown" if suffix == ".md" else "text/plain", [{"page": None, "text": text}]

    if suffix != ".pdf":
        raise ValueError("Upload a PDF, TXT, or Markdown source file.")
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(reader.pages) > MAX_SOURCE_PAGES:
            raise ValueError(f"PDF exceeds the {MAX_SOURCE_PAGES} page limit.")
        pages = [{"page": index + 1, "text": page.extract_text() or ""}
                 for index, page in enumerate(reader.pages)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read this PDF. Check that it is a valid, unencrypted document.") from exc
    if sum(len(page["text"]) for page in pages) > MAX_SOURCE_CHARS:
        raise ValueError("Extracted source text exceeds the 250,000 character limit.")
    if not any(page["text"].strip() for page in pages):
        raise ValueError("This PDF has no extractable text. OCR for scanned PDFs is not enabled.")
    return "application/pdf", pages


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _make_chunks(pages: Iterable[dict], source_id: str) -> list[dict]:
    chunks: list[dict] = []
    for page in pages:
        text = _clean_text(page.get("text", ""))
        start = 0
        page_no = page.get("page")
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + CHUNK_SIZE // 2, end)
                if boundary > start:
                    end = boundary
            segment = text[start:end].strip()
            if segment:
                chunks.append({
                    "chunk_id": f"{source_id}:p{page_no or 0}:c{len(chunks) + 1}",
                    "page": page_no,
                    "text": segment,
                })
            if end >= len(text):
                break
            start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


class SourceStore:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("""CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                char_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS source_chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
                page INTEGER,
                text TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS source_chunks_source_idx ON source_chunks(source_id)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add(self, filename: str, content_type: str, raw: bytes, pages: list[dict]) -> dict:
        source_id = f"src-{uuid.uuid4().hex}"
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        chunks = _make_chunks(pages, source_id)
        char_count = sum(len(page.get("text", "")) for page in pages)
        page_count = sum(bool(page.get("page")) for page in pages) or 1
        with self._connect() as db:
            db.execute("""INSERT INTO sources
                (source_id, filename, content_type, sha256, created_at, page_count, char_count, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                    source_id, filename, content_type, hashlib.sha256(raw).hexdigest(), created_at,
                    page_count, char_count, len(chunks),
                ))
            db.executemany("INSERT INTO source_chunks(chunk_id, source_id, page, text) VALUES (?, ?, ?, ?)", [
                (chunk["chunk_id"], source_id, chunk["page"], chunk["text"]) for chunk in chunks
            ])
        return self.get(source_id) or {}

    def list(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("""SELECT source_id, filename, content_type, sha256, created_at,
                page_count, char_count, chunk_count FROM sources ORDER BY created_at DESC, source_id DESC""").fetchall()
        return [dict(row) for row in rows]

    def get(self, source_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        return dict(row) if row else None

    def get_chunk(self, source_id: str, chunk_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("""SELECT c.chunk_id, c.source_id, c.page, c.text, s.filename
                FROM source_chunks c JOIN sources s USING(source_id)
                WHERE c.source_id = ? AND c.chunk_id = ?""", (source_id, chunk_id)).fetchone()
        return dict(row) if row else None

    def delete(self, source_id: str) -> bool:
        with self._connect() as db:
            result = db.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
        return result.rowcount > 0

    def search(self, query: str, limit: int = 5) -> list[dict]:
        terms = [token.casefold() for token in TOKEN_RE.findall(query) if token.casefold() not in STOP_WORDS]
        terms = list(dict.fromkeys(terms))[:32]
        if not terms:
            return []
        with self._connect() as db:
            rows = db.execute("""SELECT c.chunk_id, c.source_id, c.page, c.text, s.filename
                FROM source_chunks c JOIN sources s USING(source_id)""").fetchall()
        if not rows:
            return []
        documents = [dict(row) for row in rows]
        tokenized = [Counter(token.casefold() for token in TOKEN_RE.findall(doc["text"])) for doc in documents]
        document_frequency = {term: sum(term in tokens for tokens in tokenized) for term in terms}
        average_length = sum(sum(tokens.values()) for tokens in tokenized) / max(1, len(tokenized))
        total_docs = len(documents)
        scored = []
        for doc, counts in zip(documents, tokenized):
            length = sum(counts.values())
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                idf = 1 + (total_docs - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
                score += idf * (frequency * 2.2) / (
                    frequency + 1.2 * (0.25 + 0.75 * length / max(1, average_length))
                )
            if score > 0:
                doc["score"] = round(score, 4)
                scored.append(doc)
        return sorted(scored, key=lambda item: (-item["score"], item["source_id"], item["chunk_id"]))[:limit]

    def count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT count(*) FROM sources").fetchone()[0])
