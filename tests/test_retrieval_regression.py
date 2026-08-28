"""Retrieval-quality regression check over a golden dataset.

Indexes Carsen's own ``docs/`` tree in sparse-only mode (no embedding models,
no Qdrant) and asserts that natural-language queries still retrieve the pages
that answer them. Guards the sparse scorer, tokeniser and runtime wiring
against silent regressions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from carsen_mcp.config import (
    CarsenConfig,
    IndexingConfig,
    KnowledgeConfig,
    RetrievalConfig,
    SourcePathConfig,
    SourcesConfig,
    StorageConfig,
)
from carsen_mcp.evaluation import average_metrics, evaluate_results, load_evaluation_dataset
from carsen_mcp.ingestion.indexer import index_config
from carsen_mcp.mcp.runtime import InstanceRuntime

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
DATASET = Path(__file__).parent / "datasets" / "carsen_self_docs_eval.yaml"


@pytest.mark.regression
def test_self_docs_retrieval_quality(tmp_path: Path) -> None:
    indexing = IndexingConfig()
    indexing.ignored_directories = [*indexing.ignored_directories, "superpowers", "assets", "stylesheets"]
    config = CarsenConfig(
        knowledge=KnowledgeConfig(id="carsen-self-docs-eval"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        retrieval=RetrievalConfig(dense_candidates=0),
        indexing=indexing,
        sources=SourcesConfig(documents=[SourcePathConfig(path=DOCS_DIR)]),
    )
    report = index_config(config)
    assert report.chunks > 100

    runtime = InstanceRuntime(config)
    dataset = load_evaluation_dataset(DATASET)
    rows = [evaluate_results(case.expected, runtime.search_knowledge(case.query, limit=10), ks=(5, 10)) for case in dataset.queries]

    for case, row in zip(dataset.queries, rows, strict=True):
        assert row["recall@10"] == 1.0, f"expected {case.expected} not in top 10 for {case.query!r}"

    metrics = average_metrics(rows)
    assert metrics["recall@5"] >= 0.85, metrics
    assert metrics["mrr"] >= 0.55, metrics
