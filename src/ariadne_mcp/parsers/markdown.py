"""Markdown parser preserving headings and chunk order."""

from __future__ import annotations

from pathlib import Path
from ariadne_mcp.chunks.model import Chunk
from .base import read_text, rel_path


def parse_markdown(path: Path, knowledge_id: str, source_root: Path | None = None) -> list[Chunk]:
    text = read_text(path); lines = text.splitlines(); source = rel_path(path, source_root)
    starts = [i for i, line in enumerate(lines, 1) if line.startswith("#")]
    if not starts: starts = [1]
    chunks = []
    for order, start in enumerate(starts):
        end = (starts[order + 1] - 1) if order + 1 < len(starts) else max(1, len(lines))
        heading = lines[start - 1].lstrip("# ").strip() if lines else None
        chunks.append(Chunk(knowledge_id, source, "markdown", heading, start, end, "\n".join(lines[start-1:end]), order, {"heading": heading, "path": source}))
    return chunks
