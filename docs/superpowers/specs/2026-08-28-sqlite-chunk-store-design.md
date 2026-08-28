# SQLite chunk store with FTS5 sparse retrieval

## Status

Accepted. Supersedes `2026-08-28-qdrant-native-sparse-design.md` (option A), which
kept lexical search in a second Qdrant vector but left the chunk store loaded
entirely in memory.

## Goal

Replace the JSONL chunk store and the in-process Python BM25 index with one
per-instance SQLite database. This fixes both scaling limits in the current
runtime at once:

- `ChunkStore.load_all_chunks()` reads and JSON-parses every `chunks/*.jsonl`
  file on first access and keeps the full chunk list (with text) resident.
- `SparseRetriever` holds a second copy of the text as token counters.

SQLite is local-first, offline, needs no new heavy dependency, and its FTS5
module provides BM25 lexical search with per-column weighting.

## Layout

One database per instance: `<storage.data_directory>/chunks.sqlite3`.
`index_state.sqlite3` is unchanged.

```sql
CREATE TABLE chunks (
  rowid         INTEGER PRIMARY KEY,
  chunk_id      TEXT UNIQUE NOT NULL,
  knowledge_id  TEXT NOT NULL,
  source_path   TEXT NOT NULL,
  kind          TEXT,
  symbol        TEXT,
  start_line    INTEGER,
  end_line      INTEGER,
  ord           INTEGER,
  content_hash  TEXT,
  indexed_at    TEXT,
  text          TEXT NOT NULL,
  metadata      TEXT NOT NULL,          -- JSON blob, full round-trip fidelity
  -- promoted filter columns (also present in metadata)
  source_type    TEXT,
  document_type  TEXT,
  language       TEXT,
  repository_name TEXT
);
CREATE INDEX idx_chunks_source    ON chunks(source_path);
CREATE INDEX idx_chunks_symbol    ON chunks(symbol);
CREATE INDEX idx_chunks_knowledge ON chunks(knowledge_id);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
  tok_text,        -- code-aware tokenised projection of text (+ symbol, path, kind)
  tok_symbol,      -- tokenised symbol
  tok_path,        -- tokenised source path
  content='',      -- contentless
  contentless_delete=1,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);  -- holds 'generation'
```

`chunks_fts.rowid` equals `chunks.rowid`. Both tables are written in one
transaction per file.

## Tokenisation

The existing `carsen_mcp.retrieval.sparse.tokenise()` (dotted identifiers,
snake/camel splitting, light stemming) is reused to build `tok_text` /
`tok_symbol` / `tok_path` at write time, and to build the FTS `MATCH` query at
read time. FTS5's `unicode61` tokenizer then only splits on whitespace, so the
code-aware behaviour is preserved without a C extension.

## Sparse retrieval

```sql
SELECT c.*, bm25(chunks_fts, 1.0, 8.0, 2.0) AS bm
FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid
WHERE chunks_fts MATCH :match
  AND (:source_type IS NULL OR c.source_type IN (:source_types))
  AND (:path_prefix  IS NULL OR c.source_path LIKE :path_prefix || '%')
ORDER BY bm DESC LIMIT :limit;
```

- Column weights approximate the current scorer's symbol/path emphasis.
- `bm25()` returns lower-is-better; the retriever negates it to a positive score.
- The current hand-tuned bonuses (exact symbol match `+10`, partial symbol `+3`,
  path substring `+1`, XML-path heuristics) are re-applied in Python on the
  returned candidate set (tens of rows), not lost.
- Filters map: scalar -> `=`, list -> `IN`, `path_prefix` / `source_path_prefix`
  -> `LIKE 'prefix%'`. Same predicate set as the Qdrant dense filter translator.

## ChunkStore API

Method names stay stable so the indexer and runtime change minimally:

- `replace_file_chunks(source_path, chunks)` — one transaction: delete existing
  rows for the path (chunks + FTS), insert new rows, bump `generation`.
- `delete_file_chunks(source_path)`, `delete_chunk_file` (path-compat shim),
  `prune_unknown_sources(knowledge_id, allowed)` — as today, SQL-backed.
- `generation()` — reads `meta.generation` instead of the `.generation` file.
- `load_all_chunks()` — streams rows (kept for `reembed` and tests).

New, replacing linear scans in the runtime:

- `get_chunk(chunk_id)`, `chunk_by_source(source_path)`
- `iter_symbol(symbol)` for `find_symbol`
- `search_sparse(query, limit, filters)` returning `SearchResult`s
- `count(knowledge_id)`, `source_count(knowledge_id)` for `knowledge_info`

## Runtime changes

- `InstanceRuntime` drops `_chunks_cache`, `_sparse_cache`, `_symbol_index`,
  `_chunk_by_id/_chunk_by_source` and the generation-polling reload logic:
  SQLite is the shared source of truth, so a served instance sees an indexing
  run's writes immediately (WAL mode, `PRAGMA synchronous=NORMAL`).
- `_sparse()` delegates to `store.search_sparse`.
- `find_symbol`, `_find_chunk`, `knowledge_info` become direct queries.
- `_dense_retriever()` / reranker caching are unchanged.
- `SourceExpander` / `get_related_sources` read the small set of rows they need
  for one source path rather than the whole corpus.

## Migration

On `ChunkStore` open: if `chunks.sqlite3` is absent but a legacy `chunks/`
directory with `*.jsonl` files exists, import them once into SQLite and log a
one-line notice. The legacy directory is left in place; `docs` describes
deleting it. `carsen index --force` and `carsen reembed` also rebuild cleanly.
No config changes.

## Keeping the in-memory retriever

`SparseRetriever` (list-backed) and its unit tests stay as the reference
implementation and for callers that pass an explicit chunk list. `tokenise()`
moves to being the shared tokeniser for both paths.

## Risks

- FTS5 must be compiled into SQLite. Checked on the dev target (3.53, FTS5
  present); add a clear error at store creation if the `fts5` module is missing,
  pointing to `dense_candidates: 0` being unaffected only if it, too, needs FTS
  — it does, so document the requirement.
- BM25 ranking differs from the current scorer. The retrieval regression gate
  (`tests/test_retrieval_regression.py`) covers this; thresholds may need a
  one-time adjustment recorded in the changelog.
- Concurrent writers (a watch thread) plus readers (the server): WAL mode and a
  short `busy_timeout` handle this; writes are per-file and quick.

## Validation

- Port `tests/test_mcp_runtime.py` fixtures to the SQLite store (the `populate`
  helper changes, assertions do not).
- New `ChunkStore` unit tests: round-trip fidelity, per-file replace, prune,
  generation, legacy import, sparse query with filters.
- `tests/test_retrieval_regression.py` must still pass (adjust thresholds once
  if needed).
- Operational smoke unchanged.
