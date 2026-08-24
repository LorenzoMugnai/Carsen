"""Reciprocal Rank Fusion for retrieval result lists."""

from __future__ import annotations

from dataclasses import replace
from .filters import diversify_by_source
from .models import SearchResult


def rrf_fuse(result_lists: list[list[SearchResult]], limit: int = 10, k: int = 60, max_results_per_source: int | None = None) -> list[SearchResult]:
    scores: dict[str, float] = {}
    best: dict[str, SearchResult] = {}
    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
            best.setdefault(result.chunk_id, result)
    fused = [replace(best[chunk_id], score=score) for chunk_id, score in scores.items()]
    fused.sort(key=lambda result: result.score, reverse=True)
    return diversify_by_source(fused, max_results_per_source)[:limit]
