<div align="center">

<img src="docs/assets/logo.png" alt="Carsen logo" width="288" />

<h1>Carsen</h1>

<p><em>Local-first MCP knowledge engine for indexed code and document collections.</em></p>

<p>
  <a href="https://github.com/LorenzoMugnai/Carsen/actions/workflows/ci.yml">
    <img alt="GitHub Actions CI" src="https://github.com/LorenzoMugnai/Carsen/actions/workflows/ci.yml/badge.svg?branch=main">
  </a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="carsen-mcp v0.1.0" src="https://img.shields.io/badge/carsen--mcp-v0.1.0-7c3aed?style=flat-square">
  <img alt="MCP enabled" src="https://img.shields.io/badge/MCP-enabled-111827?style=flat-square">
  <img alt="Ruff" src="https://img.shields.io/badge/Ruff-linting-2C6BED?style=flat-square&logo=ruff&logoColor=white">
  <img alt="mypy" src="https://img.shields.io/badge/mypy-checked-2A6DB2?style=flat-square&logo=mypy&logoColor=white">
  <img alt="local-first" src="https://img.shields.io/badge/local--first-yes-0F766E?style=flat-square">
  <img alt="Qdrant" src="https://img.shields.io/badge/Qdrant-backed-FF6F00?style=flat-square&logo=qdrant&logoColor=white">
</p>

</div>

Carsen is a local-first Model Context Protocol (MCP) knowledge engine for serving indexed code and document collections to any MCP-capable client. It keeps retrieval, citation metadata and operational state in Carsen; the generative LLM remains replaceable.

## Documentation

- [Quickstart for academic users](docs/quickstart.md)
- [Core concepts](docs/concepts.md)
- [Full documentation index](docs/index.md)

To build the website locally:

```bash
uv pip install -e '.[docs]'
uv run mkdocs serve
```

## Core ideas

- **Multi-instance architecture:** each knowledge base is a named Carsen instance with its own configuration, sources, Qdrant collection, state directory and MCP endpoint.
- **LLM independence:** Carsen retrieves and cites context; answer generation belongs to the client or model you choose.
- **Isolation by default:** separate instances avoid accidental mixing of projects, tenants or trust boundaries.
- **Hybrid retrieval:** dense, sparse and exact retrieval paths can be combined over canonical chunks with metadata-backed citations.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra test
uv run carsen status
```

Run Qdrant locally, for example with Docker:

```bash
docker run --rm -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

## Create, configure, index and serve

Create a named instance and edit the generated YAML in your Carsen config directory:

```bash
uv run carsen create my-project --code ./src --documents ./docs
uv run carsen validate my-project
uv run carsen index my-project
```

Use `--embed` to also create or update the configured Qdrant collection during indexing:

```bash
uv run carsen index my-project --embed
uv run carsen reembed my-project
uv run carsen delete-index my-project
```

Serve over stdio for local MCP clients:

```bash
uv run carsen serve my-project --transport stdio
```

Serve over HTTP for clients that connect to a host and port:

```bash
uv run carsen serve my-project --transport http
```

Use `uv run carsen list` and `uv run carsen status my-project` to inspect registered instances. Example configurations live in `configs/examples/`.

## Remote access

For remote machines, bind Carsen to `127.0.0.1` on the server and tunnel the port over SSH:

```bash
ssh -L 8765:127.0.0.1:8765 user@example.org
```

Point the MCP client at the local forwarded endpoint. This keeps the Carsen HTTP service off the public network while allowing remote use.

## Deployment pointers

- Docker: see `Dockerfile` and `docker-compose.example.yml` for one Qdrant service with multiple isolated Carsen instances.
- systemd: see `deployment/systemd/carsen@.service` for a per-instance service template.

## Tests

```bash
uv run pytest
```

## Architecture decisions

- [ADR 0001: Separate knowledge instances](docs/adr/0001-separate-knowledge-instances.md)
- [ADR 0002: Qdrant per-instance collections](docs/adr/0002-qdrant-per-instance-collections.md)
- [ADR 0003: Canonical chunk store](docs/adr/0003-canonical-chunk-store.md)
- [ADR 0004: Hybrid dense/sparse retrieval](docs/adr/0004-hybrid-dense-sparse-retrieval.md)
- [ADR 0005: Metadata-backed citations](docs/adr/0005-metadata-backed-citations.md)
- [ADR 0006: Generative LLM independence](docs/adr/0006-generative-llm-independence.md)
