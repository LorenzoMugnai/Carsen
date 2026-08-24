"""Dense retrieval over a generic vector store."""

from __future__ import annotations

from typing import Any, Protocol

from ariadne_mcp.embeddings import EmbeddingProvider

from .models import SearchResult


class VectorStore(Protocol):
    """Minimal vector store contract used before concrete storage integration."""

    def search(self, query_vector: list[float], limit: int, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        """Return ranked vector hits for a query vector."""
        ...


class DenseRetriever:
    """Embed queries and delegate vector search to the supplied store."""

    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query_vector = self.embedding_provider.embed_query(query)
        return self.vector_store.search(query_vector, limit=limit, filters=filters)
