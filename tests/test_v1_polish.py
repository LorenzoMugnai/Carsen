from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ariadne_mcp.chunks.model import Chunk
from ariadne_mcp.chunks.store import ChunkStore
from ariadne_mcp.cli import app
from ariadne_mcp.config import AriadneConfig, KnowledgeConfig, StorageConfig, dump_config
from ariadne_mcp.evaluation import evaluate_results, load_evaluation_dataset
from ariadne_mcp.retrieval import SearchResult


def make_config(tmp_path: Path) -> Path:
    cfg = AriadneConfig(knowledge=KnowledgeConfig(id="alpha"), storage=StorageConfig(data_directory=tmp_path / "data"))
    chunk = Chunk("alpha", "src/settings.py", "function", "calibrate", 1, 2, "CALIBRATION_CONSTANT = 42", metadata={"source_type": "code", "source_path": "src/settings.py"})
    ChunkStore(tmp_path / "data").replace_file_chunks(chunk.source_path, [chunk])
    path = tmp_path / "alpha.yaml"
    path.write_text(dump_config(cfg), encoding="utf-8")
    return path


def test_search_cli_normal_and_debug(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    runner = CliRunner()
    normal = runner.invoke(app, ["search", "--config", str(config), "42", "--corpus", "code", "--limit", "1"])
    assert normal.exit_code == 0
    assert "src/settings.py:1-2" in normal.stdout
    assert "CALIBRATION_CONSTANT = 42" in normal.stdout

    debug = runner.invoke(app, ["search", "--config", str(config), "42", "--debug"])
    assert debug.exit_code == 0
    assert "Diagnostics:" in debug.stdout
    assert "sparse_candidates:" in debug.stdout


def test_evaluation_dataset_and_metrics(tmp_path: Path) -> None:
    dataset_path = tmp_path / "eval.yaml"
    dataset_path.write_text("queries:\n  - query: calibrate\n    expected: [a, c]\n", encoding="utf-8")
    dataset = load_evaluation_dataset(dataset_path)
    assert dataset.queries[0].query == "calibrate"
    results = [SearchResult("x", 1, ""), SearchResult("a", 0.9, ""), SearchResult("b", 0.8, ""), SearchResult("c", 0.7, "")]
    metrics = evaluate_results(["a", "c"], results, ks=(5, 10))
    assert metrics["recall@5"] == 1.0
    assert metrics["recall@10"] == 1.0
    assert metrics["mrr"] == 0.5


@pytest.mark.model
@pytest.mark.skip(reason="Example only: real sentence-transformers models are not required in CI.")
def test_optional_real_model_marker_example() -> None:
    assert True


def test_docs_and_changelog_mentions() -> None:
    root = Path(__file__).resolve().parents[1]
    assert "model" in (root / "docs" / "testing.md").read_text(encoding="utf-8")
    assert "ariadne search" in (root / "docs" / "retrieval.md").read_text(encoding="utf-8")
    assert "--embed" in (root / "docs" / "indexing.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "V1 retrieval integration" in changelog
    assert "search diagnostics" in changelog
    assert "evaluation" in changelog
