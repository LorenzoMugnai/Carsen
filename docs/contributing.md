# Contributing

Carsen grows best through small, tested changes that preserve local-first retrieval, instance isolation and metadata-backed citations.

## Start here

The canonical repository guide is [`CONTRIBUTING.md`](../CONTRIBUTING.md). Use it for setup, workflow, quality gates, pull request expectations and release steps.

## quality gates

Before reporting a code change as complete, run:

```bash
python -m ruff check .
PYTHONPATH=src python -m mypy
python -m pytest
```

Documentation-only changes should still be checked for links, commands and rendered Markdown. Run `uv run mkdocs build --strict` when changing the site structure.

## tag-based versioning

Carsen release versions come from Git tags such as `v0.1.1`. Do not update duplicated version literals for releases; build artifacts from tagged commits so package metadata receives the release version.

## Pull request checklist

- Keep the change focused.
- Add tests for behavior changes.
- Update user-facing docs and `CHANGELOG.md` when behavior changes.
- Keep secrets, local indexes and registry files out of Git.

## Release checklist

Use the root guide for the full manual release checklist. Automated package publishing is intentionally out of scope until credentials and release policy are defined.
