from pathlib import Path

from ariadne_mcp.chunks.model import Chunk
from ariadne_mcp.config import AriadneConfig, KnowledgeConfig, SourcePathConfig, SourcesConfig, StorageConfig
from ariadne_mcp.ingestion.discovery import discover_files, sha256_file
from ariadne_mcp.ingestion.indexer import index_config
from ariadne_mcp.ingestion.state import FileRecord, IndexState
from ariadne_mcp.parsers.markdown import parse_markdown
from ariadne_mcp.parsers.python import parse_python
from ariadne_mcp.parsers.text import parse_text


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
    md = tmp_path / "guide.md"; md.write_text("# One\nBody\n## Two\nMore\n", encoding="utf-8")
    txt = tmp_path / "notes.txt"; txt.write_text("plain\ntext\n", encoding="utf-8")
    md_chunks = parse_markdown(md, "kb", tmp_path)
    assert [c.metadata["heading"] for c in md_chunks] == ["One", "Two"]
    assert [c.order for c in md_chunks] == [0, 1]
    assert parse_text(txt, "kb", tmp_path)[0].metadata["path"] == "notes.txt"


def test_discovery_ignores_and_hashing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir(); (tmp_path / ".git" / "hidden.py").write_text("x", encoding="utf-8")
    (tmp_path / "keep.py").write_text("x", encoding="utf-8")
    (tmp_path / "skip.pyc").write_text("x", encoding="utf-8")
    cfg = AriadneConfig(knowledge=KnowledgeConfig(id="kb")).indexing
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
    src = tmp_path / "src"; src.mkdir(); (src / "a.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    cfg = AriadneConfig(knowledge=KnowledgeConfig(id="kb"), storage=StorageConfig(data_directory=tmp_path / "data"), sources=SourcesConfig(code=[SourcePathConfig(path=src)]))
    report = index_config(cfg)
    assert report.new == 1 and report.chunks >= 2
    assert list((tmp_path / "data" / "chunks").glob("*.jsonl"))
