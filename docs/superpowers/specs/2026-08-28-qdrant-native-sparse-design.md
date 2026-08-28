# Qdrant-native sparse retrieval design

## Status

Superseded by `2026-08-28-sqlite-chunk-store-design.md`. That approach moves both
the chunk store and lexical search into one per-instance SQLite database with
FTS5, which also removes the in-memory chunk load this design left in place and
avoids adding the `fastembed` dependency. Kept for the analysis below.

## Goal

Replace Carsen's in-process Python BM25 implementation with Qdrant's native
sparse vectors, so that a single Qdrant query serves the hybrid retrieval path
with server-side filtering and fusion. This removes the largest scaling limit in
the current runtime: every served instance loads all chunks into memory and
rebuilds a lexical index at startup.

## Current state

- `carsen_mcp/retrieval/sparse.py` implements a BM25-like scorer over
  `SearchResult` objects built from every persisted chunk.
- `InstanceRuntime.chunks` calls `ChunkStore.load_all_chunks()`, which reads and
  JSON-parses every `*.jsonl` file in the instance chunk directory on first
  access, then keeps the full list (with chunk text) resident.
- `SparseRetriever` holds a second copy of the text in `SparseDocument` token
  counters. Memory scales with corpus size; startup scales with chunk count.
- Hybrid search issues one Qdrant dense query plus one in-memory sparse query and
  fuses the two candidate lists with reciprocal rank fusion in Python.
- Filters are evaluated twice with two code paths (`retrieval/filters.py` for
  sparse, `storage/qdrant.py:_filter` for dense).

## Target state

- Each chunk is stored in Qdrant once, carrying both a dense vector and a named
  sparse vector.
- Sparse vectors are produced by a sparse embedding model (BM25/BM42 or SPLADE)
  via `fastembed`, which `qdrant-client` already depends on.
- Retrieval uses Qdrant's Query API with prefetch + fusion (`Fusion.RRF`) so a
  single request returns fused candidates, filtered server-side.
- The Python `SparseRetriever` remains only as a no-Qdrant fallback for
  `dense_candidates: 0` / offline operation, reading from the local chunk store
  as it does today.

## Design

### Storage

`QdrantVectorStore` gains a sparse vector configuration:

- `create_collection` / `recreate_collection` declare
  `sparse_vectors_config={"text": SparseVectorParams(modifier=Modifier.IDF)}`
  alongside the existing dense `VectorParams`.
- `upsert_chunks` accepts an optional `sparse_vectors: list[SparseVector]`
  parameter and attaches them to each point under the `text` name.
- Existing dense-only collections remain valid; a collection without a sparse
  vector simply skips the sparse prefetch at query time.

### Indexing

- `carsen_mcp/embeddings/` gains a `SparseEmbeddingProvider` protocol and a
  `FastEmbedSparseProvider` implementation (lazy import of `fastembed`).
- `index_vectors_for_config` computes sparse vectors in the same batch loop that
  computes dense vectors and passes both to `upsert_chunks`.
- A new `models.sparse` config block selects the sparse model
  (`Qdrant/bm25` default) and is optional; when absent, indexing writes
  dense-only points and retrieval uses the Python sparse fallback.
- `carsen reembed` rebuilds both vector types from canonical chunks, preserving
  the "canonical chunks are the source of truth" principle.

### Retrieval

- `DenseRetriever` is joined by a `QdrantHybridRetriever` that issues one
  `query_points` call with:
  - `prefetch=[Prefetch(query=<dense>, using="", limit=dense_candidates),
    Prefetch(query=<sparse>, using="text", limit=sparse_candidates)]`
  - `query=FusionQuery(fusion=Fusion.RRF)`
  - `query_filter=_filter(filters)` (the unified filter translator).
- `HybridRetriever` (Python fusion) stays for the fallback path and for unit
  tests that do not require a Qdrant service.
- `InstanceRuntime._search_with_debug` selects the Qdrant hybrid path when a
  sparse vector is configured and the collection is reachable, and falls back to
  the current behaviour otherwise, reporting the mode in diagnostics.

### Diagnostics

- `search_debug` reports `mode: "qdrant_hybrid"` with per-prefetch candidate
  counts pulled from the Qdrant response, keeping the redaction rules already in
  place.

## Migration and compatibility

- No breaking config changes: `models.sparse` is additive and optional.
- Collections indexed before this change keep working as dense-only; a
  `carsen reembed` upgrades them in place.
- The Python `SparseRetriever` and its tests are retained, so
  `dense_candidates: 0` and no-Qdrant deployments are unaffected.

## Risks

- `fastembed` model download on first sparse index; document it and allow a
  pre-download step, mirroring the embedding model guidance.
- BM25 scoring differences versus the current hand-tuned scorer (symbol and
  path boosts). Mitigate by keeping the symbol/path boosts as payload-based
  score adjustments or by accepting the change and recording it via the
  retrieval evaluation dataset.
- Local (in-memory) Qdrant supports sparse vectors but not payload indexes;
  behaviour parity for tests needs a check.

## Out of scope

- Replacing the dense embedding provider.
- Changing chunk boundaries or sizes (tracked separately).

## Validation

- New unit tests for sparse collection creation, dual upsert and the fused
  query path against `QdrantClient(":memory:")`.
- Extend the retrieval evaluation dataset and record Recall@k / MRR before and
  after the switch.
- Operational smoke: `carsen index --embed` then `carsen search --debug`
  against a Docker Qdrant, asserting `mode: qdrant_hybrid`.
