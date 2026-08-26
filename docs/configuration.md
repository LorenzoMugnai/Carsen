# Configuration

Carsen uses YAML. A file represents one knowledge instance and is validated by `carsen_mcp.config`.

## Top-level fields

```yaml
knowledge:
  id: example
  name: Example Knowledge Base
  description: Example Carsen knowledge instance.
server:
  transport: http
  host: 127.0.0.1
  port: 8765
storage:
  qdrant_url: http://127.0.0.1:6333
  # qdrant_path overrides qdrant_url and uses embedded local Qdrant storage.
  # qdrant_path: "${HOME}/.local/share/carsen/example/qdrant"
  collection: kb_example
  data_directory: "${HOME}/.local/share/carsen/example"
models:
  embedding:
    provider: sentence_transformers
    model: Qwen/Qwen3-Embedding-0.6B
    dimensions: 1024
    device: auto
    batch_size: 8
    max_seq_length: 1024
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
  watch: false
  watch_debounce_seconds: 10.0
  watch_embed: false
parsing:
  documents:
    ocr: false
    table_structure: false
    force_backend_text: true
sources:
  code: []
  documents: []
policy:
  allow_external_llm: false
```

## Field notes

- `knowledge.id` must be filesystem-safe. If `name` is absent, it defaults to the ID.
- `server.transport` supports `stdio` and `http`; HTTP is served as streamable HTTP on `/mcp`.
- `storage.collection` defaults to `kb_<knowledge_id>`. `storage.data_directory` defaults under `~/.local/share/carsen/<id>`.
- `storage.qdrant_url` points to a running Qdrant service. If Docker or a Qdrant server is unavailable, set `storage.qdrant_path` (for example `~/.local/share/carsen/<id>/qdrant`) to use embedded local Qdrant storage. When set, `qdrant_path` overrides `qdrant_url`.
- Environment variables and `~` are expanded in YAML values. Relative paths are resolved against the YAML file location.
- `retrieval.fusion` currently accepts only `rrf`.
- Set `retrieval.dense_candidates: 0` for sparse/exact-only operation. In this mode Carsen does not load the embedding model during search, which is useful on CPU-only or low-memory machines.
- `models.embedding.batch_size` bounds local embedding calls during indexing and provider encoding. Lower it for memory-constrained machines. `models.embedding.max_seq_length` caps Sentence Transformers token length so oversized chunks are truncated before encoding.
- Embeddings and Qdrant are optional for indexing and MCP retrieval. Plain `carsen index` builds local chunks for sparse/exact search. `carsen index --embed` warns if the optional dense phase fails, while `carsen reembed` remains dense-only and reports failures as errors.
- `indexing.watch` enables foreground/background filesystem watch indexing. `watch_debounce_seconds` coalesces rapid file events, and `watch_embed` also refreshes dense vectors after watched changes.
- `parsing.documents` controls optional Docling document parsing. PDF parsing defaults to fast text extraction: OCR and table structure are disabled, and backend text is preferred.
- `sources.code` and `sources.documents` contain entries with `path`, optional `repository_name`, optional `type` and optional `tags`.
- `policy.allow_external_llm` is metadata for clients; it is not an enforcement boundary.

## Running without GPU or Qdrant server

Carsen has two layers of retrieval:

1. **Local chunk retrieval** uses the canonical chunk store on disk. It supports sparse lexical search, exact symbol/path lookup, citations and source expansion. It does not need a GPU, an embedding model or a Qdrant server.
2. **Dense retrieval** adds semantic vector search. It needs an embedding model and a Qdrant collection. This can improve meaning-based queries, but it is optional.

For the most portable setup, start with sparse/exact-only mode:

```yaml
retrieval:
  dense_candidates: 0
  sparse_candidates: 40
  final_results: 8
```

With `dense_candidates: 0`, `carsen search` and the MCP runtime do not load the embedding model during search. This is the recommended mode for CPU-only laptops, low-memory machines and quick setup on a new computer.

Indexing works in the same layered way:

```bash
carsen index NAME
```

This command builds the local chunk store. It is enough for MCP tools such as `search_knowledge`, `search_code`, `find_symbol`, `read_source` and related-source lookup.

Dense indexing is an optional extra:

```bash
carsen index NAME --embed
```

If the dense phase fails because the model is too large, Qdrant is unavailable or the machine has insufficient memory, Carsen keeps the chunk index and prints a warning. Sparse/exact search remains available. Use `carsen reembed NAME` only when you specifically want to rebuild dense vectors; unlike `index --embed`, `reembed` is dense-only and fails if embeddings or Qdrant are unavailable.

## Choosing a Qdrant mode

Use one of these storage modes for dense retrieval:

### Server mode

Server mode expects Qdrant to be running separately, commonly with Docker:

```yaml
storage:
  qdrant_url: http://127.0.0.1:6333
```

Choose this when you already operate Qdrant as a service or want to share one Qdrant process across multiple tools.

### Embedded local mode

Embedded mode stores Qdrant data in a local directory and does not require Docker:

```yaml
storage:
  qdrant_path: "${HOME}/.local/share/carsen/example/qdrant"
```

When `qdrant_path` is set, Carsen ignores `qdrant_url` for dense indexing/search and opens Qdrant through the local Python client. This is the easiest dense setup for a single-user local machine.

## CPU-friendly embedding settings

If you enable dense retrieval on a CPU-only machine, keep batches and sequence length modest:

```yaml
models:
  embedding:
    provider: sentence_transformers
    model: Qwen/Qwen3-Embedding-0.6B
    dimensions: 1024
    device: cpu
    batch_size: 1
    max_seq_length: 512
```

`batch_size` controls how many chunks are embedded at once. Lower values use less memory and are slower. `max_seq_length` limits how much text each chunk sends into the transformer model. Lower values avoid very large attention buffers, especially for long XML, HTML or generated files.

If you do not need semantic vector search, prefer `retrieval.dense_candidates: 0` and skip `--embed` entirely.
