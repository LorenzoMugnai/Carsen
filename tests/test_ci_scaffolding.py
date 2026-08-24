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
