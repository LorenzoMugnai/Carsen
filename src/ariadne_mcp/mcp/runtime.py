"""Lightweight per-instance runtime backed by the local chunk store."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from ariadne_mcp.chunks.model import Chunk
from ariadne_mcp.chunks.store import ChunkStore
from ariadne_mcp.citations import CitationFormatter
from ariadne_mcp.config import AriadneConfig
from ariadne_mcp.retrieval import SearchResult, SourceExpander, SparseRetriever, lookup_symbol


class InstanceRuntime:
    """Serve tools for exactly one configured knowledge instance."""

    def __init__(self, config: AriadneConfig) -> None:
        if config.storage.data_directory is None:
            raise ValueError("storage.data_directory is required for MCP runtime")
        self.config = config
        self.store = ChunkStore(Path(config.storage.data_directory))
        self.formatter = CitationFormatter()

    @property
    def chunks(self) -> list[Chunk]:
        return [chunk for chunk in self.store.load_all_chunks() if chunk.knowledge_id == self.config.knowledge.id]

    def knowledge_info(self) -> dict[str, Any]:
        chunks = self.chunks
        sources = {chunk.source_path for chunk in chunks}
        return {"knowledge_id": self.config.knowledge.id, "name": self.config.knowledge.name, "description": self.config.knowledge.description, "chunk_count": len(chunks), "source_count": len(sources)}

    def search_knowledge(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return [self._serialise_result(result) for result in self._sparse(filters).search(query, limit=limit, filters=filters)]

    def search_code(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        merged = {**(filters or {}), "source_type": "code"}
        results = self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))
        if not results:
            merged.pop("source_type")
            merged.setdefault("document_type", "code")
            results = self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))
        return [self._serialise_result(result) for result in results]

    def search_documents(self, query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        merged = {**(filters or {}), "source_type": "documents"}
        return [self._serialise_result(result) for result in self._sparse(None).search(query, limit=limit, filters=cast(dict[str, object], merged))]

    def find_symbol(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        results = lookup_symbol([self._chunk_to_result(chunk) for chunk in self.chunks], symbol)[:limit]
        return [self._serialise_result(result) for result in results]

    def read_source(self, source_id: str | None = None, chunk_id: str | None = None, previous: int = 0, next: int = 0) -> dict[str, Any]:
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return {"found": False, "source_id": source_id, "chunk_id": chunk_id}
        expanded = SourceExpander(self.chunks).surrounding_code(target, before=previous, after=next)
        return {"found": True, "chunk": self._serialise_chunk(target, include_text=True), "chunks": [self._serialise_chunk(cast(Chunk, chunk), include_text=True) for chunk in expanded]}

    def get_source_metadata(self, source_id: str | None = None, chunk_id: str | None = None) -> dict[str, Any]:
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return {"found": False, "source_id": source_id, "chunk_id": chunk_id}
        return {"found": True, "metadata": self._serialise_chunk(target, include_text=False)}

    def get_related_sources(self, source_id: str | None = None, chunk_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        target = self._find_chunk(source_id=source_id, chunk_id=chunk_id)
        if target is None:
            return []
        query = " ".join(part for part in [target.symbol, target.metadata.get("heading"), target.text[:200]] if part)
        results = [result for result in self._sparse(None).search(query, limit=limit + 1) if result.chunk_id != target.chunk_id]
        return [self._serialise_result(result) for result in results[:limit]]

    def _sparse(self, filters: dict[str, Any] | None) -> SparseRetriever:
        chunks = self.chunks
        if filters:
            chunks = [chunk for chunk in chunks if all(chunk.metadata.get(k) == v for k, v in filters.items())]
        return SparseRetriever(chunks=chunks)

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

    def _serialise_chunk(self, chunk: Chunk, include_text: bool) -> dict[str, Any]:
        data = asdict(chunk)
        data["citation"] = self.formatter.format(chunk)
        if not include_text:
            data.pop("text", None)
        return data
