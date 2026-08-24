"""Source expansion helpers for neighbouring code and document chunks."""

from __future__ import annotations

from collections.abc import Sequence

from ariadne_mcp.chunks.model import Chunk

from .models import SearchResult


class SourceExpander:
    """Expand hits using only existing chunk metadata and identifiers."""

    def __init__(self, items: Sequence[SearchResult | Chunk]) -> None:
        self.items = list(items)

    def surrounding_code(self, target: SearchResult | Chunk, before: int = 1, after: int = 1) -> list[SearchResult | Chunk]:
        """Return neighbouring chunks from the same file around the target order."""

        source = _source_path(target)
        order = _order(target)
        if source is None or order is None:
            return [target]
        lower = order - before
        upper = order + after
        return sorted([item for item in self.items if _source_path(item) == source and (item_order := _order(item)) is not None and lower <= item_order <= upper], key=lambda item: _order(item) or 0)

    def parent_class(self, target: SearchResult | Chunk) -> SearchResult | Chunk | None:
        """Return a parent class chunk when metadata or dotted symbols identify one."""

        parent = _metadata(target).get("parent_symbol")
        symbol = _symbol(target)
        if parent is None and symbol and "." in symbol:
            parent = symbol.rsplit(".", 1)[0]
        if parent is None:
            return None
        for item in self.items:
            if _source_path(item) == _source_path(target) and _symbol(item) == parent:
                return item
        return None

    def document_neighbours(self, target: SearchResult | Chunk, before: int = 1, after: int = 1) -> list[SearchResult | Chunk]:
        """Return previous and next document chunks from the same source."""

        return self.surrounding_code(target, before=before, after=after)

    def document_section(self, target: SearchResult | Chunk) -> list[SearchResult | Chunk]:
        """Return chunks in the same document section, preserving order."""

        metadata = _metadata(target)
        section = metadata.get("section") or metadata.get("heading")
        source = _source_path(target)
        if source is None or section is None:
            return [target]
        return sorted([item for item in self.items if _source_path(item) == source and (_metadata(item).get("section") or _metadata(item).get("heading")) == section], key=lambda item: _order(item) or 0)


def _metadata(item: SearchResult | Chunk) -> dict[str, object]:
    return dict(item.metadata)


def _source_path(item: SearchResult | Chunk) -> str | None:
    return getattr(item, "source_path", None) or item.metadata.get("source_path") or item.metadata.get("path")


def _order(item: SearchResult | Chunk) -> int | None:
    value = getattr(item, "order", None) if isinstance(item, Chunk) else item.metadata.get("order")
    return int(value) if value is not None else None


def _symbol(item: SearchResult | Chunk) -> str | None:
    return getattr(item, "symbol", None) or item.metadata.get("symbol")
