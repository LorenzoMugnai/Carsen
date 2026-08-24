"""Incremental source indexer producing canonical chunks."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ariadne_mcp.chunks.store import ChunkStore
from ariadne_mcp.config import AriadneConfig, SourcePathConfig
from ariadne_mcp.embeddings import EmbeddingProvider, embedding_provider_from_config
from ariadne_mcp.parsers.base import parse_file
from ariadne_mcp.storage import QdrantVectorStore, qdrant_store_from_config

from .discovery import discover_files, sha256_file
from .git import git_metadata
from .state import FileRecord, IndexState


@dataclass(frozen=True)
class IndexReport:
    new: int
    unchanged: int
    changed: int
    deleted: int
    chunks: int


def _records(files: list[Path]) -> list[FileRecord]:
    records = []
    for path in files:
        stat = path.stat()
        meta = git_metadata(path)
        records.append(FileRecord(str(path), stat.st_mtime, stat.st_size, sha256_file(path), meta.get("commit")))
    return records


def _sources(config: AriadneConfig) -> list[SourcePathConfig]:
    return [*config.sources.code, *config.sources.documents]


def index_config(config: AriadneConfig, force: bool = False, embed: bool = False, embedding_provider: EmbeddingProvider | None = None, vector_store: QdrantVectorStore | None = None) -> IndexReport:
    """Parse configured sources, persist chunks and update incremental state."""
    assert config.storage.data_directory is not None
    data_dir = Path(config.storage.data_directory)
    state = IndexState(data_dir)
    store = ChunkStore(data_dir)
    files: list[Path] = []
    roots: dict[str, Path] = {}
    for source in _sources(config):
        if not source.path.exists():
            continue
        discovered = [source.path.resolve()] if source.path.is_file() else discover_files(source.path, config.indexing)
        for file in discovered:
            files.append(file)
            roots[str(file)] = source.path.resolve() if source.path.is_dir() else source.path.parent.resolve()
    records = _records(sorted(set(files)))
    status = state.classify(records)
    to_parse = status["new"] + status["changed"] + (status["unchanged"] if force else [])
    chunk_count = 0
    by_path = {r.path: r for r in records}
    for path_str in to_parse:
        path = Path(path_str)
        chunks = parse_file(path, config.knowledge.id, roots.get(path_str))
        store.replace_file_chunks(path_str, chunks)
        chunk_count += len(chunks)
    for path_str in status["deleted"]:
        store.delete_file_chunks(path_str)
    state.upsert([by_path[p] for p in to_parse if p in by_path])
    state.delete(status["deleted"])
    if embed:
        index_vectors_for_config(config, embedding_provider=embedding_provider, vector_store=vector_store)
    return IndexReport(len(status["new"]), len(status["unchanged"]), len(status["changed"]), len(status["deleted"]), chunk_count)


def index_vectors_for_config(config: AriadneConfig, embedding_provider: EmbeddingProvider | None = None, vector_store: QdrantVectorStore | None = None, recreate: bool = False) -> int:
    """Embed canonical chunks and upsert them into the configured Qdrant collection."""

    assert config.storage.data_directory is not None
    chunks = [chunk for chunk in ChunkStore(Path(config.storage.data_directory)).load_all_chunks() if chunk.knowledge_id == config.knowledge.id]
    provider = embedding_provider or embedding_provider_from_config(config.models.embedding)
    texts = [chunk.text for chunk in chunks]
    vectors = provider.embed_texts(texts) if texts else []
    dimensions = provider.dimensions or (len(vectors[0]) if vectors else 0)
    if dimensions < 1:
        raise ValueError("embedding dimensions must be available before vector indexing")
    store = vector_store or qdrant_store_from_config(config, dimensions)
    if recreate:
        store.recreate_collection()
    store.upsert_chunks(chunks, vectors)
    return len(chunks)


def reembed_config(config: AriadneConfig, embedding_provider: EmbeddingProvider | None = None, vector_store: QdrantVectorStore | None = None) -> int:
    """Recreate the dense index from already persisted canonical chunks."""

    return index_vectors_for_config(config, embedding_provider=embedding_provider, vector_store=vector_store, recreate=True)


def delete_index_config(config: AriadneConfig, vector_store: QdrantVectorStore | None = None, clear_vectors: bool = True) -> tuple[bool, str | None]:
    """Remove this instance local index data and, where possible, its Qdrant collection."""

    assert config.storage.data_directory is not None
    vector_error: str | None = None
    if clear_vectors:
        try:
            provider = embedding_provider_from_config(config.models.embedding)
            store = vector_store or qdrant_store_from_config(config, provider.dimensions)
            store.delete_collection()
        except Exception as exc:
            vector_error = str(exc)
    data_dir = Path(config.storage.data_directory)
    existed = data_dir.exists()
    if existed:
        shutil.rmtree(data_dir)
    return existed, vector_error
