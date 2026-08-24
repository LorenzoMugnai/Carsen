# CLI reference

This semi-generated reference mirrors the current Typer command surface used by tests.

## Core commands

- `carsen create NAME` creates a registered knowledge configuration.
- `carsen list` lists registered instances, status, ports, chunk counts and data directories.
- `carsen validate NAME` or `carsen validate --config PATH` validates configuration.
- `carsen status [NAME]` shows per-instance status and local index counts.

## Index and retrieval

- `carsen index NAME [--force] [--embed]` parses sources into canonical chunks, optionally embedding into Qdrant.
- `carsen search NAME QUERY` searches a local instance chunk store.
- `carsen search --config PATH QUERY` searches an explicit configuration.
- Search options: `--corpus all|code|documents`, `--limit N`, `--debug`.
- `carsen evaluate NAME DATASET` evaluates retrieval against a YAML dataset.
- `carsen evaluate --config PATH DATASET` evaluates an explicit configuration.

## Runtime and lifecycle

- `carsen serve NAME` starts one MCP instance over configured or overridden transport.
- `carsen serve-all [NAMES...]` starts multiple instances under an external supervisor pattern.
- `carsen stop NAME` reports the external-supervisor stop guidance.
- `carsen reembed NAME` re-embeds existing canonical chunks.
- `carsen delete-index NAME` removes local index state and attempts dense collection cleanup.

## Operational smoke procedure

For a local smoke check, create or point at a small config, run `carsen index --config PATH`, then run `carsen search --config PATH "known token" --debug`. Optional deployment smoke tests should use the `smoke` pytest marker and must not require model downloads in CI.
