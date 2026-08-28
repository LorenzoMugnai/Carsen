from __future__ import annotations

import types

import pytest

from carsen_mcp.config import ModelProviderConfig
from carsen_mcp.embeddings.providers import (
    FastEmbedEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
    embedding_provider_from_config,
)


def test_sentence_transformers_provider_sets_sequence_limit_and_encode_batch(monkeypatch) -> None:
    created = {}

    class FakeModel:
        def __init__(self, model_name: str, device: str | None = None) -> None:
            self.model_name = model_name
            self.device = device
            self.max_seq_length = 9999
            self.encode_calls = []
            created["model"] = self

        def get_sentence_embedding_dimension(self) -> int:
            return 2

        def encode(self, texts, **kwargs):
            self.encode_calls.append((texts, kwargs))
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(
        "carsen_mcp.embeddings.providers.importlib.import_module",
        lambda name: types.SimpleNamespace(SentenceTransformer=FakeModel),
    )
    provider = SentenceTransformersEmbeddingProvider(
        "fake/model",
        device="cpu",
        batch_size=3,
        max_seq_length=128,
    )

    vectors = provider.embed_texts(["a", "b"])
    query = provider.embed_query("q")

    model = created["model"]
    assert model.max_seq_length == 128
    assert vectors == [[1.0, 0.0], [1.0, 0.0]]
    assert query == [1.0, 0.0]
    assert model.encode_calls == [
        (["a", "b"], {"batch_size": 3, "convert_to_numpy": False, "normalize_embeddings": True}),
        (["q"], {"batch_size": 3, "convert_to_numpy": False, "normalize_embeddings": True}),
    ]


def test_embedding_provider_from_config_passes_memory_safety_options(monkeypatch) -> None:
    captured = {}

    class FakeProvider:
        def __init__(
            self, model_name, dimensions=None, device=None, batch_size=8, max_seq_length=1024, query_instruction=None
        ) -> None:
            captured.update(
                model_name=model_name,
                dimensions=dimensions,
                device=device,
                batch_size=batch_size,
                max_seq_length=max_seq_length,
                query_instruction=query_instruction,
            )

    monkeypatch.setattr("carsen_mcp.embeddings.providers.SentenceTransformersEmbeddingProvider", FakeProvider)

    embedding_provider_from_config(
        ModelProviderConfig(
            provider="sentence_transformers",
            model="fake/model",
            dimensions=7,
            device="cpu",
            batch_size=2,
            max_seq_length=256,
            query_instruction="Instruct: retrieve\nQuery: ",
        )
    )

    assert captured == {
        "model_name": "fake/model",
        "dimensions": 7,
        "device": "cpu",
        "batch_size": 2,
        "max_seq_length": 256,
        "query_instruction": "Instruct: retrieve\nQuery: ",
    }


def test_query_instruction_prepended_to_queries_only(monkeypatch) -> None:
    class FakeModel:
        def __init__(self, model_name: str, device: str | None = None) -> None:
            self.max_seq_length = 0
            self.encode_calls: list[tuple[list[str], dict]] = []

        def get_sentence_embedding_dimension(self) -> int:
            return 2

        def encode(self, texts, **kwargs):
            self.encode_calls.append((texts, kwargs))
            return [[1.0, 0.0] for _ in texts]

    model_holder: dict[str, FakeModel] = {}

    def fake_import(name: str):
        def make(model_name, device=None):
            model_holder["model"] = FakeModel(model_name, device)
            return model_holder["model"]

        return types.SimpleNamespace(SentenceTransformer=make)

    monkeypatch.setattr("carsen_mcp.embeddings.providers.importlib.import_module", fake_import)

    provider = SentenceTransformersEmbeddingProvider("fake/model", query_instruction="PREFIX ")
    provider.embed_texts(["doc one"])
    provider.embed_query("my question")

    calls = model_holder["model"].encode_calls
    assert calls[0] == (["doc one"], {"batch_size": 8, "convert_to_numpy": False, "normalize_embeddings": True})
    assert calls[1] == (["my question"], {"batch_size": 1, "convert_to_numpy": False, "normalize_embeddings": True, "prompt": "PREFIX "})


class _FakeTextEmbedding:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls: list[tuple[str, list[str]]] = []

    def embed(self, texts):
        materialised = list(texts)
        self.calls.append(("embed", materialised))
        return [[0.1, 0.2] for _ in materialised]

    def query_embed(self, texts):
        materialised = list(texts)
        self.calls.append(("query_embed", materialised))
        return [[0.3, 0.4] for _ in materialised]


def test_fastembed_provider_embeds_texts_and_prefixes_queries(monkeypatch) -> None:
    monkeypatch.setattr(
        "carsen_mcp.embeddings.providers.importlib.import_module",
        lambda name: types.SimpleNamespace(TextEmbedding=_FakeTextEmbedding),
    )
    provider = FastEmbedEmbeddingProvider("BAAI/bge-small-en-v1.5", dimensions=2, query_instruction="Q: ")

    assert provider.dimensions == 2
    assert provider.embed_texts(["a", "b"]) == [[0.1, 0.2], [0.1, 0.2]]
    assert provider.embed_query("hello") == [0.3, 0.4]
    assert provider._model.calls == [("embed", ["a", "b"]), ("query_embed", ["Q: hello"])]


def test_fastembed_provider_requires_dimensions() -> None:
    with pytest.raises(ValueError):
        FastEmbedEmbeddingProvider("BAAI/bge-small-en-v1.5", dimensions=0)


def test_embedding_provider_from_config_dispatches_fastembed() -> None:
    provider = embedding_provider_from_config(
        ModelProviderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5", dimensions=384)
    )
    assert isinstance(provider, FastEmbedEmbeddingProvider)
    assert provider.dimensions == 384

    with pytest.raises(ValueError):
        embedding_provider_from_config(ModelProviderConfig(provider="fastembed", model="BAAI/bge-small-en-v1.5"))
