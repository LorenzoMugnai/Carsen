"""Lightweight per-instance runtime backed by the local chunk store."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.citations import CitationFormatter
from carsen_mcp.config import CarsenConfig
from carsen_mcp.embeddings import EmbeddingProvider, embedding_provider_from_config
from carsen_mcp.retrieval import (
    DenseRetriever,
    HybridRetrievalConfig,
    HybridRetriever,
    SearchResult,
    SourceExpander,
    SparseRetriever,
    lookup_symbol,
)
from carsen_mcp.storage import QdrantVectorStore, qdrant_store_from_config


class InstanceRuntime:
    """Serve tools for exactly one configured knowledge instance."""

    def __init__(self, config: CarsenConfig, embedding_provider: EmbeddingProvider | None = None, vector_store: QdrantVectorStore | None = None) -> None:
        if config.storage.data_directory is None:
            raise ValueError("storage.data_directory is required for MCP runtime")
        self.config = config
        self.store = ChunkStore(Path(config.storage.data_directory))
        self.formatter = CitationFormatter()
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    @property
    def chunks(self) -> list[Chunk]:
        return [chunk for chunk in self.store.load_all_chunks() if chunk.knowledge_id == self.config.knowledge.id]

    def knowledge_info(self) -> dict[str, Any]:
        self._log_tool_call("knowledge_info")
        chunks = self.chunks
        sources = {chunk.source_path for chunk in chunks}
        return {"knowledge_id": self.config.knowledge.id, "name": self.config.knowledge.name, "description": self.config.knowledge.description, "chunk_count": len(chunks), "source_count": len(sources)}

    def search_knowledge(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._log_tool_call("search_knowledge", limit=limit, filters=filters)
        return [self._serialise_result(result) for result in self._search(query, limit, filters)]

    def search_debug(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return search results plus redacted retrieval diagnostics."""

        self._log_tool_call("search_debug", limit=limit, filters=filters)
        results, diagnostics = self._search_with_debug(query, limit, filters)
        return {"results": [self._serialise_result(result) for result in results], "diagnostics": diagnostics}

    def search_code(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._log_tool_call("search_code", limit=limit, filters=filters)
        merged = {**(filters or {}), "source_type": "code"}
        results = self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))
        if not results:
            merged.pop("source_type")
            merged.setdefault("document_type", "code")
            results = self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))
        return [self._serialise_result(result) for result in results]

    def search_documents(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._log_tool_call("search_documents", limit=limit, filters=filters)
        merged = {**(filters or {}), "source_type": "documents"}
        return [self._serialise_result(result) for result in self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))]

    def find_symbol(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        self._log_tool_call("find_symbol", limit=limit)
        results = lookup_symbol([self._chunk_to_result(chunk) for chunk in self.chunks], symbol)[:limit]
        return [self._serialise_result(result) for result in results]

    def read_source(self, source_id: str | None = None, chunk_id: str | None = None, previous: int = 0, next: int = 0) -> dict[str, Any]:
        self._log_tool_call("read_source", has_source_id=source_id is not None, has_chunk_id=chunk_id is not None, previous=previous, next=next)
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return {"found": False, "source_id": source_id, "chunk_id": chunk_id}
        expanded = SourceExpander(self.chunks).surrounding_code(target, before=previous, after=next)
        return {"found": True, "chunk": self._serialise_chunk(target, include_text=True), "chunks": [self._serialise_chunk(cast(Chunk, chunk), include_text=True) for chunk in expanded]}

    def get_source_metadata(self, source_id: str | None = None, chunk_id: str | None = None) -> dict[str, Any]:
        self._log_tool_call("get_source_metadata", has_source_id=source_id is not None, has_chunk_id=chunk_id is not None)
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return {"found": False, "source_id": source_id, "chunk_id": chunk_id}
        return {"found": True, "metadata": self._serialise_chunk(target, include_text=False)}

    def get_related_sources(self, source_id: str | None = None, chunk_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        self._log_tool_call("get_related_sources", has_source_id=source_id is not None, has_chunk_id=chunk_id is not None, limit=limit)
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return []
        query = " ".join(part for part in [target.symbol, target.metadata.get("heading"), target.text[:200]] if part)
        results = [result for result in self._sparse(None).search(query, limit=limit + 1) if result.chunk_id != target.chunk_id]
        return [self._serialise_result(result) for result in results[:limit]]

    def _log_tool_call(self, tool_name: str, **metadata: Any) -> None:
        safe_parts = [f"instance={self.config.knowledge.id}", f"tool={tool_name}"]
        if "filters" in metadata:
            filters = metadata.pop("filters")
            if isinstance(filters, dict):
                metadata["filter_keys"] = sorted(str(key) for key in filters)
            else:
                metadata["filter_keys"] = []
        safe_parts.extend(f"{key}={value}" for key, value in metadata.items())
        print("Carsen MCP tool call: " + " ".join(safe_parts), file=sys.stderr, flush=True)

    def _sparse(self, filters: dict[str, Any] | None) -> SparseRetriever:
        chunks = self.chunks
        if filters:
            chunks = [chunk for chunk in chunks if all(chunk.metadata.get(k) == v for k, v in filters.items())]
        return SparseRetriever(chunks=chunks)

    def _search(self, query: str, limit: int, filters: dict[str, Any] | None) -> list[SearchResult]:
        return self._search_with_debug(query, limit, filters)[0]

    def _search_with_debug(self, query: str, limit: int, filters: dict[str, Any] | None) -> tuple[list[SearchResult], dict[str, Any]]:
        sparse = self._sparse(None)
        try:
            provider = self.embedding_provider or embedding_provider_from_config(self.config.models.embedding)
            store = self.vector_store or qdrant_store_from_config(self.config, provider.dimensions)
            dense = DenseRetriever(provider, store)
            config = HybridRetrievalConfig(
                dense_candidates=self.config.retrieval.dense_candidates,
                sparse_candidates=self.config.retrieval.sparse_candidates,
                final_results=limit,
                max_results_per_source=self.config.retrieval.max_results_per_source,
            )
            diagnostics = HybridRetriever(dense, sparse, config=config).search_with_diagnostics(query, filters=filters)
            return diagnostics.final_results, {
                "mode": "hybrid",
                "dense_candidates": len(diagnostics.dense_candidates),
                "sparse_candidates": len(diagnostics.sparse_candidates),
                "fused_ranking": [self._redacted_result(result) for result in diagnostics.fused_ranking],
                "reranker_error": diagnostics.reranker_error,
            }
        except Exception as exc:
            results = sparse.search(query, limit=limit, filters=filters)
            return results, {"mode": "sparse_fallback", "fallback_reason": exc.__class__.__name__, "sparse_candidates": len(results), "ranking": [self._redacted_result(result) for result in results]}

    def _find_chunk(self, source_id: str | None = None, chunk_id: str | None = None) -> Chunk | None:
        for chunk in self.chunks:
            if chunk_id and chunk.chunk_id == chunk_id:
                return chunk
            if source_id and (chunk.source_path == source_id or chunk.metadata.get("source_id") == source_id):
                return chunk
        return None

    def _chunk_to_result(self, chunk: Chunk) -> SearchResult:
        metadata = dict(chunk.metadata)
        metadata.update({"knowledge_id": chunk.knowledge_id, "source_path": chunk.source_path, "kind": chunk.kind, "symbol": chunk.symbol, "start_line": chunk.start_line, "end_line": chunk.end_line, "order": chunk.order})
        return SearchResult(chunk.chunk_id, 0.0, chunk.text, metadata)

    def _serialise_result(self, result: SearchResult) -> dict[str, Any]:
        return {"chunk_id": result.chunk_id, "score": result.score, "text": result.text, "metadata": result.metadata, "citation": self.formatter.format(result)}

    def _redacted_result(self, result: SearchResult) -> dict[str, Any]:
        return {"chunk_id": result.chunk_id, "score": result.score, "citation": self.formatter.format(result), "source_path": result.metadata.get("source_path"), "symbol": result.metadata.get("symbol")}

    def _serialise_chunk(self, chunk: Chunk, include_text: bool) -> dict[str, Any]:
        data = asdict(chunk)
        data["citation"] = self.formatter.format(chunk)
        if not include_text:
            data.pop("text", None)
        return data
