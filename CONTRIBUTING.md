# Contributing to Carsen

Carsen is a local-first Model Context Protocol (MCP) knowledge engine. Contributions should preserve instance isolation, metadata-backed citations, local-first defaults and the separation between retrieval and generation.

## Development setup

Use Python 3.12+ and `uv` from the repository root:

```bash
uv pip install -e '.[dev]'
```

If a moved virtual environment has stale entry-point shebangs, run tools through Python:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest
```

## Workflow

1. Create a focused branch from `main`.
2. Keep changes small and reversible.
3. Add or update tests for behavior changes.
4. Update documentation and `CHANGELOG.md` when users or operators see a change.
5. Avoid committing generated indexes, local state, secrets, `.env` files or user-specific registry files.

## Quality gates

Run the smallest gate that proves the change, then run the full gate before merging code changes:

```bash
python -m ruff check .
PYTHONPATH=src python -m mypy
python -m pytest
```

For documentation changes, also inspect Markdown links and run the docs build used by CI when practical:

```bash
uv run mkdocs build --strict
```

## Pull request checklist

- Tests or documentation explain the behavior change.
- `python -m ruff check .` passes.
- `PYTHONPATH=src python -m mypy` passes.
- `python -m pytest` passes, or skipped checks are documented.
- User-facing docs and `CHANGELOG.md` are updated when needed.
- No old Ariadne names were reintroduced.
- No secrets or local index artifacts are included.

## tag-based versioning

Carsen uses tag-based versioning. Release versions come from Git tags such as `v0.1.1` or `v0.2.0`; contributors should not edit package version literals for a release.

## Release checklist

1. Confirm `CHANGELOG.md` describes the release.
2. Run `python -m ruff check .`.
3. Run `PYTHONPATH=src python -m mypy`.
4. Run `python -m pytest`.
5. Run any practical operational smoke for indexing, retrieval, Qdrant or MCP changes.
6. Create a Git tag such as `v0.1.1` on the release commit.
7. Build artifacts from the tagged commit and confirm the generated version matches the tag.
8. Publish manually only after package credentials and release policy are defined.
