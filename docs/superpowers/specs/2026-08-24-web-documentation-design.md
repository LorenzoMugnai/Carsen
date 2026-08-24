# Web Documentation Design

## Goal

Build a polished, English-language documentation website for Carsen that helps academic users understand, install and operate a local-first MCP knowledge engine without assuming prior knowledge of vector databases, embeddings, chunks, citations or MCP.

## Audience

The primary audience is researchers, research software engineers, PhD students, lab staff and academic collaborators. Many readers may be comfortable with Python but unfamiliar with modern retrieval systems, vector databases or AI-agent protocols. The documentation must therefore explain concepts before asking readers to run commands.

## Recommended documentation system

Use **MkDocs Material** for the first documentation website.

Reasons:

- Carsen documentation is already Markdown-first.
- MkDocs Material produces a navigable, modern static site with little configuration.
- Mermaid diagrams are supported through MkDocs Material's built-in extensions.
- The site can be built to `site/`, served locally with `mkdocs serve`, and later served behind a reverse proxy or under a safe non-MCP path.

Sphinx with MyST remains a future option if Carsen needs deep Python API autodoc, but that is not the immediate need.

## Scope for this phase

This phase adds documentation-site scaffolding and improves explanatory content. It does **not** integrate the documentation site into `carsen serve` yet.

Included:

- `mkdocs.yml` configured for Material.
- `docs` optional dependency group in `pyproject.toml`.
- A didactic Quickstart for academic users.
- Concept pages explaining Qdrant, MCP, embeddings, chunks and citations.
- Mermaid diagrams that show the main flows visually.
- CI support for `mkdocs build --strict`.
- README links to the documentation site entry points.
- Tests that assert documentation scaffolding exists and references the expected pages.

Deferred:

- `carsen docs serve` command.
- `carsen serve --docs-site site` integration.
- Hosting on GitHub Pages or another public endpoint.
- Python API autodoc.

## Content architecture

The MkDocs navigation should be organized as follows:

1. **Home** — `docs/index.md`
2. **Getting started**
   - `docs/quickstart.md`
   - `docs/academic-users.md`
3. **Core concepts**
   - `docs/concepts.md`
   - `docs/concepts/mcp.md`
   - `docs/concepts/qdrant.md`
   - `docs/concepts/embeddings.md`
   - `docs/concepts/chunks-and-citations.md`
4. **Using Carsen**
   - `docs/configuration.md`
   - `docs/knowledge-instances.md`
   - `docs/indexing.md`
   - `docs/retrieval.md`
   - `docs/citations.md`
   - `docs/mcp.md`
   - `docs/cli-reference.md`
5. **Operations**
   - `docs/deployment.md`
   - `docs/security.md`
   - `docs/testing.md`
   - `docs/troubleshooting.md`
6. **Development**
   - `docs/architecture.md`
   - `docs/development.md`
   - `docs/extending.md`
   - ADRs under `docs/adr/`

## Diagram requirements

Use Mermaid diagrams in Markdown. Diagrams should be simple enough to read in GitHub and MkDocs Material.

Minimum diagrams:

1. **System overview** — User, MCP client, Carsen, chunk store, Qdrant and source files.
2. **Indexing pipeline** — discover files, parse, chunk, store metadata, embed, write Qdrant vectors.
3. **Retrieval pipeline** — query, dense/sparse/exact search, fusion/reranking, citations, MCP result.
4. **Instance isolation** — two projects with separate configs, state directories and Qdrant collections.
5. **Academic quickstart mental model** — documents/code become a searchable research memory.

## Tone and style

- All new documentation must be in English.
- Define unfamiliar terms before using them heavily.
- Prefer short sections, concrete examples and diagrams.
- Use academic analogies where helpful: catalogue, index cards, library shelves, lab notebook, citation trail.
- Avoid marketing exaggeration.
- Avoid assuming Docker, Qdrant, embeddings or MCP are already understood.

## Build and verification

Local build:

```bash
uv pip install -e '.[docs]'
mkdocs build --strict
```

CI should include the same `mkdocs build --strict` command after installing docs dependencies.

The `site/` output directory remains ignored by `.gitignore`.

## Future runtime serving design

A later implementation may add one of these patterns:

1. `carsen docs serve` — a dedicated command that serves built or source documentation independently from MCP.
2. `carsen serve NAME --transport http --docs-site site` — mount built static files under `/docs-site/` while keeping MCP streamable HTTP on `/mcp`.

If implemented, docs serving must never share the `/mcp` endpoint or interfere with MCP session handling.
