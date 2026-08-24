"""Canonical chunk records for indexed Ariadne content."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """A deterministic unit of source content, namespaced by knowledge ID.

    ``chunk_id`` is stable while the source boundary is stable.  ``content_hash``
    captures the current text, so embeddings can be refreshed or invalidated
    without changing the canonical source identifier.
    """

    knowledge_id: str
    source_path: str
    kind: str
    symbol: str | None
    start_line: int
    end_line: int
    text: str
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    content_hash: str = ""
    indexed_at: str = ""

    def __post_init__(self) -> None:
        if not self.chunk_id:
            seed = f"{self.knowledge_id}\0{self.source_path}\0{self.kind}\0{self.symbol or ''}\0{self.start_line}\0{self.end_line}\0{self.order}"
            object.__setattr__(self, "chunk_id", f"{self.knowledge_id}_chk_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]}")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", hashlib.sha256(self.text.encode("utf-8")).hexdigest())
        if not self.indexed_at:
            object.__setattr__(self, "indexed_at", datetime.now(UTC).isoformat())

    @property
    def id(self) -> str:
        """Backward-compatible alias for the stable chunk identifier."""

        return self.chunk_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        return cls(**data)
