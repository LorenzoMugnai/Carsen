"""Reranker implementations and protocols."""

from __future__ import annotations

import importlib
from dataclasses import replace
from typing import Protocol

from ariadne_mcp.retrieval.models import SearchResult


class Reranker(Protocol):
    """Protocol for reranking retrieval candidates."""

    def rerank(self, query: str, candidates: list[SearchResult], limit: int) -> list[SearchResult]:
        """Return candidates in reranked order."""
        ...


class DeterministicReranker:
    """Predictable lexical-overlap reranker for tests and local smoke checks."""

    def rerank(self, query: str, candidates: list[SearchResult], limit: int) -> list[SearchResult]:
        query_terms = {term.lower() for term in query.split()}
        scored: list[SearchResult] = []
        for index, candidate in enumerate(candidates):
            text_terms = set(candidate.text.lower().split())
            symbol = str(candidate.metadata.get("symbol") or "").lower()
            score = float(len(query_terms & text_terms)) + (2.0 if query.lower() == symbol else 0.0) + (1.0 / (index + 1000))
            metadata = dict(candidate.metadata)
            metadata["reranker_score"] = score
            metadata["pre_rerank_score"] = candidate.score
            scored.append(replace(candidate, score=score, metadata=metadata))
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:limit]


class SentenceTransformersCrossEncoderReranker:
    """Optional CrossEncoder reranker imported lazily only when used."""

    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-0.6B", device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                module = importlib.import_module("sentence_transformers")
            except ImportError as exc:
                raise RuntimeError("sentence-transformers is not installed; install the optional reranking dependency") from exc
            kwargs = {"device": self.device} if self.device else {}
            self._model = module.CrossEncoder(self.model_name, **kwargs)
        return self._model

    def rerank(self, query: str, candidates: list[SearchResult], limit: int) -> list[SearchResult]:
        model = self._load_model()
        scores = model.predict([(query, candidate.text) for candidate in candidates])
        reranked = []
        for candidate, score in zip(candidates, scores, strict=True):
            metadata = dict(candidate.metadata)
            metadata["reranker_score"] = float(score)
            metadata["pre_rerank_score"] = candidate.score
            reranked.append(replace(candidate, score=float(score), metadata=metadata))
        reranked.sort(key=lambda result: result.score, reverse=True)
        return reranked[:limit]
