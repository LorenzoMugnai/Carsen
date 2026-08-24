"""Hybrid dense and sparse retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .fusion import rrf_fuse
from .models import SearchResult


class TextRetriever(Protocol):
    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]: ...


@dataclass(frozen=True)
class HybridRetrievalConfig:
    dense_candidates: int = 40
    sparse_candidates: int = 40
    final_results: int = 8
    max_results_per_source: int | None = None


class HybridRetriever:
    """Combine dense semantic search with sparse lexical search via RRF."""
    def __init__(self, dense: TextRetriever, sparse: TextRetriever, config: HybridRetrievalConfig | None = None) -> None:
        self.dense = dense
        self.sparse = sparse
        self.config = config or HybridRetrievalConfig()

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        dense_results = self.dense.search(query, limit=self.config.dense_candidates, filters=filters)
        sparse_results = self.sparse.search(query, limit=self.config.sparse_candidates, filters=filters)
        return rrf_fuse([dense_results, sparse_results], limit=self.config.final_results, max_results_per_source=self.config.max_results_per_source)
