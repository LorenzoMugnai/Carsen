# Configuration

Ariadne uses YAML. A file represents one knowledge instance and is validated by `ariadne_mcp.config`.

## Top-level fields

```yaml
knowledge:
  id: example
  name: Example Knowledge Base
  description: Example Ariadne knowledge instance.
server:
  transport: http
  host: 127.0.0.1
  port: 8765
storage:
  qdrant_url: http://127.0.0.1:6333
  collection: kb_example
  data_directory: "${HOME}/.local/share/ariadne/example"
models:
  embedding:
    provider: sentence_transformers
    model: Qwen/Qwen3-Embedding-0.6B
    dimensions: 1024
    device: auto
  reranker:
    provider: sentence_transformers
    model: Qwen/Qwen3-Reranker-0.6B
retrieval:
  dense_candidates: 40
  sparse_candidates: 40
  fused_candidates: 30
  final_results: 8
  fusion: rrf
  max_results_per_source: 3
indexing:
  incremental: true
  follow_symlinks: false
sources:
  code: []
  documents: []
policy:
  allow_external_llm: false
```

## Field notes

- `knowledge.id` must be filesystem-safe. If `name` is absent, it defaults to the ID.
- `server.transport` supports `stdio` and `http`; HTTP is served as streamable HTTP on `/mcp`.
- `storage.collection` defaults to `kb_<knowledge_id>`. `storage.data_directory` defaults under `~/.local/share/ariadne/<id>`.
- Environment variables and `~` are expanded in YAML values. Relative paths are resolved against the YAML file location.
- `retrieval.fusion` currently accepts only `rrf`.
- `sources.code` and `sources.documents` contain entries with `path`, optional `repository_name`, optional `type` and optional `tags`.
- `policy.allow_external_llm` is metadata for clients; it is not an enforcement boundary.
