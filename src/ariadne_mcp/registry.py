"""Local configuration registry discovery."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .chunks.store import ChunkStore
from .config import AriadneConfig, SourcePathConfig, default_config, dump_config, load_config


def registry_dir() -> Path:
    """Return the local registry directory, defaulting to ``~/.config/ariadne``."""

    override = os.environ.get("ARIADNE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "ariadne"


def config_path_for(name: str, base_dir: Path | None = None) -> Path:
    """Return the registry path for a simple configuration name."""

    return (base_dir or registry_dir()) / f"{name}.yaml"


def create_config(
    name: str,
    overwrite: bool = False,
    base_dir: Path | None = None,
    code: list[Path] | None = None,
    documents: list[Path] | None = None,
) -> Path:
    """Create a default configuration in the local registry."""

    cfg = default_config(name)
    cfg.sources.code = [SourcePathConfig(path=path.expanduser()) for path in code or []]
    cfg.sources.documents = [SourcePathConfig(path=path.expanduser()) for path in documents or []]
    target = config_path_for(cfg.name, base_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"configuration '{name}' already exists; use --overwrite to replace it")
    target.write_text(dump_config(cfg), encoding="utf-8")
    return target


def discover_configs(explicit: Path | None = None, base_dir: Path | None = None) -> list[Path]:
    """Discover registry configurations and include an explicit path if supplied."""

    paths: list[Path] = []
    directory = base_dir or registry_dir()
    if directory.exists():
        paths.extend(sorted(directory.glob("*.yml")))
        paths.extend(sorted(directory.glob("*.yaml")))
    if explicit is not None:
        explicit_path = explicit.expanduser()
        if explicit_path not in paths:
            paths.append(explicit_path)
    return paths


def list_configs(explicit: Path | None = None, base_dir: Path | None = None) -> list[AriadneConfig]:
    """Load all discoverable valid configurations."""

    return [load_config(path) for path in discover_configs(explicit, base_dir)]


def instance_metadata(config: AriadneConfig) -> dict[str, Any]:
    """Return best-effort local metadata for one registered instance."""

    chunk_count = 0
    source_count = 0
    data_directory = config.storage.data_directory
    if data_directory is not None:
        try:
            chunks = [chunk for chunk in ChunkStore(data_directory).load_all_chunks() if chunk.knowledge_id == config.knowledge.id]
            chunk_count = len(chunks)
            source_count = len({chunk.source_path for chunk in chunks})
        except Exception:
            chunk_count = 0
            source_count = 0
    return {
        "name": config.knowledge.id,
        "status": "runnable",
        "port": config.server.port,
        "transport": config.server.transport,
        "collection": config.storage.collection,
        "data_directory": str(data_directory),
        "chunks": chunk_count,
        "sources": source_count,
    }
