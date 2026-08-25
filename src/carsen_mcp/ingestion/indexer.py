"""Incremental source indexer producing canonical chunks."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.config import CarsenConfig, SourcePathConfig
from carsen_mcp.embeddings import EmbeddingProvider, embedding_provider_from_config
from carsen_mcp.parsers.base import parse_file
from carsen_mcp.storage import QdrantVectorStore, qdrant_store_from_config

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


class ProgressReporter(Protocol):
    def __call__(self, event: str, payload: dict[str, Any]) -> None: ...


def _progress(progress: ProgressReporter | None, event: str, **payload: Any) -> None:
    if progress is not None:
        progress(event, payload)


def _records(files: list[Path], progress: ProgressReporter | None = None) -> list[FileRecord]:
    records = []
    _progress(progress, "fingerprint_start", total=len(files))
    for index, path in enumerate(files, start=1):
        stat = path.stat()
        meta = git_metadata(path)
        records.append(FileRecord(str(path), stat.st_mtime, stat.st_size, sha256_file(path), meta.get("commit")))
        _progress(progress, "file_fingerprinted", path=str(path), index=index, total=len(files))
    _progress(progress, "fingerprint_complete", total=len(files))
    return records


def _sources(config: CarsenConfig) -> list[SourcePathConfig]:
    return [*config.sources.code, *config.sources.documents]


def index_config(
    config: CarsenConfig,
    force: bool = False,
    embed: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: QdrantVectorStore | None = None,
    progress: ProgressReporter | None = None,
) -> IndexReport:
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
        discovered = (
            [source.path.resolve()]
            if source.path.is_file()
            else discover_files(source.path, config.indexing)
        )
        for file in discovered:
            files.append(file)
            roots[str(file)] = source.path.resolve() if source.path.is_dir() else source.path.parent.resolve()
    files = sorted(set(files))
    _progress(progress, "discovered", files=len(files))
    records = _records(files, progress)
    status = state.classify(records)
    to_parse = status["new"] + status["changed"] + (status["unchanged"] if force else [])
    _progress(
        progress,
        "classified",
        new=len(status["new"]),
        unchanged=len(status["unchanged"]),
        changed=len(status["changed"]),
        deleted=len(status["deleted"]),
        to_parse=len(to_parse),
    )
    chunk_count = 0
    by_path = {r.path: r for r in records}
    parsed_paths: list[str] = []
    _progress(progress, "parse_start", total=len(to_parse))
    for index, path_str in enumerate(to_parse, start=1):
        path = Path(path_str)
        try:
            chunks = parse_file(path, config.knowledge.id, roots.get(path_str))
        except Exception as exc:
            _progress(
                progress,
                "file_failed",
                path=path_str,
                index=index,
                total=len(to_parse),
                error=str(exc),
            )
            continue
        store.replace_file_chunks(path_str, chunks)
        parsed_paths.append(path_str)
        chunk_count += len(chunks)
        _progress(
            progress,
            "file_parsed",
            path=path_str,
            index=index,
            total=len(to_parse),
            chunks=len(chunks),
            chunk_total=chunk_count,
        )
    _progress(progress, "parse_complete", total=len(to_parse), chunks=chunk_count)
    for path_str in status["deleted"]:
        store.delete_file_chunks(path_str)
    _progress(progress, "deleted", files=len(status["deleted"]))
    state.upsert([by_path[p] for p in parsed_paths if p in by_path])
    state.delete(status["deleted"])
    if embed:
        index_vectors_for_config(
            config,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            progress=progress,
        )
    return IndexReport(
        len(status["new"]),
        len(status["unchanged"]),
        len(status["changed"]),
        len(status["deleted"]),
        chunk_count,
    )


def index_vectors_for_config(
    config: CarsenConfig,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: QdrantVectorStore | None = None,
    recreate: bool = False,
    progress: ProgressReporter | None = None,
) -> int:
    """Embed canonical chunks and upsert them into the configured Qdrant collection."""

    assert config.storage.data_directory is not None
    chunks = [
        chunk
        for chunk in ChunkStore(Path(config.storage.data_directory)).load_all_chunks()
        if chunk.knowledge_id == config.knowledge.id
    ]
    _progress(progress, "embed_start", chunks=len(chunks), recreate=recreate)
    provider = embedding_provider or embedding_provider_from_config(config.models.embedding)
    texts = [chunk.text for chunk in chunks]
    vectors = provider.embed_texts(texts) if texts else []
    _progress(progress, "embed_complete", chunks=len(chunks))
    dimensions = provider.dimensions or (len(vectors[0]) if vectors else 0)
    if dimensions < 1:
        raise ValueError("embedding dimensions must be available before vector indexing")
    store = vector_store or qdrant_store_from_config(config, dimensions)
    if recreate:
        store.recreate_collection()
    _progress(progress, "upsert_start", chunks=len(chunks), recreate=recreate)
    store.upsert_chunks(chunks, vectors)
    _progress(progress, "upsert_complete", chunks=len(chunks))
    return len(chunks)


def reembed_config(config: CarsenConfig, embedding_provider: EmbeddingProvider | None = None, vector_store: QdrantVectorStore | None = None) -> int:
    """Recreate the dense index from already persisted canonical chunks."""

    return index_vectors_for_config(config, embedding_provider=embedding_provider, vector_store=vector_store, recreate=True)


def delete_index_config(config: CarsenConfig, vector_store: QdrantVectorStore | None = None, clear_vectors: bool = True) -> tuple[bool, str | None]:
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
