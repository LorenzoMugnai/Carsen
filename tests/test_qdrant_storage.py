from __future__ import annotations

from qdrant_client import QdrantClient

from ariadne_mcp.chunks.model import Chunk
from ariadne_mcp.embeddings import FakeEmbeddingProvider
from ariadne_mcp.storage import QdrantVectorStore


def make_chunk(knowledge_id: str, source_path: str, symbol: str, text: str, kind: str = "function") -> Chunk:
    return Chunk(
        knowledge_id=knowledge_id,
        source_path=source_path,
        kind=kind,
        symbol=symbol,
        start_line=1,
        end_line=2,
        text=text,
        metadata={"citation": None},
    )


def test_qdrant_collection_isolation_by_name() -> None:
    client = QdrantClient(":memory:")
    embeddings = FakeEmbeddingProvider(dimensions=8)
    first = QdrantVectorStore(client, "kb_first", dimensions=8)
    second = QdrantVectorStore(client, "kb_second", dimensions=8)
    first.recreate_collection()
    second.recreate_collection()

    chunk = make_chunk("first", "a.py", "helper", "shared target")
    first.upsert_chunks([chunk], embeddings.embed_texts([chunk.text]))

    assert first.search(embeddings.embed_query("shared target"), limit=5)
    assert second.search(embeddings.embed_query("shared target"), limit=5) == []


def test_qdrant_upsert_search_payload_and_filters() -> None:
    client = QdrantClient(":memory:")
    embeddings = FakeEmbeddingProvider(dimensions=8)
    store = QdrantVectorStore(client, "kb_dense", dimensions=8)
    store.recreate_collection()
    chunks = [
        make_chunk("kb", "code.py", "Detector.process", "target detector process", kind="method"),
        make_chunk("kb", "guide.md", "Detector", "target detector guide", kind="markdown"),
    ]
    store.upsert_chunks(chunks, embeddings.embed_texts([chunk.text for chunk in chunks]))

    results = store.search(embeddings.embed_query("target detector process"), limit=10, filters={"kind": "method"})

    assert [result.chunk_id for result in results] == [chunks[0].chunk_id]
    assert results[0].text == chunks[0].text
    assert results[0].metadata["knowledge_id"] == "kb"
    assert results[0].metadata["source_path"] == "code.py"
    assert results[0].metadata["symbol"] == "Detector.process"
    assert results[0].metadata["content_hash"] == chunks[0].content_hash


def test_qdrant_delete_by_source_path() -> None:
    client = QdrantClient(":memory:")
    embeddings = FakeEmbeddingProvider(dimensions=8)
    store = QdrantVectorStore(client, "kb_delete", dimensions=8)
    store.recreate_collection()
    chunks = [
        make_chunk("kb", "keep.py", "keep", "keep target"),
        make_chunk("kb", "remove.py", "remove", "remove target"),
    ]
    store.upsert_chunks(chunks, embeddings.embed_texts([chunk.text for chunk in chunks]))

    store.delete_by_source_path("remove.py", knowledge_id="kb")

    remaining = store.search(embeddings.embed_query("target"), limit=10)
    assert {result.metadata["source_path"] for result in remaining} == {"keep.py"}
