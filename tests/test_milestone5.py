from __future__ import annotations

from typing import Any

import pytest

from carsen_mcp.reranking import DeterministicReranker, SentenceTransformersCrossEncoderReranker
from carsen_mcp.retrieval import HybridRetrievalConfig, HybridRetriever, SearchResult


def result(chunk_id: str, text: str, score: float = 0.1, **metadata: Any) -> SearchResult:
    return SearchResult(chunk_id=chunk_id, score=score, text=text, metadata=metadata)


class FixedRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        return self.results[:limit]


class FailingReranker:
    def rerank(self, query: str, candidates: list[SearchResult], limit: int) -> list[SearchResult]:
        raise RuntimeError("reranker unavailable")


def test_deterministic_reranker_order_limit_and_score_preservation() -> None:
    candidates = [
        result("a", "unrelated text", score=0.9, symbol="Other"),
        result("b", "calibrate detector threshold", score=0.1, symbol="Detector.calibrate"),
    ]
    reranked = DeterministicReranker().rerank("calibrate detector", candidates, limit=1)
    assert [candidate.chunk_id for candidate in reranked] == ["b"]
    assert reranked[0].metadata["pre_rerank_score"] == 0.1
    assert reranked[0].metadata["reranker_score"] == reranked[0].score


def test_sentence_transformers_cross_encoder_is_lazy() -> None:
    reranker = SentenceTransformersCrossEncoderReranker()
    assert reranker.model_name == "Qwen/Qwen3-Reranker-0.6B"
    assert reranker._model is None


def test_hybrid_reranker_integration_and_diagnostics() -> None:
    dense = FixedRetriever([result("dense", "semantic guess", source_path="a.py")])
    sparse = FixedRetriever([result("lexical", "calibrate detector threshold", source_path="b.py", citation="b.py:1")])
    hybrid = HybridRetriever(dense, sparse, HybridRetrievalConfig(final_results=1), reranker=DeterministicReranker())

    diagnostics = hybrid.search_with_diagnostics("calibrate detector")

    assert diagnostics.final_results[0].chunk_id == "lexical"
    assert [hit.chunk_id for hit in diagnostics.dense_candidates] == ["dense"]
    assert [hit.chunk_id for hit in diagnostics.sparse_candidates] == ["lexical"]
    assert {hit.chunk_id for hit in diagnostics.fused_ranking} == {"dense", "lexical"}
    assert diagnostics.reranker_ranking[0].chunk_id == "lexical"
    assert diagnostics.citations == [{"chunk_id": "lexical", "citation": "b.py:1", "payload": diagnostics.final_results[0].metadata}]


def test_reranker_failure_fallback_preserves_fused_order() -> None:
    dense = FixedRetriever([result("dense", "first", source_path="a.py")])
    sparse = FixedRetriever([result("sparse", "second", source_path="b.py")])
    hybrid = HybridRetriever(dense, sparse, HybridRetrievalConfig(final_results=2, fallback_on_reranker_error=True), reranker=FailingReranker())

    diagnostics = hybrid.search_with_diagnostics("query")

    assert [hit.chunk_id for hit in diagnostics.final_results] == [hit.chunk_id for hit in diagnostics.fused_ranking[:2]]
    assert diagnostics.reranker_error == "reranker unavailable"


def test_reranker_failure_can_be_raised() -> None:
    hybrid = HybridRetriever(FixedRetriever([]), FixedRetriever([result("x", "x")]), HybridRetrievalConfig(fallback_on_reranker_error=False), reranker=FailingReranker())
    with pytest.raises(RuntimeError, match="unavailable"):
        hybrid.search("query")
