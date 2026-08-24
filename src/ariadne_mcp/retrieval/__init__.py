"""Retrieval abstractions."""

from .dense import DenseRetriever, VectorStore
from .models import SearchResult

__all__ = ["DenseRetriever", "SearchResult", "VectorStore"]
