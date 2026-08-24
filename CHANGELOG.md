# Changelog

All notable changes to Ariadne are recorded here. The project follows British English in user-facing documentation.

## Unreleased

- Documented the Ariadne entry point, multi-instance model, isolation guarantees and LLM-independent retrieval approach.
- Added initial architecture decision records for instance isolation, Qdrant collection layout, canonical chunks, hybrid retrieval, citations and LLM independence.
- Captured current 0.1.0 progress for early adopters and maintainers.

## 0.1.0 - In progress

- Initial Ariadne MCP package scaffold with `uv`-based development workflow.
- CLI support for creating, listing, validating, indexing and serving named knowledge instances.
- Per-instance configuration, registry conventions and status inspection.
- Qdrant-backed storage foundations with separate collections per knowledge instance.
- Canonical chunk model and local chunk store for re-use across indexing and retrieval.
- Source discovery, parsing and incremental indexing foundations for code and documents.
- Dense, sparse, exact and hybrid retrieval components with diagnostics and citation formatting foundations.
- MCP runtime support for stdio and HTTP transports.
- Docker Compose and systemd scaffolding for multiple isolated instances.
