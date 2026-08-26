from pathlib import Path

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, SourcePathConfig, SourcesConfig, StorageConfig
from carsen_mcp.embeddings import FakeEmbeddingProvider
from carsen_mcp.ingestion.discovery import discover_files, sha256_file
from carsen_mcp.ingestion.indexer import index_config
from carsen_mcp.ingestion.state import FileRecord, IndexState
from carsen_mcp.parsers.markdown import parse_markdown
from carsen_mcp.parsers.python import parse_python
from carsen_mcp.parsers.text import parse_text


def test_python_parser_fixture_symbols(tmp_path: Path) -> None:
    source = tmp_path / "detector.py"
    source.write_text('''import os\n\nclass Detector:\n    """Finds things."""\n    @classmethod\n    def calibrate(cls):\n        return os.name\n\n    async def process(self):\n        return True\n\ndef helper():\n    return Detector()\n''', encoding="utf-8")
    chunks = parse_python(source, "kb", tmp_path)
    symbols = {chunk.symbol: chunk for chunk in chunks}
    assert {"Detector", "Detector.calibrate", "Detector.process", "helper"} <= set(symbols)
    assert symbols["Detector"].kind == "class"
    assert symbols["Detector.calibrate"].metadata["decorators"] == ["classmethod"]
    assert "import os" in symbols["helper"].metadata["imports"]


def test_markdown_and_text_parser_basics(tmp_path: Path) -> None:
    md = tmp_path / "guide.md"
    md.write_text("# One\nBody\n## Two\nMore\n", encoding="utf-8")
    txt = tmp_path / "notes.txt"
    txt.write_text("plain\ntext\n", encoding="utf-8")
    md_chunks = parse_markdown(md, "kb", tmp_path)
    assert [c.metadata["heading"] for c in md_chunks] == ["One", "Two"]
    assert [c.order for c in md_chunks] == [0, 1]
    assert parse_text(txt, "kb", tmp_path)[0].metadata["path"] == "notes.txt"


def test_discovery_ignores_and_hashing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.py").write_text("x", encoding="utf-8")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "cached.py").write_text("x", encoding="utf-8")
    (tmp_path / "site-packages").mkdir()
    (tmp_path / "site-packages" / "installed.py").write_text("x", encoding="utf-8")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "vendored.py").write_text("x", encoding="utf-8")
    (tmp_path / "keep.py").write_text("x", encoding="utf-8")
    (tmp_path / "skip.pyc").write_text("x", encoding="utf-8")
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="kb")).indexing
    assert [p.name for p in discover_files(tmp_path, cfg)] == ["keep.py"]
    assert sha256_file(tmp_path / "keep.py") == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"


def test_chunk_id_stability_and_namespacing() -> None:
    a = Chunk("one", "x.py", "function", "f", 1, 2, "def f(): pass")
    b = Chunk("one", "x.py", "function", "f", 1, 2, "changed text")
    c = Chunk("two", "x.py", "function", "f", 1, 2, "def f(): pass")
    assert a.chunk_id == b.chunk_id
    assert a.chunk_id.startswith("one_chk_")
    assert a.chunk_id != c.chunk_id
    assert a.content_hash != b.content_hash


def test_incremental_state_workflow(tmp_path: Path) -> None:
    state = IndexState(tmp_path)
    rec = FileRecord("a.py", 1.0, 1, "aaa", "c1")
    assert state.classify([rec])["new"] == ["a.py"]
    state.upsert([rec])
    assert state.classify([rec])["unchanged"] == ["a.py"]
    changed = FileRecord("a.py", 2.0, 2, "bbb", "c2")
    added = FileRecord("b.py", 1.0, 1, "ccc", None)
    status = state.classify([changed, added])
    assert status["changed"] == ["a.py"] and status["new"] == ["b.py"]
    state.upsert([changed, added])
    assert state.classify([added])["deleted"] == ["a.py"]


def test_indexer_persists_chunks_and_reports(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(code=[SourcePathConfig(path=src)]),
    )
    report = index_config(cfg)
    assert report.new == 1 and report.chunks >= 2
    assert list((tmp_path / "data" / "chunks").glob("*.jsonl"))


def test_indexer_reports_progress_without_changing_counts(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(code=[SourcePathConfig(path=src)]),
    )
    events: list[tuple[str, dict[str, object]]] = []

    report = index_config(
        cfg,
        progress=lambda event, payload: events.append((event, payload)),
    )

    assert report.new == 1
    assert report.unchanged == 0
    assert report.changed == 0
    assert report.deleted == 0
    assert report.chunks >= 2
    assert [event for event, _ in events] == [
        "discovered",
        "fingerprint_start",
        "file_fingerprinted",
        "fingerprint_complete",
        "classified",
        "parse_start",
        "file_parse_start",
        "file_parsed",
        "parse_complete",
        "deleted",
    ]
    assert events[0][1]["files"] == 1
    assert events[4][1]["to_parse"] == 1
    assert events[6][1]["index"] == 1
    assert events[7][1]["chunk_total"] == report.chunks


def test_indexer_skips_failed_parse_and_retries_next_run(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    src.mkdir()
    bad = src / "bad.pdf"
    good = src / "good.txt"
    bad.write_text("bad", encoding="utf-8")
    good.write_text("good", encoding="utf-8")
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(documents=[SourcePathConfig(path=src)]),
    )
    events: list[tuple[str, dict[str, object]]] = []

    def fake_parse_file(
        path: Path,
        knowledge_id: str,
        root: Path | None = None,
        document_options: object | None = None,
    ) -> list[Chunk]:
        if path == bad:
            raise RuntimeError("parser unavailable")
        return [Chunk(knowledge_id, str(path), "text", None, 1, 1, path.read_text(encoding="utf-8"))]

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.parse_file", fake_parse_file)

    report = index_config(cfg, progress=lambda event, payload: events.append((event, payload)))

    assert report.new == 2
    assert report.unchanged == 0
    assert report.chunks == 1
    failed = [payload for event, payload in events if event == "file_failed"]
    assert failed == [{"path": str(bad), "index": 1, "total": 2, "error": "parser unavailable"}]

    retry_report = index_config(cfg)

    assert retry_report.new == 1
    assert retry_report.unchanged == 1


def test_indexer_embed_failure_records_dense_error_and_keeps_chunks(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("dense optional target", encoding="utf-8")
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(documents=[SourcePathConfig(path=src)]),
    )

    class FailingVectorStore:
        def upsert_chunks(self, chunks, vectors) -> None:
            raise OSError("[Errno 61] Connection refused")

    report = index_config(
        cfg,
        embed=True,
        embedding_provider=FakeEmbeddingProvider(dimensions=8),
        vector_store=FailingVectorStore(),  # type: ignore[arg-type]
    )

    assert report.new == 1
    assert report.chunks == 1
    assert report.dense_error is not None
    assert "could not upsert vectors to Qdrant" in report.dense_error
    assert "Connection refused" in report.dense_error
    assert len(list(ChunkStore(tmp_path / "data").load_all_chunks())) == 1
    assert IndexState(tmp_path / "data").classify([])["deleted"] == [str(src / "a.txt")]
