# Indexing

Indexing is invoked with:

```bash
ariadne index NAME
ariadne index --config path/to/config.yaml
ariadne index NAME --force
```

The indexer discovers files under configured `sources.code` and `sources.documents`, computes file records, classifies files as new, unchanged, changed or deleted, then reparses only the required files unless `--force` is used.

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
