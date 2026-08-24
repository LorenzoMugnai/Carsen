from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from carsen_mcp.cli import app


def test_init_self_cli_creates_config(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry"
    source = tmp_path / "carsen"
    (source / "docs").mkdir(parents=True)
    (source / "src" / "carsen_mcp").mkdir(parents=True)
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(registry))

    result = CliRunner().invoke(app, ["init-self", "--source", str(source)])

    assert result.exit_code == 0, result.stdout
    assert "Created Carsen self-reference configuration" in result.stdout
    assert "carsen index carsen-self" in result.stdout
    assert (registry / "carsen-self.yaml").exists()


def test_init_self_cli_reports_missing_docs(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry"
    source = tmp_path / "carsen"
    source.mkdir()
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(registry))

    result = CliRunner().invoke(app, ["init-self", "--source", str(source)])

    assert result.exit_code != 0
    assert "Could not find Carsen documentation directory for self-reference" in result.stdout


def test_init_self_cli_index_flag_calls_indexer(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry"
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(registry))
    called = {}

    def fake_index_config(config, force: bool = False, embed: bool = False):
        called["knowledge_id"] = config.knowledge.id
        called["force"] = force
        called["embed"] = embed

        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 2

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["init-self", "--docs-path", str(docs), "--index"])

    assert result.exit_code == 0, result.stdout
    assert called == {"knowledge_id": "carsen-self", "force": False, "embed": False}
    assert "Indexed 'carsen-self'" in result.stdout
