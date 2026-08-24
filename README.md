# Ariadne

Ariadne is a local-first Model Context Protocol (MCP) knowledge engine for serving indexed code and document collections to any MCP-capable client. It keeps retrieval, citation metadata and operational state in Ariadne; the generative LLM remains replaceable.

## Core ideas

- **Multi-instance architecture:** each knowledge base is a named Ariadne instance with its own configuration, sources, Qdrant collection, state directory and MCP endpoint.
- **LLM independence:** Ariadne retrieves and cites context; answer generation belongs to the client or model you choose.
- **Isolation by default:** separate instances avoid accidental mixing of projects, tenants or trust boundaries.
- **Hybrid retrieval:** dense, sparse and exact retrieval paths can be combined over canonical chunks with metadata-backed citations.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra test
uv run ariadne status
```

Run Qdrant locally, for example with Docker:

```bash
docker run --rm -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

## Create, configure, index and serve

Create a named instance and edit the generated YAML in your Ariadne config directory:

```bash
uv run ariadne create my-project --code ./src --documents ./docs
uv run ariadne validate my-project
uv run ariadne index my-project
```

Use `--embed` to also create or update the configured Qdrant collection during indexing:

```bash
uv run ariadne index my-project --embed
uv run ariadne reembed my-project
uv run ariadne delete-index my-project
```

Serve over stdio for local MCP clients:

```bash
uv run ariadne serve my-project --transport stdio
```

Serve over HTTP for clients that connect to a host and port:

```bash
uv run ariadne serve my-project --transport http
```

Use `uv run ariadne list` and `uv run ariadne status my-project` to inspect registered instances. Example configurations live in `configs/examples/`.

## Remote access

For remote machines, bind Ariadne to `127.0.0.1` on the server and tunnel the port over SSH:

```bash
ssh -L 8765:127.0.0.1:8765 user@example.org
```

Point the MCP client at the local forwarded endpoint. This keeps the Ariadne HTTP service off the public network while allowing remote use.

## Deployment pointers

- Docker: see `Dockerfile` and `docker-compose.example.yml` for one Qdrant service with multiple isolated Ariadne instances.
- systemd: see `deployment/systemd/ariadne@.service` for a per-instance service template.

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
