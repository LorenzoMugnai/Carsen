from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, ModelProviderConfig, ModelsConfig, StorageConfig
from carsen_mcp.embeddings import FakeEmbeddingProvider
from carsen_mcp.ingestion.indexer import delete_index_config, index_vectors_for_config, reembed_config
from carsen_mcp.mcp.runtime import InstanceRuntime
from carsen_mcp.storage import QdrantVectorStore


def cfg(tmp_path: Path, knowledge_id: str, collection: str | None = None) -> CarsenConfig:
    return CarsenConfig(
        knowledge=KnowledgeConfig(id=knowledge_id),
        storage=StorageConfig(data_directory=tmp_path / knowledge_id, collection=collection),
        models=ModelsConfig(embedding=ModelProviderConfig(provider="fake", model="fake", dimensions=8)),
    )


def chunk(knowledge_id: str, source_path: str, text: str, order: int = 0) -> Chunk:
    return Chunk(knowledge_id, source_path, "text", None, 1, 2, text, order=order, metadata={"source_path": source_path})


def populate(config: CarsenConfig, chunks: list[Chunk]) -> None:
    assert config.storage.data_directory is not None
    store = ChunkStore(config.storage.data_directory)
    by_source: dict[str, list[Chunk]] = {}
    for item in chunks:
        by_source.setdefault(item.source_path, []).append(item)
    for source, items in by_source.items():
        store.replace_file_chunks(source, items)


def test_index_vectors_for_config_upserts_canonical_chunks(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    provider = FakeEmbeddingProvider(dimensions=8)
    vector_store = QdrantVectorStore(QdrantClient(":memory:"), "kb_alpha", dimensions=8)
    target = chunk("alpha", "a.txt", "needle dense target")
    populate(config, [target])

    count = index_vectors_for_config(config, embedding_provider=provider, vector_store=vector_store)

    assert count == 1
    assert vector_store.search(provider.embed_query("needle dense target"), limit=5)[0].chunk_id == target.chunk_id


def test_index_vectors_batches_embeddings_and_preserves_order(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    config.models.embedding.batch_size = 2
    chunks = [chunk("alpha", f"{index}.txt", f"text-{index}", order=index) for index in range(5)]
    populate(config, chunks)

    class SpyProvider:
        dimensions = 2

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(texts)
            return [[float(text.removeprefix("text-")), 0.0] for text in texts]

        def embed_query(self, text: str) -> list[float]:
            return [0.0, 0.0]

    class SpyVectorStore:
        def __init__(self) -> None:
            self.upserts: list[tuple[list[str], list[list[float]]]] = []

        def upsert_chunks(self, upsert_chunks, vectors) -> None:
            self.upserts.append(([item.text for item in upsert_chunks], vectors))

    provider = SpyProvider()
    vector_store = SpyVectorStore()

    count = index_vectors_for_config(config, embedding_provider=provider, vector_store=vector_store)  # type: ignore[arg-type]

    assert count == 5
    assert provider.calls == [["text-0", "text-1"], ["text-2", "text-3"], ["text-4"]]
    assert vector_store.upserts == [
        (["text-0", "text-1"], [[0.0, 0.0], [1.0, 0.0]]),
        (["text-2", "text-3"], [[2.0, 0.0], [3.0, 0.0]]),
        (["text-4"], [[4.0, 0.0]]),
    ]


def test_reembed_recreates_collection_from_chunk_store(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    provider = FakeEmbeddingProvider(dimensions=8)
    vector_store = QdrantVectorStore(QdrantClient(":memory:"), "kb_alpha", dimensions=8)
    first = chunk("alpha", "a.txt", "old target")
    second = chunk("alpha", "b.txt", "new target")
    populate(config, [second])
    vector_store.recreate_collection()
    vector_store.upsert_chunks([first], provider.embed_texts([first.text]))

    count = reembed_config(config, embedding_provider=provider, vector_store=vector_store)

    results = vector_store.search(provider.embed_query("target"), limit=10)
    assert count == 1
    assert {result.chunk_id for result in results} == {second.chunk_id}


def test_delete_index_removes_local_chunks_state_and_collection(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    assert config.storage.data_directory is not None
    provider = FakeEmbeddingProvider(dimensions=8)
    vector_store = QdrantVectorStore(QdrantClient(":memory:"), "kb_alpha", dimensions=8)
    target = chunk("alpha", "a.txt", "target")
    populate(config, [target])
    (config.storage.data_directory / "index_state.sqlite3").write_text("state", encoding="utf-8")
    vector_store.upsert_chunks([target], provider.embed_texts([target.text]))

    existed, error = delete_index_config(config, vector_store=vector_store)

    assert existed is True
    assert error is None
    assert not config.storage.data_directory.exists()
    assert not vector_store.client.collection_exists(vector_store.collection_name)


def test_mcp_search_uses_hybrid_dense_hit_and_sparse_fallback(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    provider = FakeEmbeddingProvider(dimensions=8)
    vector_store = QdrantVectorStore(QdrantClient(":memory:"), "kb_alpha", dimensions=8)
    dense_only = chunk("alpha", "dense.txt", "semantic vector target")
    sparse_only = chunk("alpha", "sparse.txt", "lexical fallback token")
    populate(config, [dense_only, sparse_only])
    vector_store.upsert_chunks([dense_only], provider.embed_texts([dense_only.text]))

    hybrid = InstanceRuntime(config, embedding_provider=provider, vector_store=vector_store).search_knowledge("semantic vector target", limit=1)
    fallback = InstanceRuntime(config).search_knowledge("fallback token", limit=1)

    assert hybrid[0]["chunk_id"] == dense_only.chunk_id
    assert fallback[0]["chunk_id"] == sparse_only.chunk_id


def test_alpha_beta_qdrant_collection_isolation(tmp_path: Path) -> None:
    client = QdrantClient(":memory:")
    provider = FakeEmbeddingProvider(dimensions=8)
    alpha = cfg(tmp_path, "alpha", collection="kb_alpha")
    beta = cfg(tmp_path, "beta", collection="kb_beta")
    alpha_store = QdrantVectorStore(client, "kb_alpha", dimensions=8)
    beta_store = QdrantVectorStore(client, "kb_beta", dimensions=8)
    populate(alpha, [chunk("alpha", "a.txt", "shared alpha")])
    populate(beta, [chunk("beta", "b.txt", "shared beta")])

    index_vectors_for_config(alpha, embedding_provider=provider, vector_store=alpha_store, recreate=True)
    index_vectors_for_config(beta, embedding_provider=provider, vector_store=beta_store, recreate=True)

    assert {result.metadata["knowledge_id"] for result in alpha_store.search(provider.embed_query("shared"), limit=10)} == {"alpha"}
    assert {result.metadata["knowledge_id"] for result in beta_store.search(provider.embed_query("shared"), limit=10)} == {"beta"}
