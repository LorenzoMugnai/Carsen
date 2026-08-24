"""Retrieval result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    """A ranked retrieval hit returned to higher-level search code."""

    chunk_id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
