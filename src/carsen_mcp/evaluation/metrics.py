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
    """Compute Recall@k and MRR over SearchResult-like objects or dictionaries.

    An ``expected`` entry matches a result by chunk id or by source path, so
    golden datasets can reference stable source paths instead of parser-derived
    chunk ids.
    """

    expected_set = set(expected)
    identifiers = [_result_identifiers(result) for result in results]
    hit_ranks = [index for index, ids in enumerate(identifiers, start=1) if expected_set & ids]
    metrics: dict[str, float] = {}
    for k in ks:
        matched_at_k = {identifier for ids in identifiers[:k] for identifier in ids if identifier in expected_set}
        metrics[f"recall@{k}"] = len(matched_at_k) / len(expected_set) if expected_set else 0.0
    metrics["mrr"] = 1.0 / hit_ranks[0] if hit_ranks else 0.0
    return metrics


def average_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Average metric rows, returning zeroes for an empty evaluation."""

    if not rows:
        return {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0}
    keys = rows[0].keys()
    return {key: sum(row[key] for row in rows) / len(rows) for key in keys}


def _result_identifiers(result: Any) -> set[str]:
    """Return every identifier a golden dataset may reference for one result."""

    if isinstance(result, dict):
        metadata = result.get("metadata") or {}
        candidates = [
            result.get("chunk_id"),
            result.get("id"),
            result.get("source_id"),
            result.get("source_path"),
            metadata.get("source_path"),
            metadata.get("path"),
        ]
    else:
        metadata = getattr(result, "metadata", {}) or {}
        candidates = [
            getattr(result, "chunk_id", None),
            getattr(result, "id", None),
            metadata.get("source_path"),
            metadata.get("path"),
        ]
    return {str(candidate) for candidate in candidates if candidate}
