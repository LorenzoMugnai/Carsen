"""Embedding providers used by retrieval components."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import time
import urllib.error
import urllib.request
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


class OpenAICompatibleEmbeddingProvider:
    """Call an OpenAI-style ``/embeddings`` endpoint over HTTP (stdlib only).

    Works with the OpenAI API and OpenAI-compatible servers such as Ollama,
    text-embeddings-inference (TEI) and Infinity, so retrieval needs no local
    model or PyTorch. ``dimensions`` must be set in configuration and must match
    the endpoint's output for the Qdrant collection to be created correctly.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str,
        dimensions: int,
        api_key: str | None = None,
        batch_size: int = 32,
        timeout: float = 30.0,
        query_instruction: str | None = None,
        max_retries: int = 3,
    ) -> None:
        if dimensions < 1:
            raise ValueError("the openai embedding provider requires models.embedding.dimensions to be set")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.dimensions = dimensions
        self.api_key = api_key or None
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.query_instruction = query_instruction or None
        self.max_retries = max(1, max_retries)

    def _post(self, inputs: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model_name, "input": inputs}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}/embeddings", data=payload, headers=headers, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - configured endpoint
                    body = json.loads(response.read().decode("utf-8"))
                rows = sorted(body["data"], key=lambda item: item.get("index", 0))
                return [list(map(float, row["embedding"])) for row in rows]
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                last_error = RuntimeError(f"embedding endpoint returned HTTP {exc.code}: {detail}")
                if exc.code not in (408, 409, 425, 429, 500, 502, 503, 504):
                    raise last_error from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, KeyError) as exc:
                last_error = RuntimeError(f"embedding endpoint request failed: {exc}")
            if attempt + 1 < self.max_retries:
                time.sleep(0.5 * (2**attempt))
        raise last_error or RuntimeError("embedding endpoint request failed")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._post(texts[start : start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"{self.query_instruction}{text}" if self.query_instruction else text
        return self._post([prefixed])[0]


_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


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
    if provider in {"openai", "openai_compatible", "tei", "infinity"}:
        is_openai = provider == "openai"
        base_url = config.base_url or (_OPENAI_DEFAULT_BASE_URL if is_openai else None)
        if not base_url:
            raise ValueError("models.embedding.base_url is required for the openai_compatible provider")
        api_key_env = config.api_key_env or ("OPENAI_API_KEY" if is_openai else None)
        return OpenAICompatibleEmbeddingProvider(
            config.model,
            base_url=base_url,
            dimensions=config.dimensions or 0,
            api_key=os.environ.get(api_key_env) if api_key_env else None,
            batch_size=config.batch_size,
            timeout=config.timeout,
            query_instruction=config.query_instruction,
        )
    raise ValueError(f"unsupported embedding provider: {config.provider}")
