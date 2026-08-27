import tomllib
from pathlib import Path

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
