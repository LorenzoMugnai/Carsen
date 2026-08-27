# Contributing and tag-based versioning design

## Goal

Make Carsen easier to grow as a long-lived open source repository by adding clear contributor guidance and removing duplicated manual version state. The repository should explain how to set up a development environment, make changes safely, run quality gates, update docs, prepare releases and use Git tags as the source of package versions.

## Scope

Implement the essential governance and release-hygiene path:

- Add a root `CONTRIBUTING.md` as the canonical contributor entry point.
- Add a site page at `docs/contributing.md` and include it in MkDocs navigation.
- Link contribution guidance from `README.md`.
- Convert packaging to tag-based dynamic versioning with Hatchling and `hatch-vcs`.
- Remove duplicated hard-coded package version state from `src/carsen_mcp/__init__.py`.
- Update CI checkout to fetch tags so dynamic versioning works in automation.
- Add tests or documentation-presence checks that protect the new contribution docs and versioning contract.

Out of scope for this iteration:

- Automatic PyPI publishing.
- Release-drafter automation.
- Secret management for package publishing.
- Enforcing every contribution rule with pre-commit hooks.

## Current state

Carsen already has useful development material spread across `README.md`, `docs/development.md`, `docs/testing.md`, `docs/deployment.md`, `CHANGELOG.md` and `AGENTS.md`. CI runs docs build, Ruff, mypy and pytest on Python 3.12.

Versioning is currently duplicated:

- `pyproject.toml` contains `version = "0.1.0"`.
- `src/carsen_mcp/__init__.py` contains `__version__ = "0.1.0"`.

The repository does not yet include a root `CONTRIBUTING.md`, a docs navigation entry for contributing, a release workflow or a dynamic version source.

## Proposed design

### Contributor documentation

Create `CONTRIBUTING.md` for humans landing on the repository. It should be concise and operational:

- Project identity and architectural principles.
- Local setup with `uv pip install -e '.[dev]'`.
- Development workflow: branch, focused changes, tests, docs and changelog.
- Required quality gates for code, docs and packaging changes.
- Pull request checklist.
- Release checklist based on tags.
- Security/privacy reminders for local-first indexed data.

Create `docs/contributing.md` for the documentation site. It may reuse the same content in a docs-friendly form, with links to detailed development, testing, deployment and configuration pages.

Update `README.md` and `mkdocs.yml` so contributors can find this guidance without knowing internal file names.

### Dynamic versioning

Use tag-based versioning through `hatch-vcs`:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[project]
dynamic = ["version"]

[tool.hatch.version]
source = "vcs"
fallback-version = "0.0.0"
```

Use Git tags such as `v0.1.1` or `v0.2.0` as the release version source. Build release artifacts from the tagged commit. CI should use `actions/checkout` with `fetch-depth: 0` so tags are available.

In package code, avoid maintaining a second version constant. `src/carsen_mcp/__init__.py` should obtain the installed distribution version via `importlib.metadata.version("carsen-mcp")`, with a safe fallback for editable or partial source environments where metadata is not yet available.

### Release workflow documentation

Document a manual release path without publishing automation:

1. Ensure `CHANGELOG.md` has an Unreleased section ready to cut.
2. Run `python -m ruff check .`, `PYTHONPATH=src python -m mypy` and `python -m pytest`.
3. Run any practical operational smoke relevant to the change.
4. Create a tag such as `v0.1.1` on the release commit.
5. Build artifacts and confirm the generated package version matches the tag.
6. Publish manually only when package credentials and release policy are defined.

This keeps the repository safe while enabling future release automation.

## Testing and verification

Add or update lightweight tests to cover:

- `CONTRIBUTING.md` exists and mentions setup, quality gates, PR checklist and release/versioning.
- `docs/contributing.md` exists and is included in `mkdocs.yml` navigation.
- `pyproject.toml` uses dynamic versioning and includes `hatch-vcs`.
- The package version is no longer a duplicated hard-coded literal in `__init__.py`.

Final verification for the implementation should include:

```bash
python -m ruff check .
PYTHONPATH=src python -m mypy
python -m pytest
```

If documentation structure changes are substantial, also run the docs build command used by CI.

## Risks and mitigations

- **Missing tags in CI**: set checkout `fetch-depth: 0`.
- **Builds from source trees without Git metadata**: set a fallback version.
- **Version import failures during local development**: use `importlib.metadata` with a narrow fallback rather than Git calls at import time.
- **Overly heavy governance**: keep contribution docs checklist-oriented and avoid requiring automation that does not exist yet.

## Acceptance criteria

- Contributors can find a clear root contribution guide and docs-site contribution page.
- CI still runs successfully.
- Package versioning is derived from Git tags rather than duplicated literals.
- Release steps are documented but do not require secrets or PyPI publishing automation.
- Tests protect the main documentation and versioning invariants.
