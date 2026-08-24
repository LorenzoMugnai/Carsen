from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_runs_lint_type_check_and_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "uv sync --extra dev" in workflow
    assert "uv run ruff check ." in workflow
    assert "uv run mypy" in workflow
    assert "uv run pytest" in workflow


def test_pyproject_declares_dev_quality_tools() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "ruff>=0.8" in pyproject
    assert "mypy>=1.10" in pyproject
    assert "[tool.ruff]" in pyproject
    assert "[tool.mypy]" in pyproject


def test_ci_builds_documentation_site() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert ".[docs]" in workflow
    assert "uv run mkdocs build --strict" in workflow


def test_docs_extra_declares_mkdocs_runtime_extensions() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "mkdocs>=1.6" in pyproject
    assert "mkdocs-material>=9.5" in pyproject
    assert "pymdown-extensions" in pyproject


def test_readme_uses_uv_run_for_mkdocs_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "uv run mkdocs serve" in readme
    assert "\nmkdocs serve" not in readme
