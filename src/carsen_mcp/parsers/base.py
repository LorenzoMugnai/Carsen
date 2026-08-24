"""Parser protocol and parser selection."""

from __future__ import annotations

from pathlib import Path

from carsen_mcp.chunks.model import Chunk


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_file(path: Path, knowledge_id: str, source_root: Path | None = None) -> list[Chunk]:
    from .document import DOCUMENT_EXTENSIONS, parse_document
    from .markdown import parse_markdown
    from .python import parse_python
    from .text import parse_text

    if path.suffix == ".py":
        return parse_python(path, knowledge_id, source_root)
    if path.suffix.lower() in {".md", ".markdown"}:
        return parse_markdown(path, knowledge_id, source_root)
    if path.suffix.lower() in DOCUMENT_EXTENSIONS:
        return parse_document(path, knowledge_id, source_root)
    return parse_text(path, knowledge_id, source_root)


def rel_path(path: Path, source_root: Path | None) -> str:
    try:
        return str(path.relative_to(source_root)) if source_root else str(path)
    except ValueError:
        return str(path)
