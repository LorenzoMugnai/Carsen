"""Retrieval diagnostics for explaining hybrid search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import SearchResult


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Intermediate rankings and payloads captured during retrieval."""

    dense_candidates: list[SearchResult]
    sparse_candidates: list[SearchResult]
    fused_ranking: list[SearchResult]
    reranker_ranking: list[SearchResult]
    final_results: list[SearchResult]
    citations: list[dict[str, Any]] = field(default_factory=list)
    reranker_error: str | None = None


def collect_citations(results: list[SearchResult]) -> list[dict[str, Any]]:
    citations = []
    for result in results:
        citation = result.metadata.get("citation") or result.metadata.get("citation_url")
        if citation:
            citations.append({"chunk_id": result.chunk_id, "citation": citation, "payload": result.metadata})
    return citations
