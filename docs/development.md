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

## AI-assisted development

Carsen is designed and maintained by Lorenzo Mugnai. The project's scope, its architecture, the public API and every decision recorded in the [architecture decision records](adr/0001-separate-knowledge-instances.md) are the author's.

Parts of the implementation were written with AI coding assistants — primarily Claude, with GPT-5.5 — for code generation, refactoring and test scaffolding. Every AI-assisted change is reviewed by the author, must pass the full quality gate (`ruff`, `mypy`, `pytest`, and `mkdocs build --strict` for docs) and ships with tests. Design choices follow the reasoning in the ADRs rather than an assistant's first suggestion; where an assistant proposed something that did not fit the instance-isolation, local-first or LLM-independence principles, it was rejected.

This note exists so the provenance of the code is clear, and so a future submission to a venue such as the Journal of Open Source Software can carry an accurate AI-usage disclosure.
