"""Hybrid dense and sparse retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .diagnostics import RetrievalDiagnostics, collect_citations
from .filters import diversify_by_source
from .fusion import rrf_fuse
from .models import SearchResult


class TextRetriever(Protocol):
    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]: ...


class RerankerLike(Protocol):
    def rerank(self, query: str, candidates: list[SearchResult], limit: int) -> list[SearchResult]: ...


@dataclass(frozen=True)
class HybridRetrievalConfig:
    dense_candidates: int = 40
    sparse_candidates: int = 40
    final_results: int = 8
    max_results_per_source: int | None = None
    fallback_on_reranker_error: bool = True


class HybridRetriever:
    """Combine dense semantic search with sparse lexical search via RRF."""
    def __init__(self, dense: TextRetriever, sparse: TextRetriever, config: HybridRetrievalConfig | None = None, reranker: RerankerLike | None = None) -> None:
        self.dense = dense
        self.sparse = sparse
        self.config = config or HybridRetrievalConfig()
        self.reranker = reranker

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        return self.search_with_diagnostics(query, filters).final_results

    def search_with_diagnostics(self, query: str, filters: dict[str, Any] | None = None) -> RetrievalDiagnostics:
        dense_results = self.dense.search(query, limit=self.config.dense_candidates, filters=filters)
        sparse_results = self.sparse.search(query, limit=self.config.sparse_candidates, filters=filters)
        fused = rrf_fuse([dense_results, sparse_results], limit=max(self.config.final_results, self.config.dense_candidates, self.config.sparse_candidates))
        reranked = fused
        error = None
        if self.reranker is not None:
            try:
                reranked = self.reranker.rerank(query, fused, limit=len(fused))
            except Exception as exc:
                if not self.config.fallback_on_reranker_error:
                    raise
                error = str(exc)
                reranked = fused
        final = diversify_by_source(reranked, self.config.max_results_per_source)[: self.config.final_results]
        return RetrievalDiagnostics(dense_results, sparse_results, fused, reranked, final, collect_citations(final), error)
