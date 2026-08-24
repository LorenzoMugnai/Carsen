# Development

Carsen is a Python package using Hatchling metadata in `pyproject.toml`. The console script is `carsen = carsen_mcp.cli:app` and the package source is under `src/carsen_mcp`.

## Useful commands

```bash
python -m pip install -e '.[test]'
carsen --help
pytest
```

## Code layout

- CLI commands live in `cli.py`.
- Configuration models live in `config.py`.
- Parsers return canonical `Chunk` records.
- Retrieval modules work with `SearchResult` objects.
- MCP server creation is intentionally thin and delegates to `InstanceRuntime`.

Keep changes aligned with the instance-per-config model and avoid adding global state that crosses knowledge instances.
