"""Incremental source indexer producing canonical chunks."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.config import CarsenConfig, SourcePathConfig
from carsen_mcp.embeddings import EmbeddingProvider, embedding_provider_from_config
from carsen_mcp.parsers.base import parse_file, rel_path
from carsen_mcp.storage import QdrantVectorStore, qdrant_store_from_config

from .discovery import discover_files, sha256_file
from .git import citation_url, clone_or_update, git_metadata, origin_remote, public_remote_url
from .state import FileRecord, IndexState

DEFAULT_EMBEDDING_BATCH_SIZE = 8


class EmbeddingIndexError(RuntimeError):
    """Embedding provider failed while building a dense index."""


class VectorIndexError(RuntimeError):
    """Vector store failed while building a dense index."""


@dataclass(frozen=True)
class IndexReport:
    new: int
    unchanged: int
    changed: int
    deleted: int
    chunks: int
    dense_error: str | None = None


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


def _safe_remote_id(repo_url: str) -> str:
    return hashlib.sha256(repo_url.encode("utf-8")).hexdigest()[:16]


def resolve_source_path(config: CarsenConfig, source: SourcePathConfig) -> Path:
    """Return the local path to index, cloning remote sources into instance cache."""

    if source.repo_url:
        assert config.storage.data_directory is not None
        checkout = Path(config.storage.data_directory) / "remotes" / _safe_remote_id(source.repo_url)
        clone_or_update(source.repo_url, checkout, source.ref)
        return checkout / source.subpath if source.subpath is not None else checkout
    if source.path is None:
        raise ValueError("source requires path or repo_url")
    return source.path


def _enrich_chunks(chunks: list[Any], source: SourcePathConfig, file_path: Path) -> None:
    for chunk in chunks:
        metadata = chunk.metadata
        git = git_metadata(file_path)
        metadata.update(git)
        if "commit" in git:
            metadata.setdefault("git_commit", git["commit"])
        if source.repository_name:
            metadata["repository_name"] = source.repository_name
        remote = source.repo_url or origin_remote(file_path)
        if remote:
            public = public_remote_url(remote)
            if public is not None:
                metadata["repository_url"] = public.web_url
                metadata["remote_url"] = public.web_url
                commit = metadata.get("git_commit") or metadata.get("commit")
                git_path = metadata.get("git_path")
                if commit and git_path:
                    url = citation_url(public.web_url, public.provider, commit, git_path, chunk.start_line, chunk.end_line)
                    if url:
                        metadata["citation_url"] = url


def _chunk_batches[T](items: list[T], size: int) -> list[list[T]]:
    if size < 1:
        raise ValueError("embedding batch size must be positive")
    return [items[index : index + size] for index in range(0, len(items), size)]


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
    source_by_file: dict[str, SourcePathConfig] = {}
    for source in _sources(config):
        source_path = resolve_source_path(config, source)
        if not source_path.exists():
            continue
        discovered = (
            [source_path.resolve()]
            if source_path.is_file()
            else discover_files(source_path, config.indexing)
        )
        for file in discovered:
            files.append(file)
            roots[str(file)] = source_path.resolve() if source_path.is_dir() else source_path.parent.resolve()
            source_by_file[str(file)] = source
    files = sorted(set(files))
    allowed_sources = {str(path) for path in files}
    allowed_sources.update(rel_path(path, roots.get(str(path))) for path in files)
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
        _progress(progress, "file_parse_start", path=path_str, index=index, total=len(to_parse))
        try:
            chunks = parse_file(path, config.knowledge.id, roots.get(path_str), config.parsing.documents)
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
        _enrich_chunks(chunks, source_by_file.get(path_str) or SourcePathConfig(path=path), path)
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
    pruned = store.prune_unknown_sources(config.knowledge.id, allowed_sources)
    deleted_count = len(status["deleted"]) + pruned
    _progress(progress, "deleted", files=deleted_count)
    state.upsert([by_path[p] for p in parsed_paths if p in by_path])
    state.delete(status["deleted"])
    dense_error: str | None = None
    if embed:
        try:
            index_vectors_for_config(
                config,
                embedding_provider=embedding_provider,
                vector_store=vector_store,
                progress=progress,
            )
        except (EmbeddingIndexError, VectorIndexError) as exc:
            dense_error = _compact_error(exc)
            _progress(progress, "dense_failed", error=dense_error)
    return IndexReport(
        len(status["new"]),
        len(status["unchanged"]),
        len(status["changed"]),
        deleted_count,
        chunk_count,
        dense_error,
    )


def _compact_error(exc: Exception) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        text = str(current)
        if text and text not in messages:
            messages.append(text)
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return ": ".join(messages) or exc.__class__.__name__


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
    chunks.sort(key=lambda chunk: (chunk.source_path, chunk.order, chunk.chunk_id))
    _progress(progress, "embed_start", chunks=len(chunks), recreate=recreate)
    provider = embedding_provider or embedding_provider_from_config(config.models.embedding)
    batch_size = config.models.embedding.batch_size or DEFAULT_EMBEDDING_BATCH_SIZE
    store: QdrantVectorStore | None = vector_store
    upserted = 0
    if recreate:
        if store is None:
            dimensions = provider.dimensions
            if dimensions < 1:
                raise ValueError("embedding dimensions must be available before vector indexing")
            try:
                store = qdrant_store_from_config(config, dimensions)
            except Exception as exc:
                raise VectorIndexError("could not create Qdrant vector store") from exc
        try:
            store.recreate_collection()
        except Exception as exc:
            raise VectorIndexError("could not recreate Qdrant collection") from exc
    _progress(progress, "upsert_start", chunks=len(chunks), recreate=recreate)
    for batch_index, chunk_batch in enumerate(_chunk_batches(chunks, batch_size), start=1):
        texts = [chunk.text for chunk in chunk_batch]
        try:
            vectors = provider.embed_texts(texts)
        except Exception as exc:
            raise EmbeddingIndexError(
                "embedding batch failed; one chunk or document may be too large. "
                "Try reducing models.embedding.batch_size, lowering models.embedding.max_seq_length, "
                "using a smaller embedding model, or indexing without --embed."
            ) from exc
        if len(vectors) != len(chunk_batch):
            raise RuntimeError(
                f"embedding provider returned {len(vectors)} vector(s) for {len(chunk_batch)} chunk(s)"
            )
        if store is None:
            dimensions = provider.dimensions or (len(vectors[0]) if vectors else 0)
            if dimensions < 1:
                raise ValueError("embedding dimensions must be available before vector indexing")
            try:
                store = qdrant_store_from_config(config, dimensions)
            except Exception as exc:
                raise VectorIndexError("could not create Qdrant vector store") from exc
        try:
            store.upsert_chunks(chunk_batch, vectors)
        except Exception as exc:
            raise VectorIndexError("could not upsert vectors to Qdrant") from exc
        upserted += len(chunk_batch)
        _progress(progress, "embed_batch_complete", batches=batch_index, chunks=upserted, total=len(chunks))
    _progress(progress, "embed_complete", chunks=upserted)
    _progress(progress, "upsert_complete", chunks=upserted)
    return upserted


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
