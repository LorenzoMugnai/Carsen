# CLI reference

This semi-generated reference mirrors the current Typer command surface used by tests.

## Core commands

- `carsen create NAME` creates a registered knowledge configuration.
- `carsen list` lists registered instances, status, ports, chunk counts and data directories.
- `carsen validate NAME` or `carsen validate --config PATH` validates configuration.
- `carsen status [NAME]` shows per-instance status and local index counts.

## Index and retrieval

- `carsen index NAME [--force] [--embed]` parses sources into canonical chunks, optionally embedding into Qdrant. If the optional dense phase fails, indexing still succeeds with a warning and sparse/exact search remains available.
- `carsen index NAME` is the portable baseline: it does not require GPU, embeddings or Qdrant, and it prepares the MCP tools that read from the local chunk store.
- `carsen watch NAME` watches configured sources and indexes after debounced filesystem changes.
- `carsen search NAME QUERY` searches a local instance chunk store.
- `carsen search --config PATH QUERY` searches an explicit configuration.
- Search options: `--corpus all|code|documents`, `--limit N`, `--debug`.
- Set `retrieval.dense_candidates: 0` in configuration when you want search to stay sparse/exact-only and avoid loading the embedding model.
- `carsen evaluate NAME DATASET` evaluates retrieval against a YAML dataset.
- `carsen evaluate --config PATH DATASET` evaluates an explicit configuration.

## Runtime and lifecycle

- `carsen serve NAME [--watch|--no-watch]` starts one MCP instance over configured or overridden transport, optionally running watch indexing in the background.
- `carsen serve-all [NAMES...]` starts multiple instances under an external supervisor pattern.
- `carsen stop NAME` reports the external-supervisor stop guidance.
- `carsen reembed NAME` re-embeds existing canonical chunks; this dense-only command exits nonzero if embeddings or Qdrant are unavailable.
- `carsen delete-index NAME` removes local index state and attempts dense collection cleanup.

## `carsen init-self`

Create a local registry configuration for Carsen's own documentation and source package.

```bash
carsen init-self
carsen init-self --index
carsen init-self --docs-path ./docs --source . --name carsen-self
```

By default the command creates an isolated `carsen-self` instance for self-reference and points it at the local Carsen documentation plus source package. Use it with an LLM client when you want Carsen to retrieve cited context about Carsen itself. Use `--index` to index immediately, or run `carsen index carsen-self` afterwards.

Options:

- `--docs-path PATH`: documentation directory to include.
- `--source PATH`: Carsen checkout root to scan; code is discovered at `PATH/src/carsen_mcp`.
- `--name NAME`: instance name to create; defaults to `carsen-self`.
- `--index`: index the self-reference instance immediately.
- `--force`: overwrite an existing local registry entry for the selected name.

## Operational smoke procedure

For a local smoke check, create or point at a small config, run `carsen index --config PATH`, then run `carsen search --config PATH "known token" --debug`. Optional deployment smoke tests should use the `smoke` pytest marker and must not require model downloads in CI.
