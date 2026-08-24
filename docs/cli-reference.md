# CLI reference

This semi-generated reference mirrors the current Typer command surface used by tests.

## Core commands

- `ariadne create NAME` creates a registered knowledge configuration.
- `ariadne list` lists registered instances, status, ports, chunk counts and data directories.
- `ariadne validate NAME` or `ariadne validate --config PATH` validates configuration.
- `ariadne status [NAME]` shows per-instance status and local index counts.

## Index and retrieval

- `ariadne index NAME [--force] [--embed]` parses sources into canonical chunks, optionally embedding into Qdrant.
- `ariadne search NAME QUERY` searches a local instance chunk store.
- `ariadne search --config PATH QUERY` searches an explicit configuration.
- Search options: `--corpus all|code|documents`, `--limit N`, `--debug`.
- `ariadne evaluate NAME DATASET` evaluates retrieval against a YAML dataset.
- `ariadne evaluate --config PATH DATASET` evaluates an explicit configuration.

## Runtime and lifecycle

- `ariadne serve NAME` starts one MCP instance over configured or overridden transport.
- `ariadne serve-all [NAMES...]` starts multiple instances under an external supervisor pattern.
- `ariadne stop NAME` reports the external-supervisor stop guidance.
- `ariadne reembed NAME` re-embeds existing canonical chunks.
- `ariadne delete-index NAME` removes local index state and attempts dense collection cleanup.

## Operational smoke procedure

For a local smoke check, create or point at a small config, run `ariadne index --config PATH`, then run `ariadne search --config PATH "known token" --debug`. Optional deployment smoke tests should use the `smoke` pytest marker and must not require model downloads in CI.
