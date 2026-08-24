"""File discovery and content hashing."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ariadne_mcp.config import IndexingConfig


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_files(root: Path, indexing: IndexingConfig) -> list[Path]:
    """Return files under root, respecting ignored names and symlink policy."""
    root = Path(root)
    ignored_dirs = set(indexing.ignored_directories)
    ignored_exts = set(indexing.ignored_extensions)
    results: list[Path] = []
    for current, dirs, files in os.walk(root, followlinks=indexing.follow_symlinks):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and (indexing.follow_symlinks or not (Path(current) / d).is_symlink())]
        for name in files:
            path = Path(current) / name
            if path.suffix in ignored_exts:
                continue
            if path.is_symlink() and not indexing.follow_symlinks:
                continue
            results.append(path.resolve())
    return sorted(results)
