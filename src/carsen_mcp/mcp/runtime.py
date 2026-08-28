"""Lightweight per-instance runtime backed by the local chunk store."""

from __future__ import annotations

import re
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.citations import CitationFormatter
from carsen_mcp.config import CarsenConfig
from carsen_mcp.embeddings import EmbeddingProvider, embedding_provider_from_config
from carsen_mcp.reranking import Reranker, reranker_from_config
from carsen_mcp.retrieval import (
    DenseRetriever,
    HybridRetrievalConfig,
    HybridRetriever,
    SearchResult,
    SourceExpander,
)
from carsen_mcp.storage import QdrantVectorStore, qdrant_store_from_config


class _StoreSparseRetriever:
    """Adapt ``ChunkStore.search_sparse`` to the ``TextRetriever`` protocol."""

    def __init__(self, store: ChunkStore, knowledge_id: str) -> None:
        self._store = store
        self._knowledge_id = knowledge_id

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        return self._store.search_sparse(query, limit=limit, filters=filters, knowledge_id=self._knowledge_id)


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
        self._sparse_retriever = _StoreSparseRetriever(self.store, config.knowledge.id)
        self._dense_cache: DenseRetriever | None = None
        self._reranker_cache: Reranker | None = None
        self._reranker_loaded = False
        # Tool calls run in worker threads (HTTP transport); guard the lazy
        # model/client construction so it happens exactly once.
        self._init_lock = threading.Lock()

    def knowledge_info(self) -> dict[str, Any]:
        self._log_tool_call("knowledge_info")
        knowledge_id = self.config.knowledge.id
        return {
            "knowledge_id": knowledge_id,
            "name": self.config.knowledge.name,
            "description": self.config.knowledge.description,
            "chunk_count": self.store.count(knowledge_id),
            "source_count": self.store.source_count(knowledge_id),
        }

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
        results = self._sparse_retriever.search(query, limit=limit, filters=merged)
        if not results:
            merged.pop("source_type")
            merged.setdefault("document_type", "code")
            results = self._sparse_retriever.search(query, limit=limit, filters=merged)
        return [self._serialise_result(result) for result in results]

    def search_documents(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._log_tool_call("search_documents", limit=limit, filters=filters)
        merged = {**(filters or {}), "source_type": "documents"}
        return [self._serialise_result(result) for result in self._sparse_retriever.search(query, limit=limit, filters=merged)]

    def find_symbol(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        self._log_tool_call("find_symbol", limit=limit)
        matches = self.store.find_symbol(symbol, limit=limit, knowledge_id=self.config.knowledge.id)
        return [self._serialise_result(self._chunk_to_result(chunk)) for chunk in matches]

    def read_source(self, source_id: str | None = None, chunk_id: str | None = None, previous: int = 0, next: int = 0) -> dict[str, Any]:
        self._log_tool_call("read_source", has_source_id=source_id is not None, has_chunk_id=chunk_id is not None, previous=previous, next=next)
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return {"found": False, "source_id": source_id, "chunk_id": chunk_id}
        expanded = SourceExpander(self.store.chunks_for_source(target.source_path)).surrounding_code(target, before=previous, after=next)
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
        results = [result for result in self._sparse_retriever.search(query, limit=limit + 1) if result.chunk_id != target.chunk_id]
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

    def _dense_retriever(self) -> DenseRetriever:
        """Build the dense retriever once and reuse it across tool calls.

        Constructing the embedding provider and Qdrant client is expensive: the
        sentence-transformers model is loaded from disk on first use, so a fresh
        provider per query would reload the model every time.
        """

        if self._dense_cache is None:
            with self._init_lock:
                if self._dense_cache is None:
                    provider = self.embedding_provider or embedding_provider_from_config(self.config.models.embedding)
                    store = self.vector_store or qdrant_store_from_config(self.config, provider.dimensions)
                    self.embedding_provider = provider
                    self.vector_store = store
                    self._dense_cache = DenseRetriever(provider, store)
        return self._dense_cache

    def _reranker(self) -> Reranker | None:
        """Build the configured reranker once, or ``None`` when reranking is off."""

        if not self._reranker_loaded:
            with self._init_lock:
                if not self._reranker_loaded:
                    if self.config.retrieval.rerank:
                        self._reranker_cache = reranker_from_config(self.config.models.reranker)
                    self._reranker_loaded = True
        return self._reranker_cache

    def _search(self, query: str, limit: int, filters: dict[str, Any] | None) -> list[SearchResult]:
        return self._search_with_debug(query, limit, filters)[0]

    def _search_with_debug(self, query: str, limit: int, filters: dict[str, Any] | None) -> tuple[list[SearchResult], dict[str, Any]]:
        sparse = self._sparse_retriever
        if self.config.retrieval.dense_candidates == 0:
            results = sparse.search(query, limit=limit, filters=filters)
            return results, {"mode": "sparse_only", "sparse_candidates": len(results), "ranking": [self._redacted_result(result) for result in results]}
        try:
            dense = self._dense_retriever()
            config = HybridRetrievalConfig(
                dense_candidates=self.config.retrieval.dense_candidates,
                sparse_candidates=self.config.retrieval.sparse_candidates,
                final_results=limit,
                max_results_per_source=self.config.retrieval.max_results_per_source,
            )
            reranker = self._reranker()
            diagnostics = HybridRetriever(dense, sparse, config=config, reranker=reranker).search_with_diagnostics(query, filters=filters)
            return diagnostics.final_results, {
                "mode": "hybrid",
                "dense_candidates": len(diagnostics.dense_candidates),
                "sparse_candidates": len(diagnostics.sparse_candidates),
                "reranked": reranker is not None and diagnostics.reranker_error is None,
                "fused_ranking": [self._redacted_result(result) for result in diagnostics.fused_ranking],
                "reranker_error": diagnostics.reranker_error,
            }
        except Exception as exc:
            category = _fallback_category(exc)
            detail = _redact_secrets(_compact_exception(exc))
            print(
                f"Carsen MCP dense retrieval unavailable: instance={self.config.knowledge.id} "
                f"category={category} error={exc.__class__.__name__}: {detail}; serving sparse results.",
                file=sys.stderr,
                flush=True,
            )
            results = sparse.search(query, limit=limit, filters=filters)
            return results, {
                "mode": "sparse_fallback",
                "degraded": True,
                "fallback_reason": exc.__class__.__name__,
                "fallback_category": category,
                "fallback_detail": detail,
                "sparse_candidates": len(results),
                "ranking": [self._redacted_result(result) for result in results],
            }

    def _find_chunk(self, source_id: str | None = None, chunk_id: str | None = None) -> Chunk | None:
        if chunk_id:
            found = self.store.get_chunk(chunk_id)
            if found is not None:
                return found
        if source_id:
            return self.store.chunk_by_source(source_id)
        return None

    def _chunk_to_result(self, chunk: Chunk) -> SearchResult:
        metadata = dict(chunk.metadata)
        metadata.update({"knowledge_id": chunk.knowledge_id, "source_path": chunk.source_path, "kind": chunk.kind, "symbol": chunk.symbol, "start_line": chunk.start_line, "end_line": chunk.end_line, "order": chunk.order})
        return SearchResult(chunk.chunk_id, 0.0, chunk.text, metadata)

    def _serialise_result(self, result: SearchResult) -> dict[str, Any]:
        return {"chunk_id": result.chunk_id, "score": result.score, "text": result.text, "metadata": result.metadata, "citation": self.formatter.format(result), "citation_url": result.metadata.get("citation_url")}

    def _redacted_result(self, result: SearchResult) -> dict[str, Any]:
        return {"chunk_id": result.chunk_id, "score": result.score, "citation": self.formatter.format(result), "source_path": result.metadata.get("source_path"), "symbol": result.metadata.get("symbol")}

    def _serialise_chunk(self, chunk: Chunk, include_text: bool) -> dict[str, Any]:
        data = asdict(chunk)
        data["citation"] = self.formatter.format(chunk)
        if not include_text:
            data.pop("text", None)
        return data


_SECRET_RE = re.compile(r"(://)[^/\s:@]+:[^/\s@]+@")
_TOKEN_RE = re.compile(r"\b(api[_-]?key|token|secret|password|bearer)\b\s*[=:]\s*\S+", re.IGNORECASE)


def _redact_secrets(text: str) -> str:
    """Strip embedded credentials and obvious secrets from a diagnostic string."""

    redacted = _SECRET_RE.sub(r"\1***@", text)
    return _TOKEN_RE.sub(lambda match: f"{match.group(1)}=***", redacted)


def _compact_exception(exc: BaseException, limit: int = 200) -> str:
    """Return a short single-line message for an exception and its cause."""

    seen: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(seen) < 3:
        message = str(current).strip().replace("\n", " ")
        if message and message not in seen:
            seen.append(message)
        current = current.__cause__ or current.__context__
    joined = ": ".join(seen) or exc.__class__.__name__
    return joined[:limit]


def _fallback_category(exc: BaseException) -> str:
    """Classify why the dense path failed so operators know where to look."""

    if isinstance(exc, ModuleNotFoundError | ImportError):
        return "missing_dependency"
    if isinstance(exc, ValueError | TypeError | KeyError):
        return "configuration"
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    if "connect" in name or "connection" in text or "timeout" in name or "timed out" in text or "refused" in text:
        return "service_unavailable"
    if "dimension" in text or "vector" in text or "collection" in text:
        return "index"
    return "unknown"
