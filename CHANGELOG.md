# Changelog

All notable changes to Carsen are recorded here. The project follows British English in user-facing documentation.

## Unreleased

- Performance: the MCP runtime now builds the dense retriever, embedding provider and Qdrant client once per instance instead of rebuilding them (and reloading the embedding model) on every search.
- Retrieval: the configured reranker is now applied to hybrid search when `retrieval.rerank` is enabled; it was previously never invoked. The default reranker model is a genuine cross-encoder.
- Retrieval: `models.embedding.query_instruction` applies an asymmetric task prefix to queries only, improving recall with models such as Qwen3-Embedding.
- Retrieval: dense filters now share the sparse filter semantics (equality, list membership, path prefix) and Qdrant collections get keyword payload indexes on the filterable fields.
- Operations: a running MCP server refreshes its in-memory chunks and sparse index after any indexing run, so re-indexed content no longer requires a restart.
- Operations: dense-retrieval fallback is logged with a redacted reason and classified (`missing_dependency`, `configuration`, `service_unavailable`, `index`) in search diagnostics.
- Embeddings: added an optional `fastembed` (ONNX, no PyTorch) embedding provider for CPU-only deployments.
- Testing: added a retrieval-quality regression gate over a golden dataset of Carsen's own documentation; evaluation datasets can now reference source paths.
- Design: recorded a design for moving lexical retrieval onto Qdrant native sparse vectors.
- V1 retrieval integration: local CLI search now uses the instance runtime over canonical chunks with code/document corpus selection.
- Added MCP client/runtime end-to-end coverage for isolated knowledge instances and local tool behaviour.
- Added redacted search diagnostics for sparse fallback and hybrid candidate rankings.
- Added YAML evaluation dataset loading with Recall@k and MRR metrics for retrieval checks.
- Added `carsen evaluate` and a CLI reference covering search, evaluation and operational smoke procedures.
- Verified operational smoke paths for Docker-hosted Qdrant indexing/search and streamable HTTP MCP client calls.
- Documented the Carsen entry point, multi-instance model, isolation guarantees and LLM-independent retrieval approach.
- Added initial architecture decision records for instance isolation, Qdrant collection layout, canonical chunks, hybrid retrieval, citations and LLM independence.
- Captured current 0.1.0 progress for early adopters and maintainers.

## 0.1.0 - In progress

- Initial Carsen MCP package scaffold with `uv`-based development workflow.
- CLI support for creating, listing, validating, indexing and serving named knowledge instances.
- Per-instance configuration, registry conventions and status inspection.
- Qdrant-backed storage foundations with separate collections per knowledge instance.
- Canonical chunk model and local chunk store for re-use across indexing and retrieval.
- Source discovery, parsing and incremental indexing foundations for code and documents.
- Dense, sparse, exact and hybrid retrieval components with diagnostics and citation formatting foundations.
- MCP runtime support for stdio and HTTP transports.
- Docker Compose and systemd scaffolding for multiple isolated instances.
- Operational smoke procedure for local Qdrant and HTTP MCP deployments.
