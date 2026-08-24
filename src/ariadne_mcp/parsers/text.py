"""Plain text and fallback source parser."""

from __future__ import annotations

from pathlib import Path

from ariadne_mcp.chunks.model import Chunk

from .base import read_text, rel_path


def parse_text(path: Path, knowledge_id: str, source_root: Path | None = None) -> list[Chunk]:
    text = read_text(path)
    source = rel_path(path, source_root)
    lines = text.splitlines()
    return [Chunk(knowledge_id, source, "text", None, 1, max(1, len(lines)), text, 0, {"path": source})]
