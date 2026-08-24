"""Incremental source indexer producing canonical chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ariadne_mcp.chunks.store import ChunkStore
from ariadne_mcp.config import AriadneConfig, SourcePathConfig
from ariadne_mcp.parsers.base import parse_file
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
        stat = path.stat(); meta = git_metadata(path)
        records.append(FileRecord(str(path), stat.st_mtime, stat.st_size, sha256_file(path), meta.get("commit")))
    return records


def _sources(config: AriadneConfig) -> list[SourcePathConfig]:
    return [*config.sources.code, *config.sources.documents]


def index_config(config: AriadneConfig, force: bool = False) -> IndexReport:
    """Parse configured sources, persist chunks and update incremental state."""
    assert config.storage.data_directory is not None
    data_dir = Path(config.storage.data_directory)
    state = IndexState(data_dir); store = ChunkStore(data_dir)
    files: list[Path] = []
    roots: dict[str, Path] = {}
    for source in _sources(config):
        if not source.path.exists():
            continue
        discovered = [source.path.resolve()] if source.path.is_file() else discover_files(source.path, config.indexing)
        for file in discovered:
            files.append(file); roots[str(file)] = source.path.resolve() if source.path.is_dir() else source.path.parent.resolve()
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
    return IndexReport(len(status["new"]), len(status["unchanged"]), len(status["changed"]), len(status["deleted"]), chunk_count)
