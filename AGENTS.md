# AGENTS.md

This file is the canonical operating guide for AI agents and human contributors working in this repository. Follow it before changing code, tests, documentation or deployment assets.

## Project identity

Carsen is a local-first Model Context Protocol (MCP) knowledge engine. It indexes code and document collections into isolated knowledge instances, retrieves cited context through dense, sparse, exact and hybrid search, and exposes that retrieval over MCP. Carsen does not own answer generation; the client or external LLM remains replaceable.

Use the current names consistently:

- Product/project: **Carsen**
- Python distribution: `carsen-mcp`
- Python package: `carsen_mcp`
- CLI executable: `carsen`
- Default config directory: `~/.config/carsen`
- Default data directory: `~/.local/share/carsen`

Do not reintroduce old Ariadne names. Before completing rename-adjacent work, search for `Ariadne`, `ariadne` and `ariadne_mcp`.

## Architectural principles

1. **Instance isolation is mandatory.** Each knowledge base is a named instance with its own configuration, source roots, local state, chunk store, Qdrant collection and MCP endpoint. Do not add process-global state that can mix instances.
2. **Retrieval is separate from generation.** Carsen retrieves, ranks and cites context. Do not add hard dependencies on one chat model or provider for answer generation.
3. **Canonical chunks are the source of truth.** Dense indexes, sparse indexes and exact lookup should be rebuildable from canonical chunk records and metadata.
4. **Citations must be metadata-backed.** Search results should point back to source paths, spans, symbols and other metadata rather than fabricated prose references.
5. **Local-first by default.** Prefer safe localhost defaults, explicit remote configuration and clear deployment guidance.
6. **Small, typed modules.** Keep CLI, config, ingestion, parsing, retrieval, storage and MCP runtime responsibilities separated.
7. **Operational clarity beats cleverness.** Errors should explain what configuration, dependency, index or service is missing and how to fix it.

## Repository map

- `src/carsen_mcp/cli.py` — Typer CLI commands: create, list, validate, index, search, evaluate, serve, reembed and delete-index.
- `src/carsen_mcp/config.py` — Pydantic configuration models and default paths.
- `src/carsen_mcp/registry.py` — local config discovery and registry helpers.
- `src/carsen_mcp/chunks/` — canonical chunk model and local chunk store.
- `src/carsen_mcp/ingestion/` — source discovery, indexing state and incremental indexing.
- `src/carsen_mcp/parsers/` — code and document parsers that emit chunks.
- `src/carsen_mcp/embeddings/` — embedding provider interfaces and implementations.
- `src/carsen_mcp/retrieval/` — dense, sparse, exact, hybrid, filtering, fusion, diagnostics and expansion logic.
- `src/carsen_mcp/reranking/` — reranker provider interfaces.
- `src/carsen_mcp/storage/qdrant.py` — Qdrant vector-store integration.
- `src/carsen_mcp/mcp/` — MCP runtime and server transport wiring.
- `src/carsen_mcp/evaluation/` — retrieval evaluation dataset loading and metrics.
- `tests/` — unit, integration and operational smoke coverage.
- `docs/` — user, architecture, operations and extension documentation.
- `configs/examples/` — example instance configurations.
- `deployment/` and `docker-compose.example.yml` — deployment scaffolding.

## Development environment

Use Python 3.12+. The project uses Hatchling metadata and `uv` is the preferred environment manager.

Recommended setup from the repository root:

```bash
uv pip install -e '.[dev]'
```

After a repository path rename or virtualenv move, entry-point scripts may keep stale shebangs. Prefer module execution for verification in that situation:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest
```

CLI smoke examples:

```bash
.venv/bin/carsen --help
.venv/bin/carsen validate --config config.example.yaml
.venv/bin/carsen search --help
.venv/bin/carsen evaluate --help
```

## Required quality gates

Run the smallest gate that proves your change, and do not claim completion without fresh evidence.

- For Python behavior changes: `python -m ruff check .`, `python -m mypy`, and relevant `python -m pytest ...` tests.
- For broad refactors or package renames: full `python -m pytest` plus CLI smoke.
- For CLI/config changes: targeted CLI tests plus `carsen --help` and `carsen validate --config config.example.yaml`.
- For retrieval/indexing changes: relevant retrieval tests; if Qdrant or embeddings behavior changes, add or run an operational smoke where practical.
- For documentation-only changes: inspect the rendered Markdown mentally, check links/commands, and run a lightweight status/lint gate if code imports are untouched.

Prefer `python -m <tool>` inside `.venv` when path stability matters:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest
```

## Contribution rules

### Configuration and registry

- Preserve the named-instance model.
- Keep defaults local and explicit: config under `~/.config/carsen`, state under `~/.local/share/carsen` unless the user config says otherwise.
- Validate user-facing configuration with clear Pydantic errors or CLI messages.
- Update `config.example.yaml`, `configs/examples/`, `docs/configuration.md` and tests when config schema changes.

### Ingestion and parsers

- Parsers should emit canonical `Chunk` records with enough metadata for citations and filtering.
- Keep parser failures local to the affected file where possible; do not make one malformed document corrupt an entire instance.
- Avoid introducing heavyweight parser dependencies without making them optional or documenting operational impact.
- Preserve incremental indexing semantics and indexing state unless explicitly changing them with tests.

### Retrieval and ranking

- Keep dense, sparse and exact retrieval paths independently understandable and testable.
- Hybrid search should expose diagnostics that explain which retrieval paths contributed.
- Do not fabricate citations, source paths or symbol names.
- Keep filter semantics explicit for corpus, path, language and metadata filters.
- If scoring or fusion changes, update tests and document any user-visible ranking behavior.

### MCP runtime and CLI

- Keep MCP transport wiring thin; business logic belongs in `InstanceRuntime` and related modules.
- CLI commands should fail with actionable messages.
- Preserve non-interactive behavior suitable for scripts and systemd services.
- When command signatures or help text change, update tests and `docs/cli-reference.md`.

### Storage and Qdrant

- Instance-specific collections must remain isolated.
- Dense indexes should be rebuildable from canonical chunks.
- Handle missing Qdrant services, empty collections and embedding mismatches with clear errors.
- Do not require Qdrant for code paths that only inspect local configuration or local chunks.

### Documentation and deployment

- Keep docs synchronized with the actual CLI, package name and config schema.
- Use `carsen` in commands and `carsen-mcp` in package/deployment contexts.
- Deployment examples should default to localhost or explicitly explain exposure risks.
- Update Docker, Compose and systemd examples together when service names or ports change.

## Safety and privacy

- Never commit secrets, local `.env` files, private indexes, Qdrant data directories, generated databases or user-specific registry files.
- Treat indexed source documents as potentially sensitive. Avoid printing large source excerpts in logs or errors.
- Redact tokens, credentials and remote URLs with embedded secrets in diagnostics.
- Keep `.gitignore` aligned with local runtime artifacts so working trees stay clean.

## Dependency policy

- Prefer small, well-maintained dependencies.
- Avoid adding model-provider SDKs or parser stacks to core dependencies unless Carsen cannot function without them.
- Optional capabilities should be optional dependencies or gracefully degraded code paths.
- If a dependency changes runtime requirements, update `pyproject.toml`, docs and CI/test expectations together.

## Testing expectations

Add or update tests with behavior changes. Useful patterns:

- Config/schema changes: `tests/test_config.py` and example config validation.
- Registry changes: `tests/test_registry.py`.
- Parser changes: parser-specific tests and chunk metadata assertions.
- Indexing changes: milestone/indexing tests and chunk-store state assertions.
- Retrieval changes: unit tests for the retrieval component plus integration tests for composed search.
- MCP changes: runtime tests and MCP client E2E tests where transport behavior changes.
- Deployment scaffolding: tests that assert expected files, service names and commands.

Do not rely only on manual inspection for executable behavior. If a bug is fixed, add a regression test when practical.

## Coding style

- Use Python 3.12 idioms and type annotations.
- Keep functions short enough to reason about without reading unrelated subsystems.
- Prefer explicit dataclasses/Pydantic models over unstructured dictionaries at module boundaries.
- Keep imports sorted by Ruff.
- Avoid hidden I/O at import time.
- Use `pathlib.Path` for filesystem paths.
- Make failures deterministic and testable.

## Agent workflow checklist

Before editing:

1. Confirm the requested scope and whether it touches runtime behavior, docs, deployment or tests.
2. Check `git status --short` and avoid overwriting unrelated user changes.
3. Read only the files needed for the change.
4. Identify the validation command before implementing.

While editing:

1. Keep changes focused and reversible.
2. Update code, tests and docs in the same change when behavior changes.
3. Preserve instance isolation and local-first defaults.
4. Avoid unrelated formatting churn.

Before reporting completion:

1. Run the agreed verification commands.
2. Check `git status --short`.
3. Search for stale project names when rename work is involved:

   ```bash
   rg 'Ariadne|ariadne|ariadne_mcp'
   ```

4. Report exactly what was verified and any remaining manual steps.

## Commit guidance

- Commit only when explicitly asked or when the current workflow already requires it.
- Stage only intended files.
- Use concise imperative messages, for example `Add contributor agent guidance` or `Expand local artifact ignores`.
- Before committing, inspect `git status`, `git diff --cached --stat` and recent log context.

## Known operational notes

- `.venv/bin/<tool>` scripts can break after moving the repository because their shebangs may point to the old path. Reinstall editable dependencies or run tools with `.venv/bin/python -m <tool>`.
- Full Qdrant smoke tests require a local or containerized Qdrant service and may not be appropriate for every docs-only change.
- Some optional model tests may download or load real models and are marked separately.
