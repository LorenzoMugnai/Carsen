"""Sparse lexical retrieval over canonical chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from carsen_mcp.chunks.model import Chunk

from .filters import matches_filters
from .models import SearchResult

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\.]*|[0-9]+")


def tokenise(text: str) -> list[str]:
    """Tokenise source-like text, preserving dotted identifiers."""
    return [token.lower() for token in TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class SparseDocument:
    result: SearchResult
    tokens: Counter[str]
    length: int


class SparseRetriever:
    """Small BM25-like retriever tuned for identifiers and code symbols."""
    def __init__(self, chunks: list[Chunk] | None = None, results: list[SearchResult] | None = None) -> None:
        source_results = results if results is not None else [_chunk_to_result(chunk) for chunk in chunks or []]
        self.documents = [SparseDocument(result, Counter(_document_tokens(result)), len(_document_tokens(result)) or 1) for result in source_results]
        self.average_length = sum(doc.length for doc in self.documents) / len(self.documents) if self.documents else 1.0
        self.document_frequency: Counter[str] = Counter()
        for doc in self.documents:
            self.document_frequency.update(doc.tokens.keys())

    def search(self, query: str, limit: int = 10, filters: dict[str, object] | None = None) -> list[SearchResult]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query_tokens = tokenise(query)
        scored: list[SearchResult] = []
        for doc in self.documents:
            if not matches_filters(doc.result, filters):
                continue
            score = self._score(doc, query_tokens, query)
            if score > 0:
                scored.append(SearchResult(doc.result.chunk_id, score, doc.result.text, doc.result.metadata))
        return sorted(scored, key=lambda result: result.score, reverse=True)[:limit]

    def _score(self, doc: SparseDocument, query_tokens: list[str], raw_query: str) -> float:
        total = 0.0
        k1 = 1.5
        b = 0.75
        n_docs = max(1, len(self.documents))
        for token in query_tokens:
            freq = doc.tokens[token]
            if not freq:
                continue
            df = self.document_frequency[token]
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            total += idf * ((freq * (k1 + 1)) / (freq + k1 * (1 - b + b * doc.length / self.average_length)))
        symbol = str(doc.result.metadata.get("symbol") or "")
        path = str(doc.result.metadata.get("source_path") or "")
        if raw_query == symbol:
            total += 10.0
        elif raw_query.lower() in symbol.lower():
            total += 3.0
        if raw_query in path:
            total += 1.0
        return total


def _chunk_to_result(chunk: Chunk) -> SearchResult:
    metadata = dict(chunk.metadata)
    metadata.update({"knowledge_id": chunk.knowledge_id, "source_path": chunk.source_path, "kind": chunk.kind, "symbol": chunk.symbol, "start_line": chunk.start_line, "end_line": chunk.end_line, "content_hash": chunk.content_hash})
    return SearchResult(chunk.chunk_id, 0.0, chunk.text, metadata)


def _document_tokens(result: SearchResult) -> list[str]:
    return tokenise("\n".join([result.text, str(result.metadata.get("symbol") or ""), str(result.metadata.get("source_path") or ""), str(result.metadata.get("kind") or "")]))
