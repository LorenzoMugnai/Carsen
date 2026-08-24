"""Markdown parser preserving headings and chunk order."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from ariadne_mcp.chunks.model import Chunk
from .base import read_text, rel_path


def parse_markdown(path: Path, knowledge_id: str, source_root: Path | None = None) -> list[Chunk]:
    text = read_text(path); source = rel_path(path, source_root)
    return parse_markdown_text(text, knowledge_id, source, base_metadata={"path": source})


def parse_markdown_text(text: str, knowledge_id: str, source_path: str, base_metadata: dict[str, Any] | None = None, kind: str = "markdown") -> list[Chunk]:
    """Chunk Markdown text by headings while preserving order and path metadata."""
    lines = text.splitlines(); metadata = dict(base_metadata or {})
    starts = [i for i, line in enumerate(lines, 1) if line.startswith("#")]
    if not starts: starts = [1]
    chunks = []
    for order, start in enumerate(starts):
        end = (starts[order + 1] - 1) if order + 1 < len(starts) else max(1, len(lines))
        heading = lines[start - 1].lstrip("# ").strip() if lines else None
        chunk_metadata = {**metadata, "heading": heading, "section": heading, "path": source_path, "order": order}
        chunks.append(Chunk(knowledge_id, source_path, kind, heading, start, end, "\n".join(lines[start-1:end]), order, chunk_metadata))
    return chunks
