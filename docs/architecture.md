# Architecture

Ariadne is organised around one configuration file per knowledge instance. Each instance has its own identifier, storage directory, optional Qdrant collection name and configured source roots.

```mermaid
flowchart LR
  YAML[Instance YAML] --> Config[Config validation]
  Config --> CLI[ariadne CLI]
  CLI --> Indexer[Incremental indexer]
  Indexer --> Parsers[Parsers]
  Parsers --> Chunks[Canonical chunks]
  Chunks --> Store[Local chunk store]
  Store --> Runtime[MCP runtime]
  Runtime --> Tools[MCP tools]
```

## Main packages

- `ariadne_mcp.config`: Pydantic models for YAML loading, environment expansion and path resolution.
- `ariadne_mcp.registry`: local registry discovery and starter configuration creation.
- `ariadne_mcp.ingestion`: file discovery, Git metadata, incremental state and indexing.
- `ariadne_mcp.parsers`: Python, Markdown, document and text parsing.
- `ariadne_mcp.chunks`: deterministic chunk model and local chunk persistence.
- `ariadne_mcp.retrieval`: sparse retrieval, dense/hybrid abstractions, RRF fusion, filters and diagnostics.
- `ariadne_mcp.citations`: metadata-backed citation formatting.
- `ariadne_mcp.mcp`: MCP server factory and per-instance runtime.

## Isolation model

Multi-instance isolation is achieved by namespacing chunks with `knowledge.id`, deriving instance-specific defaults for `storage.collection` and `storage.data_directory`, and serving exactly one `AriadneConfig` per MCP runtime. Instances may share the same process environment, but their persisted chunk state and metadata are separated by configuration.
