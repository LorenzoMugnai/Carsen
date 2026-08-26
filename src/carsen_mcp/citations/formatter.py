"""Metadata-backed citation formatting without inventing source details."""

from __future__ import annotations

from typing import Any

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.retrieval.models import SearchResult


class CitationFormatter:
    """Format citations from available metadata, falling back gracefully."""

    def format(self, item: SearchResult | Chunk) -> str:
        metadata = _metadata(item)
        path = _source_path(item, metadata)
        online = metadata.get("citation_url")
        if _is_document(metadata, path):
            local = self.document_citation(path, metadata)
        else:
            local = self.code_citation(item, path, metadata)
        return f"{local} ({online})" if online else local

    def code_citation(self, item: SearchResult | Chunk, path: str | None, metadata: dict[str, Any]) -> str:
        repo = metadata.get("repository") or metadata.get("repository_name")
        commit = metadata.get("commit") or metadata.get("git_commit")
        start = metadata.get("start_line") or getattr(item, "start_line", None)
        end = metadata.get("end_line") or getattr(item, "end_line", None)
        location = path or metadata.get("source_id") or _chunk_id(item)
        line_suffix = f":{start}-{end}" if start is not None and end is not None else ""
        if repo and commit and path:
            return f"{repo}@{commit}:{path}{line_suffix}"
        if path:
            return f"{path}{line_suffix}"
        return str(location)

    def document_citation(self, path: str | None, metadata: dict[str, Any]) -> str:
        location = path or metadata.get("source_id")
        if not location:
            return "unknown source"
        page = metadata.get("page") or metadata.get("page_number")
        section = metadata.get("section") or metadata.get("heading")
        suffix = f":p.{page}" if page is not None else ""
        if section:
            suffix = f"{suffix} §{section}" if suffix else f":§{section}"
        return f"{location}{suffix}"


def _metadata(item: SearchResult | Chunk) -> dict[str, Any]:
    return dict(item.metadata)


def _source_path(item: SearchResult | Chunk, metadata: dict[str, Any]) -> str | None:
    return getattr(item, "source_path", None) or metadata.get("source_path") or metadata.get("path")


def _chunk_id(item: SearchResult | Chunk) -> str:
    return getattr(item, "chunk_id", "unknown source")


def _is_document(metadata: dict[str, Any], path: str | None) -> bool:
    source_type = metadata.get("source_type")
    document_type = metadata.get("document_type")
    if source_type == "documents" or document_type in {"pdf", "markdown", "document"}:
        return True
    return bool(path and path.lower().endswith((".pdf", ".md", ".markdown", ".txt")) and metadata.get("page") is not None)
