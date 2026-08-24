from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.cli import app
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, StorageConfig, dump_config


def write_eval_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="eval"), storage=StorageConfig(data_directory=tmp_path / "data"))
    target = Chunk("eval", "src/constants.py", "function", "calibrate", 1, 2, "CALIBRATION_CONSTANT = 42", metadata={"source_type": "code", "source_path": "src/constants.py"})
    other = Chunk("eval", "src/other.py", "function", "helper", 1, 2, "unrelated helper", metadata={"source_type": "code", "source_path": "src/other.py"})
    store = ChunkStore(tmp_path / "data")
    store.replace_file_chunks(target.source_path, [target])
    store.replace_file_chunks(other.source_path, [other])
    config_path = tmp_path / "eval.yaml"
    config_path.write_text(dump_config(cfg), encoding="utf-8")
    dataset_path = tmp_path / "dataset.yaml"
    dataset_path.write_text(f"queries:\n  - query: calibration 42\n    expected: [{target.chunk_id}]\n", encoding="utf-8")
    return config_path, dataset_path, target.chunk_id


def test_evaluate_cli_with_config(tmp_path: Path) -> None:
    config_path, dataset_path, _ = write_eval_fixture(tmp_path)
    result = CliRunner().invoke(app, ["evaluate", "--config", str(config_path), str(dataset_path)])
    assert result.exit_code == 0
    assert "query_count: 1" in result.stdout
    assert "recall@5: 1.0000" in result.stdout
    assert "recall@10: 1.0000" in result.stdout
    assert "mrr: 1.0000" in result.stdout


def test_cli_reference_documents_key_commands() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "cli-reference.md").read_text(encoding="utf-8")
    for command in ["carsen search", "carsen evaluate", "carsen serve-all", "carsen index", "carsen delete-index"]:
        assert command in text
    section_heading = "## `carsen init-self`"
    assert section_heading in text
    section_start = text.index(section_heading)
    next_section_start = text.find("\n## `", section_start + len(section_heading))
    init_self_section = text[section_start:] if next_section_start == -1 else text[section_start:next_section_start]
    for option in ["--docs-path", "--source", "--name", "--index", "--force"]:
        assert option in init_self_section


def test_testing_docs_mentions_optional_smoke_marker() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "testing.md").read_text(encoding="utf-8")
    assert "@pytest.mark.smoke" in text
    assert "@pytest.mark.model" in text
