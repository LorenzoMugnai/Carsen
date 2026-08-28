"""Instance-local chunk persistence backed by SQLite + FTS5.

One database per instance at ``<data_directory>/chunks.sqlite3`` holds the
canonical chunks and a contentless FTS5 index for lexical search. This replaces
the earlier one-file-per-source JSONL layout, which had to be fully read into
memory for every served instance.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

from carsen_mcp.retrieval.filters import matches_filters
from carsen_mcp.retrieval.models import SearchResult
from carsen_mcp.retrieval.sparse import (
    chunk_to_search_result,
    document_tokens,
    fts_match_query,
    symbol_path_bonus,
    tokenise,
)

from .model import Chunk

_FILTER_COLUMNS = ("source_type", "document_type", "language", "repository_name")
_PREFIX_FILTER_KEYS = ("path_prefix", "source_path_prefix")
#: bm25() column weights: text, symbol, path. Symbol and path carry more signal.
_BM25_WEIGHTS = (1.0, 8.0, 3.0)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
  rowid           INTEGER PRIMARY KEY,
  chunk_id        TEXT UNIQUE NOT NULL,
  file_key        TEXT NOT NULL,
  knowledge_id    TEXT NOT NULL,
  source_path     TEXT NOT NULL,
  kind            TEXT,
  symbol          TEXT,
  start_line      INTEGER,
  end_line        INTEGER,
  ord             INTEGER,
  content_hash    TEXT,
  indexed_at      TEXT,
  text            TEXT NOT NULL,
  metadata        TEXT NOT NULL,
  source_type     TEXT,
  document_type   TEXT,
  language        TEXT,
  repository_name TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_file_key  ON chunks(file_key);
CREATE INDEX IF NOT EXISTS idx_chunks_source    ON chunks(source_path);
CREATE INDEX IF NOT EXISTS idx_chunks_symbol    ON chunks(symbol);
CREATE INDEX IF NOT EXISTS idx_chunks_knowledge ON chunks(knowledge_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

_FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
    "tok_text, tok_symbol, tok_path, content='', contentless_delete=1, "
    "tokenize='unicode61 remove_diacritics 2')"
)

_INSERT_COLUMNS = (
    "chunk_id, file_key, knowledge_id, source_path, kind, symbol, start_line, end_line, "
    "ord, content_hash, indexed_at, text, metadata, source_type, document_type, language, repository_name"
)


class FTS5UnavailableError(RuntimeError):
    """SQLite was built without the FTS5 module required for sparse retrieval."""


class ChunkStore:
    """Store canonical chunks for one instance in ``data_directory/chunks.sqlite3``."""

    def __init__(self, data_directory: Path) -> None:
        directory = Path(data_directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.path = directory / "chunks.sqlite3"
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._create_schema()
        self._import_legacy_jsonl(directory / "chunks")

    # -- schema and migration -------------------------------------------------

    def _create_schema(self) -> None:
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
            try:
                self._db.execute(_FTS_SCHEMA)
            except sqlite3.OperationalError as exc:
                if "fts5" in str(exc).lower():
                    raise FTS5UnavailableError(
                        "this SQLite build lacks the FTS5 module; Carsen retrieval requires it"
                    ) from exc
                raise

    def _import_legacy_jsonl(self, legacy_dir: Path) -> None:
        if not legacy_dir.is_dir():
            return
        with self._lock:
            already = self._db.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
        if already is not None:
            return
        legacy_files = sorted(legacy_dir.glob("*.jsonl"))
        if not legacy_files:
            return
        by_file: dict[str, list[Chunk]] = {}
        for path in legacy_files:
            with path.open("r", encoding="utf-8") as handle:
                chunks = [Chunk.from_dict(json.loads(line)) for line in handle if line.strip()]
            if chunks:
                by_file[chunks[0].source_path] = chunks
        for file_key, chunks in by_file.items():
            self.replace_file_chunks(file_key, chunks)

    # -- writes -------------------------------------------------------------

    def replace_file_chunks(self, source_path: str, chunks: list[Chunk]) -> None:
        """Replace every chunk stored under one source file in a single transaction."""

        with self._lock, self._db:
            self._delete_file(source_path)
            self._delete_chunk_ids([chunk.chunk_id for chunk in chunks])
            for chunk in chunks:
                self._insert_chunk(source_path, chunk)
            self._bump_generation()

    def delete_file_chunks(self, source_path: str) -> None:
        with self._lock, self._db:
            self._delete_file(source_path)
            self._bump_generation()

    def prune_unknown_sources(self, knowledge_id: str, allowed_sources: set[str]) -> int:
        """Drop chunk files for this instance whose source is no longer discoverable."""

        removed = 0
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT file_key, source_path, metadata FROM chunks WHERE knowledge_id = ? GROUP BY file_key",
                (knowledge_id,),
            ).fetchall()
            for row in rows:
                metadata = json.loads(row["metadata"])
                candidates = {row["source_path"]}
                for key in ("path", "source_path", "git_path"):
                    value = metadata.get(key)
                    if value is not None:
                        candidates.add(str(value))
                if candidates.isdisjoint(allowed_sources):
                    self._delete_file(row["file_key"])
                    removed += 1
            if removed:
                self._bump_generation()
        return removed

    def _delete_file(self, file_key: str) -> None:
        rows = self._db.execute("SELECT rowid FROM chunks WHERE file_key = ?", (file_key,)).fetchall()
        for row in rows:
            self._db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (row["rowid"],))
        self._db.execute("DELETE FROM chunks WHERE file_key = ?", (file_key,))

    def _delete_chunk_ids(self, chunk_ids: list[str]) -> None:
        """Remove any rows with these ids regardless of file_key (defensive dedup)."""

        for chunk_id in chunk_ids:
            row = self._db.execute("SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
            if row is not None:
                self._db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (row["rowid"],))
                self._db.execute("DELETE FROM chunks WHERE rowid = ?", (row["rowid"],))

    def _insert_chunk(self, file_key: str, chunk: Chunk) -> None:
        metadata = chunk.metadata
        values = (
            chunk.chunk_id,
            file_key,
            chunk.knowledge_id,
            chunk.source_path,
            chunk.kind,
            chunk.symbol,
            chunk.start_line,
            chunk.end_line,
            chunk.order,
            chunk.content_hash,
            chunk.indexed_at,
            chunk.text,
            json.dumps(metadata, sort_keys=True),
            *[_as_scalar(metadata.get(column)) for column in _FILTER_COLUMNS],
        )
        placeholders = ", ".join("?" for _ in values)
        cursor = self._db.execute(f"INSERT INTO chunks ({_INSERT_COLUMNS}) VALUES ({placeholders})", values)
        rowid = cursor.lastrowid
        self._db.execute(
            "INSERT INTO chunks_fts (rowid, tok_text, tok_symbol, tok_path) VALUES (?, ?, ?, ?)",
            (
                rowid,
                " ".join(document_tokens(chunk_to_search_result(chunk))),
                " ".join(tokenise(chunk.symbol or "")),
                " ".join(tokenise(chunk.source_path)),
            ),
        )

    def _bump_generation(self) -> None:
        self._db.execute(
            "INSERT INTO meta (key, value) VALUES ('generation', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)"
        )

    # -- reads ------------------------------------------------------------

    def generation(self) -> int:
        row = self._db.execute("SELECT value FROM meta WHERE key = 'generation'").fetchone()
        try:
            return int(row["value"]) if row is not None else 0
        except (TypeError, ValueError):
            return 0

    def count(self, knowledge_id: str | None = None) -> int:
        if knowledge_id is None:
            row = self._db.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
        else:
            row = self._db.execute("SELECT COUNT(*) AS n FROM chunks WHERE knowledge_id = ?", (knowledge_id,)).fetchone()
        return int(row["n"])

    def source_count(self, knowledge_id: str | None = None) -> int:
        if knowledge_id is None:
            row = self._db.execute("SELECT COUNT(DISTINCT source_path) AS n FROM chunks").fetchone()
        else:
            row = self._db.execute(
                "SELECT COUNT(DISTINCT source_path) AS n FROM chunks WHERE knowledge_id = ?", (knowledge_id,)
            ).fetchone()
        return int(row["n"])

    def load_all_chunks(self) -> list[Chunk]:
        """Return every stored chunk; used by re-embedding and maintenance."""

        return list(self.iter_chunks())

    def iter_chunks(self, knowledge_id: str | None = None) -> Iterator[Chunk]:
        query = "SELECT * FROM chunks"
        params: tuple[Any, ...] = ()
        if knowledge_id is not None:
            query += " WHERE knowledge_id = ?"
            params = (knowledge_id,)
        query += " ORDER BY source_path, ord, chunk_id"
        for row in self._db.execute(query, params):
            yield _row_to_chunk(row)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        row = self._db.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
        return _row_to_chunk(row) if row is not None else None

    def chunk_by_source(self, source_id: str) -> Chunk | None:
        row = self._db.execute(
            "SELECT * FROM chunks WHERE source_path = ? ORDER BY ord LIMIT 1", (source_id,)
        ).fetchone()
        if row is None:
            row = self._db.execute(
                "SELECT * FROM chunks WHERE json_extract(metadata, '$.source_id') = ? ORDER BY ord LIMIT 1",
                (source_id,),
            ).fetchone()
        return _row_to_chunk(row) if row is not None else None

    def chunks_for_source(self, source_path: str) -> list[Chunk]:
        rows = self._db.execute(
            "SELECT * FROM chunks WHERE source_path = ? ORDER BY ord, chunk_id", (source_path,)
        )
        return [_row_to_chunk(row) for row in rows]

    def find_symbol(self, symbol: str, limit: int = 8, knowledge_id: str | None = None) -> list[Chunk]:
        query = "SELECT * FROM chunks WHERE symbol = ?"
        params: list[Any] = [symbol]
        if knowledge_id is not None:
            query += " AND knowledge_id = ?"
            params.append(knowledge_id)
        query += " ORDER BY source_path, ord LIMIT ?"
        params.append(limit)
        return [_row_to_chunk(row) for row in self._db.execute(query, params)]

    def search_sparse(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        knowledge_id: str | None = None,
    ) -> list[SearchResult]:
        """Lexical search over the FTS5 index with the shared tokeniser and bonuses."""

        if limit < 1:
            raise ValueError("limit must be positive")
        match = fts_match_query(query)
        if not match:
            return []
        clauses = ["chunks_fts MATCH ?"]
        params: list[Any] = [match]
        if knowledge_id is not None:
            clauses.append("c.knowledge_id = ?")
            params.append(knowledge_id)
        sql_clauses, sql_params, python_filters = _translate_filters(filters)
        clauses.extend(sql_clauses)
        params.extend(sql_params)
        fetch = limit * 5 if python_filters else limit
        params.append(fetch)
        sql = (
            f"SELECT c.*, bm25(chunks_fts, {_BM25_WEIGHTS[0]}, {_BM25_WEIGHTS[1]}, {_BM25_WEIGHTS[2]}) AS bm "
            "FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
            f"WHERE {' AND '.join(clauses)} ORDER BY bm ASC LIMIT ?"
        )
        query_tokens = tokenise(query)
        results: list[SearchResult] = []
        for row in self._db.execute(sql, params):
            chunk = _row_to_chunk(row)
            result = chunk_to_search_result(chunk)
            if python_filters and not matches_filters(result, python_filters):
                continue
            doc_tokens = set(document_tokens(result))
            score = -float(row["bm"]) + symbol_path_bonus(query, query_tokens, result.metadata, doc_tokens)
            results.append(replace(result, score=score))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def close(self) -> None:
        with self._lock:
            self._db.close()


def _as_scalar(value: Any) -> Any:
    return value if isinstance(value, str | int | float | bool) or value is None else None


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        knowledge_id=row["knowledge_id"],
        source_path=row["source_path"],
        kind=row["kind"],
        symbol=row["symbol"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        text=row["text"],
        order=row["ord"] or 0,
        metadata=json.loads(row["metadata"]),
        chunk_id=row["chunk_id"],
        content_hash=row["content_hash"] or "",
        indexed_at=row["indexed_at"] or "",
    )


def _translate_filters(filters: dict[str, Any] | None) -> tuple[list[str], list[Any], dict[str, Any]]:
    """Split a filter dict into SQL clauses and a remainder handled in Python."""

    if not filters:
        return [], [], {}
    clauses: list[str] = []
    params: list[Any] = []
    python_filters: dict[str, Any] = {}
    for key, value in filters.items():
        if key in _PREFIX_FILTER_KEYS:
            clauses.append("c.source_path LIKE ? ESCAPE '\\'")
            params.append(_like_prefix(str(value)))
            continue
        if key not in _FILTER_COLUMNS:
            python_filters[key] = value
            continue
        if isinstance(value, list | tuple | set | frozenset):
            members = list(value)
            if not members:
                clauses.append("0")
                continue
            clauses.append(f"c.{key} IN ({', '.join('?' for _ in members)})")
            params.extend(members)
        else:
            clauses.append(f"c.{key} = ?")
            params.append(value)
    return clauses, params, python_filters


def _like_prefix(prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def bulk_replace(store: ChunkStore, chunks_by_file: Iterable[tuple[str, list[Chunk]]]) -> None:
    """Convenience for tests and importers: replace several files' chunks."""

    for file_key, chunks in chunks_by_file:
        store.replace_file_chunks(file_key, chunks)
