from __future__ import annotations

import math
from typing import Any

import pytest

from ariadne_mcp.embeddings import FakeEmbeddingProvider, SentenceTransformersEmbeddingProvider
from ariadne_mcp.retrieval import DenseRetriever, SearchResult


def dot(a: list[float], b: list[float]) -> float:
    return sum(left * right for left, right in zip(a, b, strict=True))


class InMemoryVectorStore:
    def __init__(self, rows: list[tuple[str, list[float], str, dict[str, Any]]]) -> None:
        self.rows = rows
        self.last_query_vector: list[float] | None = None
        self.last_limit: int | None = None
        self.last_filters: dict[str, Any] | None = None

    def search(self, query_vector: list[float], limit: int, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        self.last_query_vector = query_vector
        self.last_limit = limit
        self.last_filters = filters
        candidates = []
        for chunk_id, vector, text, metadata in self.rows:
            if filters and any(metadata.get(key) != value for key, value in filters.items()):
                continue
            candidates.append(SearchResult(chunk_id=chunk_id, score=dot(query_vector, vector), text=text, metadata=metadata))
        return sorted(candidates, key=lambda result: result.score, reverse=True)[:limit]


def test_fake_embedding_provider_is_deterministic_and_normalised() -> None:
    provider = FakeEmbeddingProvider(dimensions=6)
    first = provider.embed_query("calibrate detector")
    second = provider.embed_texts(["calibrate detector"])[0]
    different = provider.embed_query("process detector")
    assert first == second
    assert first != different
    assert len(first) == 6
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0)


def test_fake_embedding_provider_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="positive"):
        FakeEmbeddingProvider(dimensions=0)


def test_dense_retriever_delegates_ranking_limit_and_filters() -> None:
    provider = FakeEmbeddingProvider(dimensions=4)
    query_vector = provider.embed_query("target")
    rows = [
        ("best", query_vector, "target text", {"kind": "code"}),
        ("filtered", query_vector, "filtered text", {"kind": "docs"}),
        ("other", provider.embed_query("other"), "other text", {"kind": "code"}),
    ]
    store = InMemoryVectorStore(rows)
    retriever = DenseRetriever(provider, store)

    results = retriever.search("target", limit=1, filters={"kind": "code"})

    assert [result.chunk_id for result in results] == ["best"]
    assert store.last_query_vector == query_vector
    assert store.last_limit == 1
    assert store.last_filters == {"kind": "code"}


def test_dense_retriever_rejects_invalid_limit() -> None:
    retriever = DenseRetriever(FakeEmbeddingProvider(), InMemoryVectorStore([]))
    with pytest.raises(ValueError, match="positive"):
        retriever.search("query", limit=0)


def test_sentence_transformers_provider_imports_lazily() -> None:
    provider = SentenceTransformersEmbeddingProvider("missing-or-unneeded-model")
    assert provider.model_name == "missing-or-unneeded-model"
    assert provider._model is None
