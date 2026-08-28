<div align="center">

<img src="docs/assets/logo.png" alt="Carsen logo" width="288" />

<h1>Carsen</h1>

<p><em>Local-first MCP knowledge engine for indexed code and document collections.</em></p>

<p>
  <a href="https://github.com/LorenzoMugnai/Carsen/actions/workflows/ci.yml">
    <img alt="GitHub Actions CI" src="https://github.com/LorenzoMugnai/Carsen/actions/workflows/ci.yml/badge.svg?branch=main">
  </a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="carsen-mcp package" src="https://img.shields.io/badge/carsen--mcp-tag--versioned-7c3aed?style=flat-square">
  <img alt="MCP enabled" src="https://img.shields.io/badge/MCP-enabled-111827?style=flat-square">
  <img alt="Ruff" src="https://img.shields.io/badge/Ruff-linting-2C6BED?style=flat-square&logo=ruff&logoColor=white">
  <img alt="mypy" src="https://img.shields.io/badge/mypy-checked-2A6DB2?style=flat-square&logo=mypy&logoColor=white">
  <img alt="local-first" src="https://img.shields.io/badge/local--first-yes-0F766E?style=flat-square">
  <img alt="Qdrant" src="https://img.shields.io/badge/Qdrant-backed-FF6F00?style=flat-square&logo=qdrant&logoColor=white">
</p>

</div>

Carsen is a local-first Model Context Protocol (MCP) knowledge engine for serving indexed code and document collections to any MCP-capable client. It keeps retrieval, citation metadata and operational state in Carsen; the generative LLM remains replaceable.

## What problem does Carsen solve?

When an LLM or an AI agent has to answer questions about *your* code, papers and notes, it usually does one of three unsatisfying things:

- **guesses from training data** and quietly invents the specifics — a function signature, a config key, a parameter bound, a number;
- **has the whole file pasted into its context**, which is wasteful, and impossible once the corpus is large;
- **calls a hosted RAG service**, which means shipping your material to a third party and trusting citations you cannot check.

Carsen is the missing middle. You index your sources into isolated, on-disk knowledge bases; Carsen returns the few passages that actually answer a query, each with a real citation — source path, line span, and a commit-pinned link where one exists — and serves them over MCP so any client or model can use them. Nothing leaves your machine unless you configure it to, and the answer generation stays with whatever LLM you choose.

It is built for researchers, labs and engineers who need grounded, reproducible answers over their own material.

## Documentation

- [Quickstart for academic users](docs/quickstart.md)
- [Core concepts](docs/concepts.md)
- [Contributing guide](CONTRIBUTING.md)
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

### Set up with an AI agent

If you are an AI agent — or a user asking your assistant to do this — follow
[docs/agent-setup.md](docs/agent-setup.md). It is a linear, checkable recipe from
prerequisites to a served MCP endpoint, and the default path needs no vector
database and no embedding model. `AGENTS.md` is the deeper guide for agents
working on Carsen itself; [`llms.txt`](llms.txt) is a short map of the docs.

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

## The name

The mascot is Carsen, a librarian. The name is a quiet nod to a certain fictional librarian — the one with a wall of academic degrees who, whatever you ask, can tell you the exact shelf, the exact volume and the exact page. That is the job description here: Carsen does not write your thesis or your final answer, it just always knows where the answer lives and never makes up a citation. The pixel-art librarian is our own.

## Development and AI assistance

Carsen is designed and maintained by Lorenzo Mugnai. The project's direction, its architecture, the public API and every decision recorded in the [ADRs](docs/adr/) are the author's.

Parts of the implementation were written with AI coding assistants (Claude and GPT-5.5) — yes, there was some vibe coding. It was not blind: every AI-assisted change is reviewed, run through the full quality gate (`ruff`, `mypy`, `pytest`, `mkdocs build --strict`) and accompanied by tests before it lands, and the design choices are the ones argued in the ADRs rather than whatever an assistant proposed first. See [docs/development.md](docs/development.md) for the fuller statement.

## License

Carsen is released under the [BSD 3-Clause License](LICENSE).
