"""Qdrant dense vector storage integration."""

from __future__ import annotations

from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from ariadne_mcp.chunks.model import Chunk
from ariadne_mcp.retrieval import SearchResult


class QdrantVectorStore:
    """Dense vector store for one Ariadne knowledge collection."""

    def __init__(self, client: QdrantClient, collection_name: str, dimensions: int, distance: Distance = Distance.COSINE) -> None:
        self.client = client
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.distance = distance

    def recreate_collection(self) -> None:
        """Recreate only this instance collection."""

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(collection_name=self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.dimensions, distance=self.distance),
        )

    def ensure_collection(self) -> None:
        """Create this instance collection when it does not already exist."""

        if not self.client.collection_exists(self.collection_name):
            self.recreate_collection()

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        self.ensure_collection()
        points = [PointStruct(id=_point_id(chunk.chunk_id), vector=vector, payload=_payload(chunk)) for chunk, vector in zip(chunks, vectors, strict=True)]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def delete_by_source_path(self, source_path: str, knowledge_id: str | None = None) -> None:
        self.ensure_collection()
        conditions: list[Any] = [FieldCondition(key="source_path", match=MatchValue(value=source_path))]
        if knowledge_id is not None:
            conditions.append(FieldCondition(key="knowledge_id", match=MatchValue(value=knowledge_id)))
        self.client.delete(collection_name=self.collection_name, points_selector=Filter(must=conditions))

    def search(self, query_vector: list[float], limit: int, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        self.ensure_collection()
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=_filter(filters),
            with_payload=True,
        )
        points = cast(Any, getattr(response, "points", response))
        results: list[SearchResult] = []
        for point in points:
            payload = dict(point.payload or {})
            results.append(
                SearchResult(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    metadata=payload,
                )
            )
        return results


def _point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, chunk_id))


def _payload(chunk: Chunk) -> dict[str, Any]:
    payload = {
        "chunk_id": chunk.chunk_id,
        "knowledge_id": chunk.knowledge_id,
        "source_path": chunk.source_path,
        "kind": chunk.kind,
        "symbol": chunk.symbol,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "text": chunk.text,
        "content_hash": chunk.content_hash,
        "citation": chunk.metadata.get("citation"),
        "citation_url": chunk.metadata.get("citation_url"),
    }
    payload.update({f"metadata_{key}": value for key, value in chunk.metadata.items() if isinstance(value, str | int | float | bool) or value is None})
    return payload


def _filter(filters: dict[str, Any] | None) -> Filter | None:
    if not filters:
        return None
    return Filter(must=[FieldCondition(key=key, match=MatchValue(value=value)) for key, value in filters.items()])
