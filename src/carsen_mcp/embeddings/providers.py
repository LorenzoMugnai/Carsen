"""Embedding providers used by retrieval components."""

from __future__ import annotations

import hashlib
import importlib
import math
from typing import Any, Protocol

from carsen_mcp.config import ModelProviderConfig


class EmbeddingProvider(Protocol):
    """Protocol for text embedding providers."""

    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed one search query."""
        ...


class FakeEmbeddingProvider:
    """Deterministic lightweight embedding provider for tests and smoke checks."""

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[index % len(digest)] / 255.0) * 2.0) - 1.0 for index in range(self.dimensions)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class SentenceTransformersEmbeddingProvider:
    """Optional sentence-transformers provider imported lazily at runtime."""

    def __init__(
        self,
        model_name: str,
        dimensions: int | None = None,
        device: str | None = None,
        batch_size: int = 8,
        max_seq_length: int | None = 1024,
        query_instruction: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("embedding batch size must be positive")
        self.model_name = model_name
        self.dimensions = dimensions or 0
        self.device = device
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self.query_instruction = query_instruction or None
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                module = importlib.import_module("sentence_transformers")
            except ImportError as exc:
                raise RuntimeError("sentence-transformers is not installed; install the optional embedding dependency") from exc
            SentenceTransformer = module.SentenceTransformer
            kwargs = {"device": self.device} if self.device else {}
            model = SentenceTransformer(self.model_name, **kwargs)
            if self.max_seq_length is not None:
                model.max_seq_length = self.max_seq_length
            self._model = model
            if not self.dimensions:
                self.dimensions = int(model.get_sentence_embedding_dimension() or 0)
        if self._model is None:
            raise RuntimeError("sentence-transformers model could not be loaded")
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=False,
            normalize_embeddings=True,
        )
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query, applying the asymmetric query instruction if set.

        Retrieval models such as Qwen3-Embedding and E5 expect a task prefix on
        the query but not on stored documents; ``query_instruction`` is prepended
        here only, leaving :meth:`embed_texts` (used for indexing) untouched.
        """

        if not self.query_instruction:
            return self.embed_texts([text])[0]
        model = self._load_model()
        vectors = model.encode(
            [text],
            batch_size=1,
            convert_to_numpy=False,
            normalize_embeddings=True,
            prompt=self.query_instruction,
        )
        return list(map(float, vectors[0]))


class FastEmbedEmbeddingProvider:
    """CPU-friendly ONNX embeddings via ``fastembed``, imported lazily at runtime.

    ``fastembed`` avoids a PyTorch dependency, which suits CPU-only and
    low-memory deployments. ``dimensions`` must be set in configuration because
    the Qdrant collection is created before the first vector is produced.
    """

    def __init__(self, model_name: str, dimensions: int, query_instruction: str | None = None) -> None:
        if dimensions < 1:
            raise ValueError("the fastembed provider requires models.embedding.dimensions to be set")
        self.model_name = model_name
        self.dimensions = dimensions
        self.query_instruction = query_instruction or None
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                module = importlib.import_module("fastembed")
            except ImportError as exc:
                raise RuntimeError("fastembed is not installed; install the optional 'fastembed' dependency") from exc
            self._model = module.TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        return [list(map(float, vector)) for vector in model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        model = self._load_model()
        prefixed = f"{self.query_instruction}{text}" if self.query_instruction else text
        query_embed = getattr(model, "query_embed", None)
        vectors = list(query_embed([prefixed]) if callable(query_embed) else model.embed([prefixed]))
        return list(map(float, vectors[0]))


def embedding_provider_from_config(config: ModelProviderConfig) -> EmbeddingProvider:
    """Build an embedding provider from model configuration without eager model loading."""

    provider = config.provider.lower().replace("-", "_")
    if provider in {"fake", "local_fake", "test"}:
        return FakeEmbeddingProvider(dimensions=config.dimensions or 8)
    if provider in {"sentence_transformers", "sentence_transformer"}:
        device = None if config.device == "auto" else config.device
        return SentenceTransformersEmbeddingProvider(
            config.model,
            dimensions=config.dimensions,
            device=device,
            batch_size=config.batch_size,
            max_seq_length=config.max_seq_length,
            query_instruction=config.query_instruction,
        )
    if provider in {"fastembed", "fast_embed"}:
        return FastEmbedEmbeddingProvider(
            config.model,
            dimensions=config.dimensions or 0,
            query_instruction=config.query_instruction,
        )
    raise ValueError(f"unsupported embedding provider: {config.provider}")
