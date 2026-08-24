# Testing

Tests are configured in `pyproject.toml` with `tests` as the test path and `src` on `pythonpath`.

Run the suite with:

```bash
pytest
```

Existing tests cover configuration validation, registry behaviour, parser output, document parsing, Qdrant storage scaffolding, MCP runtime behaviour, deployment scaffolding and milestone-level integration expectations.

When adding behaviour, prefer focused tests that create temporary configurations and data directories so instances remain isolated and deterministic.

## Optional model tests

Tests that load real embedding or reranking models must be marked with `@pytest.mark.model`. They are examples or opt-in checks only: CI does not require sentence-transformers downloads, external model services or a running Qdrant server.

## Evaluation fixtures

Retrieval evaluation datasets are YAML files with `queries`, each containing a `query` string and an `expected` list of chunk IDs. The built-in evaluator reports Recall@k and MRR over SearchResult-like outputs without loading models.
