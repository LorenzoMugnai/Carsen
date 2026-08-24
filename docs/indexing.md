# Indexing

Indexing is invoked with:

```bash
ariadne index NAME
ariadne index --config path/to/config.yaml
ariadne index NAME --force
ariadne index NAME --embed
```

The indexer discovers files under configured `sources.code` and `sources.documents`, computes file records, classifies files as new, unchanged, changed or deleted, then reparses only the required files unless `--force` is used.

`--embed` additionally embeds the canonical chunks and upserts them into the instance-specific Qdrant collection. Without `--embed`, Ariadne still updates the canonical chunk store and sparse/MCP fallback retrieval can use those chunks.

## Discovery

Defaults ignore common generated or dependency directories such as `.git`, `.venv`, `node_modules`, `__pycache__`, `build` and `dist`. Binary extension ignores include `.pyc`, `.so`, `.dll` and `.dylib`. Symlink following is disabled by default.

## Canonical chunks

Parsed content becomes deterministic `Chunk` records containing:

- `knowledge_id`, `source_path`, `kind`, `symbol`, line range and order.
- `text` and `metadata`.
- stable `chunk_id` based on identity and boundaries.
- `content_hash` based on current text.
- `indexed_at` timestamp.

This separates canonical identity from content changes, enabling re-embedding or invalidation without changing the source identifier when boundaries remain stable.

## Re-embedding and deletion

Changing the embedding model does not require reparsing source files if canonical chunks are still valid:

```bash
ariadne reembed NAME
```

To remove the local chunk store, incremental state and dense collection for an instance:

```bash
ariadne delete-index NAME
```
