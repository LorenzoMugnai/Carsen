"""Qdrant dense vector storage integration."""

from __future__ import annotations

import warnings
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    QuantizationSearchParams,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    SearchParams,
    VectorParams,
)

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.config import QdrantTuningConfig
from carsen_mcp.retrieval import SearchResult

#: Metadata keys promoted to top-level payload fields and given a payload index
#: so server-side filtering matches the sparse retriever's filter semantics.
FILTERABLE_KEYS = ("knowledge_id", "source_path", "kind", "source_type", "document_type", "language", "repository_name")

#: Filter keys applied client-side because they are prefix predicates, not equality.
PREFIX_FILTER_KEYS = ("path_prefix", "source_path_prefix")


class QdrantVectorStore:
    """Dense vector store for one Carsen knowledge collection."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        dimensions: int,
        distance: Distance = Distance.COSINE,
        tuning: QdrantTuningConfig | None = None,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.distance = distance
        self.tuning = tuning or QdrantTuningConfig()

    def recreate_collection(self) -> None:
        """Recreate only this instance collection."""

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(collection_name=self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.dimensions,
                distance=self.distance,
                on_disk=self.tuning.on_disk_vectors or None,
            ),
            quantization_config=self._quantization_config(),
            on_disk_payload=self.tuning.on_disk_payload or None,
        )
        self._ensure_payload_indexes()

    def _quantization_config(self) -> Any:
        if self.tuning.quantization == "scalar":
            return ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=self.tuning.quantization_always_ram,
                )
            )
        if self.tuning.quantization == "binary":
            return BinaryQuantization(
                binary=BinaryQuantizationConfig(always_ram=self.tuning.quantization_always_ram)
            )
        return None

    def _search_params(self) -> SearchParams | None:
        quantization_params = None
        if self.tuning.quantization is not None:
            quantization_params = QuantizationSearchParams(
                ignore=False,
                rescore=self.tuning.rescore,
                oversampling=self.tuning.oversampling,
            )
        if self.tuning.hnsw_ef is None and quantization_params is None:
            return None
        return SearchParams(hnsw_ef=self.tuning.hnsw_ef, quantization=quantization_params)

    def ensure_collection(self) -> None:
        """Create this instance collection when it does not already exist."""

        if not self.client.collection_exists(self.collection_name):
            self.recreate_collection()

    def _ensure_payload_indexes(self) -> None:
        """Index the keyword fields Carsen filters on; ignore backends that lack the API."""

        with warnings.catch_warnings():
            # Local (in-memory / on-disk) Qdrant warns that payload indexes are a no-op.
            warnings.simplefilter("ignore")
            for field_name in FILTERABLE_KEYS:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                except Exception:  # noqa: BLE001 - local mode and existing indexes are non-fatal
                    pass

    def delete_collection(self) -> bool:
        """Delete only this instance collection when it exists."""

        if not self.client.collection_exists(self.collection_name):
            return False
        return bool(self.client.delete_collection(collection_name=self.collection_name))

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
        prefixes = [str(filters[key]) for key in PREFIX_FILTER_KEYS if filters and key in filters]
        # Over-fetch when a client-side prefix predicate is present so the final
        # slice still returns up to ``limit`` matches.
        query_limit = limit if not prefixes else max(limit * 4, limit + 20)
        with warnings.catch_warnings():
            # Local Qdrant is brute-force and warns that search_params are ignored.
            warnings.simplefilter("ignore")
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=query_limit,
                query_filter=_filter(filters),
                with_payload=True,
                search_params=self._search_params(),
            )
        points = cast(Any, getattr(response, "points", response))
        results: list[SearchResult] = []
        for point in points:
            payload = dict(point.payload or {})
            if prefixes and not any(str(payload.get("source_path", "")).startswith(prefix) for prefix in prefixes):
                continue
            results.append(
                SearchResult(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    metadata=payload,
                )
            )
        return results[:limit]


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
    # Promote well-known filterable metadata to top-level keys so dense filters
    # use the same names as the sparse retriever (which reads chunk.metadata).
    for key in FILTERABLE_KEYS:
        value = chunk.metadata.get(key)
        if isinstance(value, str | int | float | bool):
            payload.setdefault(key, value)
    payload.update({f"metadata_{key}": value for key, value in chunk.metadata.items() if isinstance(value, str | int | float | bool) or value is None})
    return payload


def _filter(filters: dict[str, Any] | None) -> Filter | None:
    if not filters:
        return None
    conditions: list[Any] = []
    for key, value in filters.items():
        if key in PREFIX_FILTER_KEYS:
            continue
        if isinstance(value, list | tuple | set | frozenset):
            conditions.append(FieldCondition(key=key, match=MatchAny(any=list(value))))
        else:
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=conditions) if conditions else None


def qdrant_store_from_config(config: Any, dimensions: int, client: QdrantClient | None = None) -> QdrantVectorStore:
    """Create a Qdrant vector store for one configured instance."""

    collection = config.storage.collection
    if collection is None:
        raise ValueError("storage.collection is required")
    if client is None and config.storage.qdrant_path is not None:
        client = QdrantClient(path=str(config.storage.qdrant_path), check_compatibility=False)
    return QdrantVectorStore(
        client or QdrantClient(url=config.storage.qdrant_url, check_compatibility=False),
        collection,
        dimensions=dimensions,
        tuning=getattr(config.storage, "tuning", None),
    )
