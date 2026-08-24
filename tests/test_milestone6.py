from __future__ import annotations

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.citations import CitationFormatter
from carsen_mcp.retrieval import SearchResult, SourceExpander


def result(chunk_id: str, text: str, **metadata: object) -> SearchResult:
    return SearchResult(chunk_id=chunk_id, score=1.0, text=text, metadata=metadata)


def test_code_citation_exact_formatting() -> None:
    citation = CitationFormatter().format(
        result(
            "known-id",
            "def process(): pass",
            repository="Repo",
            commit="abc123",
            source_path="src/detector.py",
            start_line=10,
            end_line=14,
        )
    )
    assert citation == "Repo@abc123:src/detector.py:10-14"


def test_document_citation_exact_formatting() -> None:
    citation = CitationFormatter().format(
        result("doc-id", "content", source_path="file.pdf", page=12, section="Section", document_type="pdf")
    )
    assert citation == "file.pdf:p.12 §Section"


def test_missing_metadata_fallback_does_not_fabricate_source_ids() -> None:
    item = result("real-chunk-id", "orphaned text")
    assert CitationFormatter().format(item) == "real-chunk-id"


def test_code_expansion_around_neighbouring_chunks_and_parent_class() -> None:
    chunks = [
        Chunk("kb", "src/detector.py", "class", "Detector", 1, 8, "class Detector:", order=0),
        Chunk("kb", "src/detector.py", "method", "Detector.calibrate", 9, 12, "def calibrate", order=1),
        Chunk("kb", "src/detector.py", "method", "Detector.process", 13, 16, "def process", order=2),
        Chunk("kb", "src/other.py", "function", "helper", 1, 2, "def helper", order=1),
    ]
    expander = SourceExpander(chunks)
    expanded = expander.surrounding_code(chunks[1], before=1, after=1)
    assert [item.chunk_id for item in expanded] == [chunks[0].chunk_id, chunks[1].chunk_id, chunks[2].chunk_id]
    assert expander.parent_class(chunks[1]) == chunks[0]


def test_document_section_expansion_and_neighbours() -> None:
    items = [
        result("a", "intro", source_path="guide.pdf", order=0, section="Intro", page=1, document_type="pdf"),
        result("b", "setup one", source_path="guide.pdf", order=1, section="Setup", page=2, document_type="pdf"),
        result("c", "setup two", source_path="guide.pdf", order=2, section="Setup", page=3, document_type="pdf"),
        result("d", "other", source_path="other.pdf", order=2, section="Setup", page=3, document_type="pdf"),
    ]
    expander = SourceExpander(items)
    assert [item.chunk_id for item in expander.document_neighbours(items[1], before=1, after=1)] == ["a", "b", "c"]
    assert [item.chunk_id for item in expander.document_section(items[1])] == ["b", "c"]
