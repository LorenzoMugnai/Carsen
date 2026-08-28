from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.cli import app
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, ModelProviderConfig, ServerConfig, StorageConfig
from carsen_mcp.embeddings import FakeEmbeddingProvider
from carsen_mcp.mcp.runtime import InstanceRuntime


def cfg(tmp_path: Path, knowledge_id: str) -> CarsenConfig:
    return CarsenConfig(knowledge=KnowledgeConfig(id=knowledge_id), storage=StorageConfig(data_directory=tmp_path / knowledge_id), server=ServerConfig(transport="stdio", port=8123))


def chunk(knowledge_id: str, source_path: str, symbol: str | None, text: str, order: int, **metadata: object) -> Chunk:
    kind_value = metadata.get("kind", "function")
    kind = kind_value if isinstance(kind_value, str) else "function"
    return Chunk(knowledge_id, source_path, kind, symbol, order * 10 + 1, order * 10 + 5, text, order=order, metadata={"source_path": source_path, "order": order, **metadata})


def populate(config: CarsenConfig, chunks: list[Chunk]) -> None:
    assert config.storage.data_directory is not None
    by_path: dict[str, list[Chunk]] = {}
    for item in chunks:
        by_path.setdefault(item.source_path, []).append(item)
    store = ChunkStore(config.storage.data_directory)
    for source_path, items in by_path.items():
        store.replace_file_chunks(source_path, items)


def test_runtime_knowledge_info_searches_and_symbol(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = cfg(tmp_path, "alpha")
    detector = chunk(
        "alpha",
        "src/detector.py",
        "Detector.process",
        "def process detection",
        0,
        source_type="code",
        language="python",
        kind="method",
        citation_url="https://github.com/org/repo/blob/abc/src/detector.py#L1-L5",
    )
    guide = chunk("alpha", "docs/guide.md", None, "process user guide", 0, source_type="documents", document_type="markdown", heading="Guide", kind="markdown")
    populate(config, [detector, guide])
    runtime = InstanceRuntime(config)

    assert runtime.knowledge_info()["chunk_count"] == 2
    code_result = runtime.search_code("process")[0]
    assert code_result["metadata"]["source_path"] == "src/detector.py"
    assert code_result["citation_url"] == "https://github.com/org/repo/blob/abc/src/detector.py#L1-L5"
    assert runtime.search_documents("guide")[0]["metadata"]["source_path"] == "docs/guide.md"
    assert runtime.find_symbol("Detector.process")[0]["chunk_id"] == detector.chunk_id
    stderr = capsys.readouterr().err
    assert "instance=alpha tool=knowledge_info" in stderr
    assert "instance=alpha tool=search_code limit=8" in stderr
    assert "process user guide" not in stderr


def test_runtime_sparse_only_mode_does_not_load_dense_provider(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    config.retrieval.dense_candidates = 0
    target = chunk("alpha", "src/target.py", "target", "sparse only target", 0, source_type="code")
    populate(config, [target])

    class ExplodingEmbeddingProvider:
        dimensions = 8

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            raise AssertionError("dense provider should not be used")

        def embed_query(self, text: str) -> list[float]:
            raise AssertionError("dense provider should not be used")

    runtime = InstanceRuntime(config, embedding_provider=ExplodingEmbeddingProvider())  # type: ignore[arg-type]

    debug = runtime.search_debug("target", limit=3)

    assert debug["diagnostics"]["mode"] == "sparse_only"
    assert debug["results"][0]["chunk_id"] == target.chunk_id


def test_runtime_reuses_loaded_chunks_between_tool_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = cfg(tmp_path, "alpha")
    target = chunk("alpha", "config.xml", None, '<channel name="AIRS-CH1"><detector pixels="64 x 64" /></channel>', 0, source_type="documents", document_type="xml")
    populate(config, [target])
    runtime = InstanceRuntime(config)
    calls = 0
    original = runtime.store.load_all_chunks

    def counting_load_all_chunks() -> list[Chunk]:
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(runtime.store, "load_all_chunks", counting_load_all_chunks)

    runtime.knowledge_info()
    runtime.search_documents("airs ch1 pixels")

    assert calls == 1


def test_runtime_reloads_after_chunk_store_changes(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    populate(config, [chunk("alpha", "src/a.py", "a", "alpha calibrate detector", 0, source_type="code")])
    runtime = InstanceRuntime(config)

    assert runtime.knowledge_info()["chunk_count"] == 1
    assert runtime.search_code("beta") == []

    populate(config, [chunk("alpha", "src/b.py", "b", "beta calibrate detector", 0, source_type="code")])

    assert runtime.knowledge_info()["chunk_count"] == 2
    reloaded = runtime.search_code("beta")
    assert reloaded and reloaded[0]["metadata"]["source_path"] == "src/b.py"


def test_runtime_reuses_sparse_retriever_between_tool_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = cfg(tmp_path, "alpha")
    target = chunk("alpha", "config.xml", None, '<channel name="AIRS-CH1"><detector pixels="64 x 64" /></channel>', 0, source_type="documents", document_type="xml")
    populate(config, [target])
    runtime = InstanceRuntime(config)
    calls = 0

    class CountingSparseRetriever:
        def __init__(self, chunks=None, results=None):
            nonlocal calls
            calls += 1
            from carsen_mcp.retrieval.sparse import SparseRetriever

            self.inner = SparseRetriever(chunks=chunks, results=results)

        def search(self, query: str, limit: int = 10, filters: dict[str, object] | None = None):
            return self.inner.search(query, limit, filters)

    monkeypatch.setattr("carsen_mcp.mcp.runtime.SparseRetriever", CountingSparseRetriever)

    runtime.search_documents("airs ch1 pixels")
    runtime.search_documents("airs ch1 detector")

    assert calls == 1


def test_runtime_builds_dense_retriever_once_across_searches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = cfg(tmp_path, "alpha")
    config.retrieval.dense_candidates = 5
    config.retrieval.sparse_candidates = 5
    populate(config, [chunk("alpha", "src/a.py", "a", "dense reuse target", 0, source_type="code")])

    class FakeStore:
        def search(self, query_vector: list[float], limit: int, filters: dict[str, object] | None = None):
            return []

    from carsen_mcp.retrieval import DenseRetriever as RealDenseRetriever

    builds = 0

    def counting_dense_retriever(provider: object, store: object) -> RealDenseRetriever:
        nonlocal builds
        builds += 1
        return RealDenseRetriever(provider, store)  # type: ignore[arg-type]

    monkeypatch.setattr("carsen_mcp.mcp.runtime.DenseRetriever", counting_dense_retriever)
    runtime = InstanceRuntime(config, embedding_provider=FakeEmbeddingProvider(8), vector_store=FakeStore())  # type: ignore[arg-type]

    runtime.search_knowledge("dense reuse target", limit=3)
    runtime.search_knowledge("another unrelated query", limit=3)

    assert builds == 1


class _EmptyDenseStore:
    def search(self, query_vector: list[float], limit: int, filters: dict[str, object] | None = None):
        return []


def test_runtime_applies_reranker_when_retrieval_rerank_enabled(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    config.retrieval.rerank = True
    config.models.reranker = ModelProviderConfig(provider="deterministic", model="unused")
    populate(
        config,
        [
            chunk("alpha", "src/a.py", "a", "calibrate detector routine", 0, source_type="code"),
            chunk("alpha", "src/b.py", "b", "unrelated helper", 1, source_type="code"),
        ],
    )
    runtime = InstanceRuntime(config, embedding_provider=FakeEmbeddingProvider(8), vector_store=_EmptyDenseStore())  # type: ignore[arg-type]

    debug = runtime.search_debug("calibrate detector", limit=2)

    assert debug["diagnostics"]["mode"] == "hybrid"
    assert debug["diagnostics"]["reranked"] is True
    assert debug["results"][0]["metadata"]["source_path"] == "src/a.py"
    assert "reranker_score" in debug["results"][0]["metadata"]


def test_runtime_does_not_build_reranker_when_disabled(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    config.models.reranker = ModelProviderConfig(provider="deterministic", model="unused")
    populate(config, [chunk("alpha", "src/a.py", "a", "calibrate detector routine", 0, source_type="code")])
    runtime = InstanceRuntime(config, embedding_provider=FakeEmbeddingProvider(8), vector_store=_EmptyDenseStore())  # type: ignore[arg-type]

    debug = runtime.search_debug("calibrate detector", limit=2)

    assert debug["diagnostics"].get("reranked") is False
    assert runtime._reranker() is None


def test_runtime_dense_failure_falls_back_to_sparse_with_redacted_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = cfg(tmp_path, "alpha")
    config.retrieval.dense_candidates = 5
    populate(config, [chunk("alpha", "src/a.py", "a", "calibrate detector routine", 0, source_type="code")])

    class BrokenStore:
        def search(self, query_vector: list[float], limit: int, filters: dict[str, object] | None = None):
            raise ConnectionError("could not connect to http://user:secretpw@qdrant:6333")

    runtime = InstanceRuntime(config, embedding_provider=FakeEmbeddingProvider(8), vector_store=BrokenStore())  # type: ignore[arg-type]

    debug = runtime.search_debug("calibrate detector", limit=2)
    diagnostics = debug["diagnostics"]

    assert diagnostics["mode"] == "sparse_fallback"
    assert diagnostics["degraded"] is True
    assert diagnostics["fallback_category"] == "service_unavailable"
    assert "secretpw" not in diagnostics["fallback_detail"]
    assert debug["results"][0]["metadata"]["source_path"] == "src/a.py"

    stderr = capsys.readouterr().err
    assert "dense retrieval unavailable" in stderr
    assert "secretpw" not in stderr


def test_runtime_xml_fact_query_returns_focused_detector_chunk(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    target = Chunk(
        "alpha",
        "payload/airs_ch1.xml",
        "document",
        "root/detector",
        10,
        14,
        "<detector>\n  <spatial_pix>64</spatial_pix>\n  <spectral_pix>130</spectral_pix>\n</detector>",
        order=1,
        metadata={"source_path": "payload/airs_ch1.xml", "path": "payload/airs_ch1.xml", "source_type": "documents", "document_type": "xml", "xml_path": "root/detector"},
    )
    broader = Chunk(
        "alpha",
        "payload/airs_ch1.xml",
        "document",
        "root",
        1,
        20,
        "<root> lots of optics text AIRS CH1 detector pixels spatial spectral </root>",
        order=0,
        metadata={"source_path": "payload/airs_ch1.xml", "path": "payload/airs_ch1.xml", "source_type": "documents", "document_type": "xml", "xml_path": "root"},
    )
    populate(config, [broader, target])

    result = InstanceRuntime(config).search_documents("numero di pixel di airs ch1", limit=1)[0]

    assert result["chunk_id"] == target.chunk_id
    assert "<spectral_pix>130</spectral_pix>" in result["text"]
    assert result["metadata"]["xml_path"] == "root/detector"


def test_runtime_read_source_expansion_and_metadata(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    chunks = [
        chunk("alpha", "src/detector.py", "Detector", "class Detector", 0, source_type="code", kind="class"),
        chunk("alpha", "src/detector.py", "Detector.process", "def process", 1, source_type="code", kind="method"),
        chunk("alpha", "src/detector.py", "Detector.calibrate", "def calibrate", 2, source_type="code", kind="method"),
    ]
    populate(config, chunks)
    runtime = InstanceRuntime(config)

    read = runtime.read_source(chunk_id=chunks[1].chunk_id, previous=1, next=1)
    assert [item["chunk_id"] for item in read["chunks"]] == [item.chunk_id for item in chunks]
    metadata = runtime.get_source_metadata(chunk_id=chunks[1].chunk_id)["metadata"]
    assert metadata["chunk_id"] == chunks[1].chunk_id
    assert "text" not in metadata


def test_runtime_related_sources_and_instance_isolation(tmp_path: Path) -> None:
    alpha = cfg(tmp_path, "alpha")
    beta = cfg(tmp_path, "beta")
    alpha_chunk = chunk("alpha", "src/a.py", "alpha", "shared token alpha", 0, source_type="code")
    alpha_related = chunk("alpha", "src/b.py", "beta", "shared token neighbour", 0, source_type="code")
    beta_chunk = chunk("beta", "src/a.py", "beta", "shared token beta", 0, source_type="code")
    populate(alpha, [alpha_chunk, alpha_related])
    populate(beta, [beta_chunk])

    related = InstanceRuntime(alpha).get_related_sources(chunk_id=alpha_chunk.chunk_id)
    assert [item["chunk_id"] for item in related] == [alpha_related.chunk_id]
    assert InstanceRuntime(beta).search_knowledge("alpha") == []


def test_cli_serve_transport_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    config_path.write_text(f"knowledge:\n  id: alpha\nstorage:\n  data_directory: {data_dir}\nserver:\n  transport: http\n  port: 9001\n", encoding="utf-8")
    called = {}

    def fake_run(config: CarsenConfig, transport: str | None = None) -> None:
        called["knowledge_id"] = config.knowledge.id
        called["transport"] = transport

    monkeypatch.setattr("carsen_mcp.mcp.server.run_mcp_server", fake_run)
    result = CliRunner().invoke(app, ["serve", "--config", str(config_path), "--transport", "stdio"])

    assert result.exit_code == 0
    assert called == {"knowledge_id": "alpha", "transport": "stdio"}
    assert "Serving Carsen instance 'alpha'" in result.output
    assert "via stdio" in result.output


def test_cli_serve_watch_override_starts_watcher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    config_path.write_text(
        f"knowledge:\n  id: alpha\nstorage:\n  data_directory: {data_dir}\nindexing:\n  watch: false\n",
        encoding="utf-8",
    )
    calls: dict[str, object] = {}

    class FakeStopEvent:
        def set(self) -> None:
            calls["stopped"] = True

    def fake_start_watch_thread(config: CarsenConfig, log=None):
        calls["watched"] = config.knowledge.id
        if log is not None:
            log("watch started")
        return object(), FakeStopEvent()

    def fake_run(config: CarsenConfig, transport: str | None = None) -> None:
        calls["served"] = config.knowledge.id

    monkeypatch.setattr("carsen_mcp.ingestion.watcher.start_watch_thread", fake_start_watch_thread)
    monkeypatch.setattr("carsen_mcp.mcp.server.run_mcp_server", fake_run)

    result = CliRunner().invoke(app, ["serve", "--config", str(config_path), "--watch"])

    assert result.exit_code == 0, result.output
    assert calls == {"watched": "alpha", "served": "alpha", "stopped": True}
    assert "watch started" in result.output


def test_cli_watch_command_calls_watcher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    config_path.write_text(f"knowledge:\n  id: alpha\nstorage:\n  data_directory: {data_dir}\n", encoding="utf-8")
    calls = {}

    def fake_watch_config(config: CarsenConfig, log=None) -> None:
        calls["knowledge_id"] = config.knowledge.id
        if log is not None:
            log("watching")

    monkeypatch.setattr("carsen_mcp.ingestion.watcher.watch_config", fake_watch_config)

    result = CliRunner().invoke(app, ["watch", "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert calls == {"knowledge_id": "alpha"}
    assert "watching" in result.output
