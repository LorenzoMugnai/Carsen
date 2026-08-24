from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.cli import app
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, ServerConfig, StorageConfig
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


def test_runtime_knowledge_info_searches_and_symbol(tmp_path: Path) -> None:
    config = cfg(tmp_path, "alpha")
    detector = chunk("alpha", "src/detector.py", "Detector.process", "def process detection", 0, source_type="code", language="python", kind="method")
    guide = chunk("alpha", "docs/guide.md", None, "process user guide", 0, source_type="documents", document_type="markdown", heading="Guide", kind="markdown")
    populate(config, [detector, guide])
    runtime = InstanceRuntime(config)

    assert runtime.knowledge_info()["chunk_count"] == 2
    assert runtime.search_code("process")[0]["metadata"]["source_path"] == "src/detector.py"
    assert runtime.search_documents("guide")[0]["metadata"]["source_path"] == "docs/guide.md"
    assert runtime.find_symbol("Detector.process")[0]["chunk_id"] == detector.chunk_id


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
