# Contributing and Tag-Based Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable contribution guidance and switch Carsen package versioning to Git tag-derived dynamic versions.

**Architecture:** Keep contribution guidance as repository documentation plus a MkDocs page. Keep release automation manual for now, but make package metadata derive from Git tags through `hatch-vcs` and remove duplicated hard-coded version state from package code.

**Tech Stack:** Python 3.12, Hatchling, hatch-vcs, importlib.metadata, PyYAML test parsing, MkDocs Material, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-27-contributing-and-tag-versioning-design.md`

## Global Constraints

- Product/project name is Carsen; distribution name is `carsen-mcp`; package name is `carsen_mcp`; CLI executable is `carsen`.
- Use tag-based versioning with Git tags like `v0.1.1` or `v0.2.0`.
- Do not add PyPI publishing automation or secrets in this iteration.
- Do not introduce old Ariadne names.
- Use TDD: tests fail before implementation changes.
- Preserve existing CI gates: docs build, Ruff, mypy and pytest.
- Do not touch unrelated untracked files under `docs/superpowers/...` or `uv.lock` unless explicitly required by a task.

---

## File Structure

- Create `CONTRIBUTING.md`: root-level canonical contributor guide for GitHub/repository users.
- Create `docs/contributing.md`: site-friendly contributor guide, linked from MkDocs navigation.
- Modify `README.md`: add contribution link and update version badge so it is not a hard-coded release version.
- Modify `mkdocs.yml`: add the contributing page under the Development section.
- Modify `pyproject.toml`: switch from static `version = "0.1.0"` to `dynamic = ["version"]`, add `hatch-vcs`, and configure `[tool.hatch.version]`.
- Modify `src/carsen_mcp/__init__.py`: derive `__version__` from package metadata with a safe fallback.
- Modify `.github/workflows/ci.yml`: checkout full history and tags with `fetch-depth: 0`.
- Modify `tests/test_documentation_presence.py`: protect contributing docs and nav links.
- Create or modify `tests/test_versioning.py`: protect the dynamic versioning contract and package `__version__` behavior.

---

### Task 1: Contribution documentation presence tests

**Files:**
- Modify: `tests/test_documentation_presence.py`
- Test target: `tests/test_documentation_presence.py::test_contributing_documentation_is_present_and_linked`

**Interfaces:**
- Consumes: existing `ROOT = Path(__file__).resolve().parents[1]`.
- Produces: a failing test that requires `CONTRIBUTING.md`, `docs/contributing.md`, README links and MkDocs nav.

- [ ] **Step 1: Write the failing test**

Add this test near the other documentation presence tests:

```python
def test_contributing_documentation_is_present_and_linked() -> None:
    root_guide = ROOT / "CONTRIBUTING.md"
    docs_guide = ROOT / "docs" / "contributing.md"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert root_guide.exists()
    assert docs_guide.exists()

    root_text = root_guide.read_text(encoding="utf-8")
    docs_text = docs_guide.read_text(encoding="utf-8")
    required_phrases = [
        "uv pip install -e '.[dev]'",
        "python -m ruff check .",
        "PYTHONPATH=src python -m mypy",
        "python -m pytest",
        "Pull request checklist",
        "Release checklist",
        "tag-based versioning",
    ]
    for phrase in required_phrases:
        assert phrase in root_text
    for phrase in ["Carsen", "quality gates", "tag-based versioning", "Release checklist"]:
        assert phrase in docs_text

    assert "CONTRIBUTING.md" in readme
    assert "contributing.md" in mkdocs
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_documentation_presence.py::test_contributing_documentation_is_present_and_linked -q
```

Expected: FAIL because `CONTRIBUTING.md` and `docs/contributing.md` do not exist yet.

- [ ] **Step 3: Stop after RED**

Do not create docs in this task. Task 2 owns implementation.

---

### Task 2: Contributor docs and navigation

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `docs/contributing.md`
- Modify: `README.md`
- Modify: `mkdocs.yml`
- Test: `tests/test_documentation_presence.py`

**Interfaces:**
- Consumes: failing test from Task 1.
- Produces: discoverable contributor docs and docs-site navigation.

- [ ] **Step 1: Create root guide**

Create `CONTRIBUTING.md` with this structure and content:

```markdown
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
```

- [ ] **Step 2: Create docs page**

Create `docs/contributing.md` with this content:

```markdown
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
```

- [ ] **Step 3: Link from README**

In `README.md`, add a Documentation bullet:

```markdown
- [Contributing guide](CONTRIBUTING.md)
```

Replace the hard-coded version badge line:

```html
  <img alt="carsen-mcp v0.1.0" src="https://img.shields.io/badge/carsen--mcp-v0.1.0-7c3aed?style=flat-square">
```

with a non-literal package badge:

```html
  <img alt="carsen-mcp package" src="https://img.shields.io/badge/carsen--mcp-tag--versioned-7c3aed?style=flat-square">
```

- [ ] **Step 4: Add MkDocs nav entry**

In `mkdocs.yml`, under `Development`, add:

```yaml
      - Contributing: contributing.md
```

Place it before `Development setup`.

- [ ] **Step 5: Run docs test**

Run:

```bash
python -m pytest tests/test_documentation_presence.py::test_contributing_documentation_is_present_and_linked -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add CONTRIBUTING.md docs/contributing.md README.md mkdocs.yml tests/test_documentation_presence.py
git commit -m "Add contributing guide"
```

---

### Task 3: Dynamic versioning tests

**Files:**
- Create: `tests/test_versioning.py`
- Test target: `tests/test_versioning.py`

**Interfaces:**
- Consumes: current static version setup.
- Produces: failing tests requiring Hatch VCS dynamic versioning and metadata-derived `__version__`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_versioning.py`:

```python
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_uses_hatch_vcs_dynamic_versioning() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["build-system"]["requires"] == ["hatchling", "hatch-vcs"]
    assert data["project"]["dynamic"] == ["version"]
    assert "version" not in data["project"]
    assert data["tool"]["hatch"]["version"]["source"] == "vcs"
    assert data["tool"]["hatch"]["version"]["fallback-version"] == "0.0.0"


def test_package_version_is_not_a_duplicated_literal() -> None:
    init_text = (ROOT / "src" / "carsen_mcp" / "__init__.py").read_text(encoding="utf-8")

    assert "importlib.metadata" in init_text
    assert "version(\"carsen-mcp\")" in init_text
    assert "__version__ = \"0.1.0\"" not in init_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_versioning.py -q
```

Expected: FAIL because `pyproject.toml` still has a static version and `__init__.py` still has `__version__ = "0.1.0"`.

- [ ] **Step 3: Stop after RED**

Do not modify packaging in this task. Task 4 owns implementation.

---

### Task 4: Hatch VCS dynamic versioning implementation

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/carsen_mcp/__init__.py`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_versioning.py`

**Interfaces:**
- Consumes: failing tests from Task 3.
- Produces: package metadata version derived from VCS tags and runtime package `__version__` derived from installed metadata.

- [ ] **Step 1: Update build system**

In `pyproject.toml`, change:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

to:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Update project version metadata**

In `[project]`, remove:

```toml
version = "0.1.0"
```

and add:

```toml
dynamic = ["version"]
```

- [ ] **Step 3: Add Hatch VCS config**

Add this after the existing Hatch build section:

```toml
[tool.hatch.version]
source = "vcs"
fallback-version = "0.0.0"
```

- [ ] **Step 4: Update package version lookup**

Replace `src/carsen_mcp/__init__.py` with:

```python
"""Carsen MCP package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("carsen-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0"
```

- [ ] **Step 5: Fetch tags in CI**

In `.github/workflows/ci.yml`, change checkout to:

```yaml
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

- [ ] **Step 6: Run versioning tests**

Run:

```bash
python -m pytest tests/test_versioning.py -q
```

Expected: PASS.

- [ ] **Step 7: Run build metadata smoke**

Run:

```bash
python -m build --wheel --outdir /tmp/opencode/carsen-dist
```

Expected: command exits 0 and prints a wheel filename with a version derived by `hatch-vcs` or the fallback. If `build` is unavailable, run `python -m pip install build` only if allowed by the environment; otherwise record that the smoke could not run and rely on pytest plus CI.

- [ ] **Step 8: Commit**

Run:

```bash
git add pyproject.toml src/carsen_mcp/__init__.py .github/workflows/ci.yml tests/test_versioning.py
git commit -m "Use tag-based package versioning"
```

---

### Task 5: Final documentation and release checklist verification

**Files:**
- Inspect/modify if needed: `CHANGELOG.md`, `docs/development.md`, `docs/testing.md`, `docs/deployment.md`
- No new public interface.

**Interfaces:**
- Consumes: docs and versioning from Tasks 2 and 4.
- Produces: final consistency check and one integration commit only if small doc fixes are needed.

- [ ] **Step 1: Search for stale version guidance**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [Path('README.md'), Path('docs/development.md'), Path('docs/testing.md'), Path('docs/deployment.md'), Path('CHANGELOG.md')]:
    text = path.read_text(encoding='utf-8')
    if '__version__ = "0.1.0"' in text or 'version = "0.1.0"' in text:
        print(path)
PY
```

Expected: no output.

- [ ] **Step 2: Search for old project names**

Run:

```bash
rg 'Ariadne|ariadne|ariadne_mcp'
```

Expected: no output.

- [ ] **Step 3: Run final gates**

Run:

```bash
python -m ruff check .
PYTHONPATH=src python -m mypy
python -m pytest
uv run mkdocs build --strict
```

Expected: all commands exit 0. If `uv run mkdocs build --strict` fails only because optional docs dependencies are not installed locally, report that exact limitation and rely on CI docs build config.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional committed files plus known unrelated pre-existing untracked files remain.

- [ ] **Step 5: Final report**

Report commits created, verification commands and any limitations. Do not claim completion without the fresh command outputs from Step 3.
