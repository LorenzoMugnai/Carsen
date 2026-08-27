"""Optional document parsing via Docling with lightweight fallbacks."""

from __future__ import annotations

import importlib
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from carsen_mcp.chunks.model import Chunk

from .base import rel_path
from .markdown import parse_markdown_text


class ParserUnavailableError(RuntimeError):
    """Raised when an optional parser dependency is unavailable."""


DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".xml"}
BINARY_EXTENSIONS = {".pdf", ".docx"}


def parse_document(
    path: Path,
    knowledge_id: str,
    source_root: Path | None = None,
    options: Any | None = None,
) -> list[Chunk]:
    """Parse PDF, DOCX or HTML documents, using Docling when available."""
    suffix = path.suffix.lower()
    source = rel_path(path, source_root)
    if suffix == ".xml":
        return _parse_xml_fallback(path, knowledge_id, source)
    if suffix == ".pdf":
        fast_chunks = _parse_pdf_text(path, knowledge_id, source)
        if fast_chunks is not None:
            return fast_chunks
    try:
        return _parse_with_docling(path, knowledge_id, source, options)
    except ParserUnavailableError as exc:
        if suffix in {".html", ".htm"}:
            return _parse_html_fallback(path, knowledge_id, source)
        if suffix in BINARY_EXTENSIONS:
            raise ParserUnavailableError(
                f"Docling is required to parse {suffix} documents; install the optional document parsing dependency"
            ) from exc
        raise


def _parse_pdf_text(path: Path, knowledge_id: str, source: str) -> list[Chunk] | None:
    """Extract selectable PDF text without starting Docling's layout pipeline."""
    try:
        pypdf = importlib.import_module("pypdf")
        reader = pypdf.PdfReader(str(path))
    except Exception:
        return None

    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            return None
        if not text.strip():
            return None
        pages.append((page_number, text))

    chunks: list[Chunk] = []
    for page_number, text in pages:
        chunks.extend(
            parse_markdown_text(
                text,
                knowledge_id,
                source,
                {
                    "path": source,
                    "source_path": source,
                    "source_type": "documents",
                    "document_type": "pdf",
                    "page": page_number,
                },
                kind="document",
            )
        )
    return chunks or None


def _load_converter():
    try:
        module = importlib.import_module("docling.document_converter")
    except ImportError as exc:
        raise ParserUnavailableError("Docling is not installed; document parsing is unavailable for binary formats") from exc
    return module.DocumentConverter


def _pdf_format_options(options: Any | None) -> dict[Any, Any]:
    if options is None:
        return {}
    try:
        input_format_module = importlib.import_module("docling.datamodel.base_models")
        pipeline_module = importlib.import_module("docling.datamodel.pipeline_options")
        converter_module = importlib.import_module("docling.document_converter")
        backend_module = importlib.import_module("docling.backend.pypdfium2_backend")
    except ImportError as exc:
        raise ParserUnavailableError("Docling is not installed; PDF parsing options are unavailable") from exc

    pipeline_options = pipeline_module.PdfPipelineOptions()
    pipeline_options.do_ocr = bool(getattr(options, "ocr", False))
    pipeline_options.do_table_structure = bool(getattr(options, "table_structure", False))
    pipeline_options.force_backend_text = bool(getattr(options, "force_backend_text", True))
    return {
        input_format_module.InputFormat.PDF: converter_module.PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=backend_module.PyPdfiumDocumentBackend,
        )
    }


@lru_cache(maxsize=8)
def _cached_converter(converter_class: Any, pdf_options: tuple[bool, bool, bool] | None) -> Any:
    """Reuse Docling's model-loaded converter across documents in one process."""
    if pdf_options is None:
        return converter_class()
    options = type(
        "DocumentOptions",
        (),
        {
            "ocr": pdf_options[0],
            "table_structure": pdf_options[1],
            "force_backend_text": pdf_options[2],
        },
    )()
    return converter_class(format_options=_pdf_format_options(options))


def _parse_with_docling(path: Path, knowledge_id: str, source: str, options: Any | None = None) -> list[Chunk]:
    converter_class = _load_converter()
    pdf_options = None
    if path.suffix.lower() == ".pdf" and options is not None:
        pdf_options = (
            bool(getattr(options, "ocr", False)),
            bool(getattr(options, "table_structure", False)),
            bool(getattr(options, "force_backend_text", True)),
        )
    converter = _cached_converter(converter_class, pdf_options)
    converted = converter.convert(path)
    document = getattr(converted, "document", converted)
    markdown = document.export_to_markdown() if hasattr(document, "export_to_markdown") else ""
    data = document.export_to_dict() if hasattr(document, "export_to_dict") else {}
    metadata = _docling_metadata(data, source)
    return parse_markdown_text(markdown, knowledge_id, source, metadata, kind="document")


def _docling_metadata(data: Any, source: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"path": source, "source_path": source, "source_type": "documents"}
    if isinstance(data, dict):
        pages = data.get("pages") or data.get("page")
        if isinstance(pages, list) and pages:
            number = pages[0].get("page_no") or pages[0].get("page_number") or pages[0].get("number") if isinstance(pages[0], dict) else None
            if number is not None:
                metadata["page"] = number
        headings = data.get("headings") or data.get("sections")
        if isinstance(headings, list) and headings:
            first = headings[0]
            metadata["section"] = first.get("text") if isinstance(first, dict) else str(first)
    return metadata


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3"}:
            self._heading = "#" * int(tag[1])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "section", "h1", "h2", "h3"}:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3"}:
            self._heading = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            prefix = f"{self._heading} " if self._heading else ""
            self.parts.append(prefix + text)


def _parse_html_fallback(path: Path, knowledge_id: str, source: str) -> list[Chunk]:
    parser = _HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    markdown = " ".join(parser.parts).replace(" \n ", "\n")
    return parse_markdown_text(markdown, knowledge_id, source, {"path": source, "source_path": source, "source_type": "documents", "document_type": "html"}, kind="document")


def _parse_xml_fallback(path: Path, knowledge_id: str, source: str) -> list[Chunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_markdown_text(text, knowledge_id, source, {"path": source, "source_path": source, "source_type": "documents", "document_type": "xml"}, kind="document")
