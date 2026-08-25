from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from carsen_mcp.config import DocumentParsingConfig
from carsen_mcp.parsers import document
from carsen_mcp.parsers.base import parse_file
from carsen_mcp.parsers.document import ParserUnavailableError, parse_document


class FakeDocument:
    def export_to_markdown(self) -> str:
        return "# Overview\nText\n## Details\nMore"

    def export_to_dict(self) -> dict[str, Any]:
        return {"pages": [{"page_no": 12}], "sections": [{"text": "Overview"}]}


class FakeResult:
    document = FakeDocument()


class FakeConverter:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def convert(self, path: Path) -> FakeResult:
        return FakeResult()


def test_docling_parser_uses_lazy_converter_and_provenance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(document, "_load_converter", lambda: FakeConverter)

    chunks = parse_document(pdf, "kb", tmp_path)

    assert [chunk.metadata["heading"] for chunk in chunks] == ["Overview", "Details"]
    assert chunks[0].metadata["page"] == 12
    assert chunks[0].metadata["source_path"] == "paper.pdf"
    assert chunks[0].metadata["source_type"] == "documents"
    assert [chunk.order for chunk in chunks] == [0, 1]


def test_unavailable_docling_for_binary_formats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docx = tmp_path / "file.docx"
    docx.write_bytes(b"binary")
    monkeypatch.setattr(document, "_load_converter", lambda: (_ for _ in ()).throw(ParserUnavailableError("missing")))

    with pytest.raises(ParserUnavailableError, match="Docling is required"):
        parse_document(docx, "kb", tmp_path)


def test_html_fallback_without_docling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text("<h1>Title</h1><p>Hello world</p>", encoding="utf-8")
    monkeypatch.setattr(document, "_load_converter", lambda: (_ for _ in ()).throw(ParserUnavailableError("missing")))

    chunks = parse_document(html, "kb", tmp_path)

    assert chunks[0].metadata["heading"] == "Title"
    assert chunks[0].metadata["document_type"] == "html"
    assert "Hello world" in chunks[0].text


def test_existing_markdown_and_txt_still_work(tmp_path: Path) -> None:
    md = tmp_path / "guide.md"
    txt = tmp_path / "notes.txt"
    md.write_text("# Guide\nBody", encoding="utf-8")
    txt.write_text("plain", encoding="utf-8")

    assert parse_file(md, "kb", tmp_path)[0].metadata["heading"] == "Guide"
    assert parse_file(txt, "kb", tmp_path)[0].kind == "text"


def test_parser_selection_routes_document_extensions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(document, "_load_converter", lambda: FakeConverter)
    for name in ["paper.pdf", "paper.docx", "paper.html"]:
        path = tmp_path / name
        path.write_text("placeholder", encoding="utf-8")
        chunks = parse_file(path, "kb", tmp_path)
        assert chunks[0].kind == "document"


def test_pdf_docling_converter_uses_fast_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class InputFormat:
        PDF = "pdf"

    class PdfPipelineOptions:
        do_ocr = True
        do_table_structure = True
        force_backend_text = False

    class PdfFormatOption:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class PyPdfiumDocumentBackend:
        pass

    class CapturingConverter(FakeConverter):
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    def fake_import_module(name: str) -> Any:
        modules = {
            "docling.datamodel.base_models": type("Module", (), {"InputFormat": InputFormat}),
            "docling.datamodel.pipeline_options": type("Module", (), {"PdfPipelineOptions": PdfPipelineOptions}),
            "docling.document_converter": type(
                "Module",
                (),
                {"DocumentConverter": CapturingConverter, "PdfFormatOption": PdfFormatOption},
            ),
            "docling.backend.pypdfium2_backend": type(
                "Module",
                (),
                {"PyPdfiumDocumentBackend": PyPdfiumDocumentBackend},
            ),
        }
        return modules[name]

    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(document.importlib, "import_module", fake_import_module)

    chunks = parse_file(pdf, "kb", tmp_path, DocumentParsingConfig())

    assert chunks[0].kind == "document"
    format_option = captured["format_options"]["pdf"]
    pipeline_options = format_option.kwargs["pipeline_options"]
    assert pipeline_options.do_ocr is False
    assert pipeline_options.do_table_structure is False
    assert pipeline_options.force_backend_text is True
    assert format_option.kwargs["backend"] is PyPdfiumDocumentBackend
