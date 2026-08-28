"""Sparse lexical retrieval over canonical chunks.

Two retrievers share this module's tokeniser and scoring bonuses:

- :class:`SparseRetriever` scores an in-memory chunk list (used by tests and by
  callers that already hold chunks).
- ``ChunkStore.search_sparse`` runs the same tokenisation against a SQLite FTS5
  index and re-applies :func:`symbol_path_bonus` to the candidates.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from carsen_mcp.chunks.model import Chunk

from .filters import matches_filters
from .models import SearchResult

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\.]*|[0-9]+")
SPLIT_RE = re.compile(r"[A-Za-z]+|[0-9]+")
MAX_INDEXED_TEXT_CHARS = 200_000


def tokenise(text: str) -> list[str]:
    """Tokenise source-like text, preserving dotted identifiers."""
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text):
        for candidate in _token_variants(token):
            tokens.append(candidate)
            if candidate.endswith("s") and len(candidate) > 3:
                tokens.append(candidate[:-1])
    return tokens


def fts_match_query(query: str) -> str:
    """Build an FTS5 MATCH expression from the code-aware tokeniser.

    Tokens are OR-ed so recall matches the in-memory retriever; each is quoted so
    dotted identifiers survive as adjacent-term phrases after FTS5's own
    ``unicode61`` pass.
    """

    tokens = list(dict.fromkeys(tokenise(query)))
    if not tokens:
        return ""
    return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)


def symbol_path_bonus(raw_query: str, query_tokens: Sequence[str], metadata: Mapping[str, Any], doc_tokens: set[str]) -> float:
    """Score adjustments for symbol, path and XML-path matches.

    Shared by the in-memory scorer and the SQLite FTS path so both rank exact
    symbol hits and structural matches the same way.
    """

    total = 0.0
    symbol = str(metadata.get("symbol") or "")
    path = str(metadata.get("source_path") or "")
    if raw_query == symbol:
        total += 10.0
    elif raw_query.lower() in symbol.lower():
        total += 3.0
    if raw_query in path:
        total += 1.0
    xml_path = str(metadata.get("xml_path") or "")
    if metadata.get("document_type") == "xml" and "/" in xml_path:
        xml_path_tokens = set(tokenise(xml_path))
        if any(token in xml_path_tokens for token in query_tokens):
            total += 1.5
        pixel_tokens = {"pixel", "pixels", "pix"}
        if pixel_tokens.intersection(query_tokens) and pixel_tokens.intersection(doc_tokens):
            total += 1.5
    return total


def _token_variants(token: str) -> list[str]:
    lowered = token.lower()
    variants = [lowered]
    parts = [part.lower() for part in SPLIT_RE.findall(token)]
    variants.extend(parts)
    if "pix" in parts:
        variants.append("pixel")
        variants.append("pixels")
    return list(dict.fromkeys(variants))


@dataclass(frozen=True)
class SparseDocument:
    result: SearchResult
    tokens: Counter[str]
    length: int


class SparseRetriever:
    """Small BM25-like retriever tuned for identifiers and code symbols."""
    def __init__(self, chunks: list[Chunk] | None = None, results: list[SearchResult] | None = None) -> None:
        source_results = results if results is not None else [chunk_to_search_result(chunk) for chunk in chunks or []]
        self.documents = [SparseDocument(result, Counter(document_tokens(result)), len(document_tokens(result)) or 1) for result in source_results]
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
        total += symbol_path_bonus(raw_query, query_tokens, doc.result.metadata, set(doc.tokens))
        return total


def chunk_to_search_result(chunk: Chunk) -> SearchResult:
    """Project a canonical chunk into a zero-scored :class:`SearchResult`."""

    metadata = dict(chunk.metadata)
    metadata.update({"knowledge_id": chunk.knowledge_id, "source_path": chunk.source_path, "kind": chunk.kind, "symbol": chunk.symbol, "start_line": chunk.start_line, "end_line": chunk.end_line, "content_hash": chunk.content_hash})
    return SearchResult(chunk.chunk_id, 0.0, chunk.text, metadata)


def document_tokens(result: SearchResult) -> list[str]:
    """Tokens indexed for one result: text plus symbol, XML path, source path and kind."""

    indexed_text = result.text[:MAX_INDEXED_TEXT_CHARS]
    return tokenise("\n".join([indexed_text, str(result.metadata.get("symbol") or ""), str(result.metadata.get("xml_path") or ""), str(result.metadata.get("source_path") or ""), str(result.metadata.get("kind") or "")]))
