"""Small YAML dataset loader and retrieval metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    expected: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationDataset:
    queries: list[EvaluationCase]


def load_evaluation_dataset(path: str | Path) -> EvaluationDataset:
    """Load a YAML evaluation dataset with ``queries`` and ``expected`` fields."""

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = []
    for item in raw.get("queries", []):
        expected = item.get("expected", [])
        if isinstance(expected, str):
            expected = [expected]
        cases.append(EvaluationCase(query=item["query"], expected=list(expected)))
    return EvaluationDataset(queries=cases)


def evaluate_results(expected: list[str], results: list[Any], ks: tuple[int, ...] = (5, 10)) -> dict[str, float]:
    """Compute Recall@k and MRR over SearchResult-like objects or dictionaries."""

    expected_set = set(expected)
    ids = [_result_id(result) for result in results]
    metrics = {}
    for k in ks:
        metrics[f"recall@{k}"] = len(expected_set.intersection(ids[:k])) / len(expected_set) if expected_set else 0.0
    reciprocal = 0.0
    for index, result_id in enumerate(ids, start=1):
        if result_id in expected_set:
            reciprocal = 1.0 / index
            break
    metrics["mrr"] = reciprocal
    return metrics


def average_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Average metric rows, returning zeroes for an empty evaluation."""

    if not rows:
        return {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0}
    keys = rows[0].keys()
    return {key: sum(row[key] for row in rows) / len(rows) for key in keys}


def _result_id(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("chunk_id") or result.get("id") or result.get("source_id"))
    return str(getattr(result, "chunk_id", getattr(result, "id", "")))
