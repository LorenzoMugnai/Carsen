# Testing

Tests are configured in `pyproject.toml` with `tests` as the test path and `src` on `pythonpath`.

Run the suite with:

```bash
pytest
```

Existing tests cover configuration validation, registry behaviour, parser output, document parsing, Qdrant storage scaffolding, MCP runtime behaviour, deployment scaffolding and milestone-level integration expectations.

When adding behaviour, prefer focused tests that create temporary configurations and data directories so instances remain isolated and deterministic.
