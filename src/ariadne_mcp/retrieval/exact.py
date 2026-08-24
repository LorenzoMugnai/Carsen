"""Exact lookup helpers for symbols and source metadata."""

from __future__ import annotations

from .filters import filter_results
from .models import SearchResult


def lookup_symbol(results: list[SearchResult], symbol: str, filters: dict[str, object] | None = None) -> list[SearchResult]:
    return [result for result in filter_results(results, filters) if result.metadata.get("symbol") == symbol]


def lookup_path(results: list[SearchResult], path: str, filters: dict[str, object] | None = None) -> list[SearchResult]:
    return [result for result in filter_results(results, filters) if result.metadata.get("source_path") == path]


def lookup_repository(results: list[SearchResult], repository: str, filters: dict[str, object] | None = None) -> list[SearchResult]:
    return [result for result in filter_results(results, filters) if result.metadata.get("repository") == repository or result.metadata.get("repository_name") == repository]
