# Indexing

Indexing is invoked with:

```bash
carsen index NAME
carsen index --config path/to/config.yaml
carsen index NAME --force
carsen index NAME --embed
carsen watch NAME
```

The indexer discovers files under configured `sources.code` and `sources.documents`, computes file records, classifies files as new, unchanged, changed or deleted, then reparses only the required files unless `--force` is used.

`--embed` additionally embeds the canonical chunks and upserts them into the instance-specific Qdrant collection. Without `--embed`, Carsen still updates the canonical chunk store and sparse/MCP fallback retrieval can use those chunks.

```mermaid
flowchart LR
    A[Configured source roots] --> B[Discover files]
    B --> C[Classify new, changed, unchanged or deleted]
    C --> D[Parse required files]
    D --> E[Create canonical chunks]
    E --> F[Store chunks and metadata locally]
    E --> G{--embed?}
    G -- No --> H[Local sparse and MCP fallback retrieval]
    G -- Yes --> I[Create embeddings]
    I --> J[Upsert vectors into instance Qdrant collection]
    F --> K[Citations and source tracing]
    J --> L[Dense semantic retrieval]
```

This flow is similar to building a catalogue for a research archive. Carsen first records what source material exists, then stores small cited records, and only then adds semantic vectors when dense search is requested.

## Discovery

Defaults ignore common generated or dependency directories such as `.git`, `.venv`, `node_modules`, `__pycache__`, `build` and `dist`. Binary extension ignores include `.pyc`, `.so`, `.dll` and `.dylib`. Symlink following is disabled by default.

## Watch indexing

Set `indexing.watch: true` to enable automatic indexing while serving, or run `carsen watch NAME` as a foreground watcher. File events are debounced by `indexing.watch_debounce_seconds` and coalesced into a single index pass. Set `indexing.watch_embed: true` to also refresh dense vectors after watched changes.

## Canonical chunks

Parsed content becomes deterministic `Chunk` records containing:

- `knowledge_id`, `source_path`, `kind`, `symbol`, line range and order.
- `text` and `metadata`.
- stable `chunk_id` based on identity and boundaries.
- `content_hash` based on current text.
- `indexed_at` timestamp.

This separates canonical identity from content changes, enabling re-embedding or invalidation without changing the source identifier when boundaries remain stable.

The local chunk store is also the fallback retrieval source for `carsen search` and the MCP runtime when dense vector services or models are unavailable.

## Re-embedding and deletion

Changing the embedding model does not require reparsing source files if canonical chunks are still valid:

```bash
carsen reembed NAME
```

To remove the local chunk store, incremental state and dense collection for an instance:

```bash
carsen delete-index NAME
```
