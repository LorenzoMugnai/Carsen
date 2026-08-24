"""Metadata predicate helpers for retrieval filters."""

from __future__ import annotations

from typing import Any

from .models import SearchResult


def matches_filters(result: SearchResult, filters: dict[str, Any] | None = None) -> bool:
    """Return whether a result satisfies supported metadata predicates."""
    if not filters:
        return True
    for key, expected in filters.items():
        if key in {"path_prefix", "source_path_prefix"}:
            if not str(result.metadata.get("source_path", "")).startswith(str(expected)):
                return False
            continue
        actual = result.metadata.get(key)
        if isinstance(expected, (list, tuple, set, frozenset)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def filter_results(results: list[SearchResult], filters: dict[str, Any] | None = None) -> list[SearchResult]:
    return [result for result in results if matches_filters(result, filters)]


def diversify_by_source(results: list[SearchResult], max_results_per_source: int | None = None) -> list[SearchResult]:
    """Limit repeated hits from the same source path while preserving order."""
    if not max_results_per_source or max_results_per_source < 1:
        return results
    counts: dict[str, int] = {}
    output: list[SearchResult] = []
    for result in results:
        source = str(result.metadata.get("source_path") or result.metadata.get("path") or result.chunk_id)
        if counts.get(source, 0) >= max_results_per_source:
            continue
        counts[source] = counts.get(source, 0) + 1
        output.append(result)
    return output
