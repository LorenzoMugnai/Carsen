# Development

Ariadne is a Python package using Hatchling metadata in `pyproject.toml`. The console script is `ariadne = ariadne_mcp.cli:app` and the package source is under `src/ariadne_mcp`.

## Useful commands

```bash
python -m pip install -e '.[test]'
ariadne --help
pytest
```

## Code layout

- CLI commands live in `cli.py`.
- Configuration models live in `config.py`.
- Parsers return canonical `Chunk` records.
- Retrieval modules work with `SearchResult` objects.
- MCP server creation is intentionally thin and delegates to `InstanceRuntime`.

Keep changes aligned with the instance-per-config model and avoid adding global state that crosses knowledge instances.
