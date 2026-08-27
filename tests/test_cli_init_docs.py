from __future__ import annotations

from pathlib import Path

import yaml
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


def test_index_cli_emits_progress_and_keeps_summary(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    config = tmp_path / "carsen.yaml"
    data = tmp_path / "data"
    config.write_text(
        f"""
knowledge:
  id: cli-kb
storage:
  data_directory: {data}
sources:
  code:
    - path: {src}
  documents: []
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["index", "--config", str(config)])

    assert result.exit_code == 0, result.stdout
    assert "Indexed 'cli-kb': new=1 unchanged=0 changed=0 deleted=0 chunks=" in result.stdout
    assert "Discovered 1 file(s)." in result.stderr
    assert "Fingerprinting 1 file(s) for incremental changes..." in result.stderr
    assert "Fingerprinting complete: 1 file(s)" in result.stderr
    assert "Classified files: new=1 unchanged=0 changed=0 deleted=0 to_parse=1" in result.stderr
    assert "Parsing 1/1:" in result.stderr
    assert "Deleted stale file entries: 0." in result.stderr


def test_index_cli_reviews_noisy_files_and_persists_selected_ignores(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (src / "run.log").write_text("log\n" * 100, encoding="utf-8")
    (src / "image.png").write_bytes(b"PNG" * 100)
    config = tmp_path / "carsen.yaml"
    data = tmp_path / "data"
    config.write_text(
        f"""
knowledge:
  id: cli-kb
storage:
  data_directory: {data}
sources:
  code:
    - path: {src}
  documents: []
""",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        calls.append(list(config.indexing.ignored_extensions))

        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 1
            dense_error = None

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "--config", str(config)], input="1\n")

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Potential indexing noise:" in result.stderr
    assert "1. logs" in result.stderr
    assert "2. images/media" in result.stderr
    assert "run.log" in result.stderr
    assert "image.png" in result.stderr
    assert ".log" in calls[0]
    assert ".png" not in calls[0]
    saved = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert ".log" in saved["indexing"]["ignored_extensions"]
    assert ".png" not in saved["indexing"].get("ignored_extensions", [])


def test_index_cli_yes_skips_noisy_file_prompt(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "run.log").write_text("log\n", encoding="utf-8")
    config = tmp_path / "carsen.yaml"
    config.write_text(
        f"""
knowledge:
  id: cli-kb
sources:
  code:
    - path: {src}
  documents: []
""",
        encoding="utf-8",
    )

    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 1
            dense_error = None

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "--config", str(config), "--yes"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Potential indexing noise:" in result.stderr
    assert "Use interactive indexing without --yes to update ignored_extensions." in result.stderr
    saved = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert "indexing" not in saved


def test_index_cli_noisy_review_summarizes_counts_sizes_and_directories(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    cache = src / "htmlcov"
    cache.mkdir(parents=True)
    (src / "array.npy").write_bytes(b"0" * 20)
    (src / "cube.fits").write_bytes(b"1" * 30)
    (src / "payload.zip").write_bytes(b"2" * 40)
    (cache / "index.html").write_text("coverage report", encoding="utf-8")
    config = tmp_path / "carsen.yaml"
    config.write_text(
        f"""
knowledge:
  id: cli-kb
sources:
  code:
    - path: {src}
  documents: []
""",
        encoding="utf-8",
    )

    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 1
            dense_error = None

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "--config", str(config)], input="1 3\n")

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "1. binary/data" in result.stderr
    assert "2 file(s)" in result.stderr
    assert "50 B" in result.stderr
    assert ".fits" in result.stderr
    assert ".npy" in result.stderr
    assert "2. archives" in result.stderr
    assert "payload.zip" in result.stderr
    assert "3. logs/cache/build" in result.stderr
    assert "1 director" in result.stderr
    assert "htmlcov" in result.stderr
    saved = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert ".fits" in saved["indexing"]["ignored_extensions"]
    assert ".npy" in saved["indexing"]["ignored_extensions"]
    assert ".zip" not in saved["indexing"]["ignored_extensions"]
    assert "htmlcov" in saved["indexing"]["ignored_directories"]


def test_index_cli_persists_noisy_ignores_for_named_local_config(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "run.log").write_text("log\n", encoding="utf-8")
    config = tmp_path / "cli-kb.yaml"
    config.write_text(
        f"""
knowledge:
  id: cli-kb
sources:
  code:
    - path: {src}
  documents: []
""",
        encoding="utf-8",
    )

    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 1
            dense_error = None

        return Report()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "cli-kb"], input="1\n")

    assert result.exit_code == 0, result.stdout + result.stderr
    saved = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert ".log" in saved["indexing"]["ignored_extensions"]


def test_cli_resolves_config_path_and_local_name_before_registry(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "ariel-fury.yaml"
    config.write_text(
        """
knowledge:
  id: ariel-fury
sources:
  code: []
  documents: []
""",
        encoding="utf-8",
    )
    registry = tmp_path / "registry"
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(registry))
    monkeypatch.chdir(tmp_path)

    path_result = CliRunner().invoke(app, ["validate", "ariel-fury.yaml"])
    name_result = CliRunner().invoke(app, ["validate", "ariel-fury"])

    assert path_result.exit_code == 0, path_result.stdout
    assert name_result.exit_code == 0, name_result.stdout
    assert "Configuration 'ariel-fury' is valid." in path_result.stdout
    assert "Configuration 'ariel-fury' is valid." in name_result.stdout


def test_index_cli_warns_and_succeeds_when_embedding_fails(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "carsen.yaml"
    config.write_text(
        """
knowledge:
  id: cli-kb
sources:
  code: []
  documents: []
""",
        encoding="utf-8",
    )

    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 2
            dense_error = "embedding batch failed: Invalid buffer size: 32.00 GiB"

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "--config", str(config), "--embed"])

    assert result.exit_code == 0
    assert "Indexed 'cli-kb': new=1 unchanged=0 changed=0 deleted=0 chunks=2" in result.stdout
    assert "Warning: dense vector indexing failed and was skipped" in result.stderr
    assert "Sparse/exact MCP search remains available" in result.stderr
    assert "Invalid buffer size: 32.00 GiB" in result.stderr
    assert "Traceback" not in result.stderr


def test_index_cli_warns_and_succeeds_when_vector_store_fails(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "carsen.yaml"
    config.write_text(
        """
knowledge:
  id: cli-kb
storage:
  qdrant_url: http://127.0.0.1:6333
sources:
  code: []
  documents: []
""",
        encoding="utf-8",
    )
    def fake_index_config(config, force: bool = False, embed: bool = False, progress=None):
        class Report:
            new = 1
            unchanged = 0
            changed = 0
            deleted = 0
            chunks = 2
            dense_error = "could not upsert vectors to Qdrant: [Errno 61] Connection refused"

        return Report()

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.index_config", fake_index_config)

    result = CliRunner().invoke(app, ["index", "--config", str(config), "--embed"])

    assert result.exit_code == 0
    assert "Warning: dense vector indexing failed and was skipped" in result.stderr
    assert "Sparse/exact MCP search remains available" in result.stderr
    assert "could not upsert vectors to Qdrant: [Errno 61] Connection refused" in result.stderr
    assert "Vector store target: Qdrant URL http://127.0.0.1:6333" in result.stderr
    assert "embedding batch size" not in result.stderr
    assert "model memory" not in result.stderr
    assert "Traceback" not in result.stderr


def test_reembed_cli_still_fails_on_vector_store_error(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "carsen.yaml"
    config.write_text(
        """
knowledge:
  id: cli-kb
storage:
  qdrant_url: http://127.0.0.1:6333
sources:
  code: []
  documents: []
""",
        encoding="utf-8",
    )
    from carsen_mcp.ingestion.indexer import VectorIndexError

    def fail_reembed_config(config):
        raise VectorIndexError("could not upsert vectors to Qdrant") from OSError("[Errno 61] Connection refused")

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.reembed_config", fail_reembed_config)

    result = CliRunner().invoke(app, ["reembed", "--config", str(config)])

    assert result.exit_code == 1
    assert "Qdrant/vector store connection failed: could not upsert vectors to Qdrant" in result.stderr
    assert "Configured Qdrant URL: http://127.0.0.1:6333" in result.stderr
    assert "Traceback" not in result.stderr
