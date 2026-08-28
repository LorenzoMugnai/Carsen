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
  tuning:
    hnsw_ef: null
    quantization: null
    quantization_always_ram: true
    rescore: true
    oversampling: 2.0
    on_disk_vectors: false
    on_disk_payload: false
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
    model: BAAI/bge-reranker-v2-m3
retrieval:
  dense_candidates: 40
  sparse_candidates: 40
  fused_candidates: 30
  final_results: 8
  fusion: rrf
  max_results_per_source: 3
  rerank: false
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
  max_chunk_tokens: 1200
  chunk_overlap_tokens: 100
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
- `storage.tuning` holds optional Qdrant performance knobs. All defaults keep current behaviour, and they only matter for a real Qdrant server (embedded local Qdrant does brute-force search and ignores them). See [Tuning Qdrant for large collections](#tuning-qdrant-for-large-collections).
- Environment variables and `~` are expanded in YAML values. Relative paths are resolved against the YAML file location.
- `retrieval.fusion` currently accepts only `rrf`.
- `retrieval.rerank` is off by default. When enabled, fused candidates are reranked with `models.reranker` before diversification; the `sentence_transformers` reranker provider loads a cross-encoder model on the first search and expects a genuine cross-encoder checkpoint such as `BAAI/bge-reranker-v2-m3`. A reranker failure falls back to the fused order and is reported in `search_debug` diagnostics.
- Set `retrieval.dense_candidates: 0` for sparse/exact-only operation. In this mode Carsen does not load the embedding model during search, which is useful on CPU-only or low-memory machines.
- `models.embedding.batch_size` bounds local embedding calls during indexing and provider encoding. Lower it for memory-constrained machines. `models.embedding.max_seq_length` caps Sentence Transformers token length so oversized chunks are truncated before encoding.
- `models.embedding.query_instruction` is prepended to search queries only, never to indexed documents. Asymmetric retrieval models (Qwen3-Embedding, E5, BGE) expect a task instruction on the query side; leave it unset for symmetric models.
- `models.embedding.provider` selects the embedding backend:
    - `sentence_transformers` — local PyTorch models.
    - `fastembed` — local ONNX models, no PyTorch; install `carsen-mcp[fastembed]` and set an explicit `dimensions`.
    - `openai` / `openai_compatible` — an OpenAI-style `/embeddings` HTTP endpoint (OpenAI, Ollama, TEI, Infinity). Set `base_url` (defaulted for `openai`), an explicit `dimensions` matching the endpoint, optional `api_key_env` naming the environment variable holding the key (`OPENAI_API_KEY` by default for `openai`), and `timeout`.
    - `fake` — deterministic vectors for tests.
- Embeddings and Qdrant are optional for indexing and MCP retrieval. Plain `carsen index` builds local chunks for sparse/exact search. `carsen index --embed` warns if the optional dense phase fails, while `carsen reembed` remains dense-only and reports failures as errors.
- `indexing.watch` enables foreground/background filesystem watch indexing. `watch_debounce_seconds` coalesces rapid file events, and `watch_embed` also refreshes dense vectors after watched changes.
- `parsing.documents` controls optional Docling document parsing. PDF parsing defaults to fast text extraction: OCR and table structure are disabled, and backend text is preferred.
- `parsing.max_chunk_tokens` (default 1200, roughly 4 chars per token) splits any parser chunk larger than the budget into overlapping line-aligned sub-chunks; `parsing.chunk_overlap_tokens` (default 100) sets the overlap. Sub-chunks carry `parent_chunk_id`, `sub_chunk_index` and `sub_chunk_count` metadata, and `order` is renumbered densely per file. Set `max_chunk_tokens: null` to keep whole parser chunks.
- `sources.code` and `sources.documents` contain entries with `path`, optional `repository_name`, optional `type` and optional `tags`.
- Sources may also use `repo_url`, `ref` and `subpath` instead of `path` for public Git repositories. Carsen clones/fetches these into the instance cache under `storage.data_directory/remotes/` and pins online citations to the checked-out commit. If both `repo_url` and `path` are present, `repo_url` takes precedence.
- `policy.allow_external_llm` is metadata for clients; it is not an enforcement boundary.

## Citation behavior

Local source paths are always preserved for citations. For public GitHub and GitLab repositories, Carsen adds `citation_url` metadata with commit-pinned line anchors. Private or unrecognized remotes do not receive online URLs; sparse/exact retrieval still works with local citation text.

```yaml
sources:
  code:
    - repo_url: https://github.com/org/repo.git
      ref: main
      subpath: src
      repository_name: org/repo
```

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

Interactive indexing performs a compact noisy-file preflight before parsing. If Carsen finds likely low-value formats such as binary/data files, archives, logs, cache/build directories or media assets, it shows numbered categories with counts, total size, extensions and a few examples. Select categories to add them to `indexing.ignored_extensions` or `indexing.ignored_directories`; Carsen persists the updated YAML and applies the ignores to the same run. Use `carsen index NAME --yes` to skip the prompt for automation.

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

## Tuning Qdrant for large collections

`storage.tuning` exposes Qdrant's performance settings. Every option is optional and the defaults change nothing, so small instances need no tuning. These settings apply only to a real Qdrant server: embedded local Qdrant (`qdrant_path`) performs exact brute-force search and ignores them.

```yaml
storage:
  tuning:
    hnsw_ef: 128
    quantization: scalar
    quantization_always_ram: true
    rescore: true
    oversampling: 2.0
    on_disk_vectors: false
    on_disk_payload: false
```

| Field | Effect | When to change it |
| --- | --- | --- |
| `hnsw_ef` | Query-time breadth of the HNSW graph search. Higher means more accurate recall and slower queries. Unset uses Qdrant's collection default. | Raise to `128`–`256` if dense recall feels low on a big collection; lower it to speed up queries when recall is already good. |
| `quantization` | Compresses stored vectors. `scalar` uses int8 (about 4x smaller, minimal accuracy loss). `binary` uses 1 bit per dimension (about 32x smaller, only worthwhile for high-dimensional models and always with `rescore`). Unset keeps full-precision vectors. | Enable `scalar` once a collection no longer fits comfortably in RAM. |
| `quantization_always_ram` | Keeps the compressed vectors in RAM even when the originals are on disk. | Leave `true` unless RAM is very tight. |
| `rescore` | After the quantized shortlist, re-rank candidates against the original full-precision vectors. | Keep `true` with quantization; it restores most of the lost accuracy at small cost. |
| `oversampling` | How many extra quantized candidates to pull before rescoring (`2.0` = fetch 2x `limit`). | Raise if quantized recall is poor; lower to reduce work. |
| `on_disk_vectors` | Stores the original vectors on disk instead of RAM. | For collections far larger than memory, usually together with `quantization`. |
| `on_disk_payload` | Stores chunk payloads (text, metadata) on disk. | For very large corpora where payload size dominates memory. |

`hnsw_ef`, `rescore` and `oversampling` take effect immediately. `quantization`, `on_disk_vectors` and `on_disk_payload` are collection-creation settings, so run `carsen reembed NAME` after changing them to recreate the collection.

A typical progression for a growing shared instance: start with defaults, add `hnsw_ef: 128` if recall drops, then `quantization: scalar` when the collection outgrows RAM, then the `on_disk` options for larger-than-memory corpora.
