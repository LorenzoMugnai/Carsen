"""Instance-local chunk persistence."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Chunk


class ChunkStore:
    """Store canonical chunks below ``storage.data_directory/chunks``."""

    def __init__(self, data_directory: Path) -> None:
        self.directory = Path(data_directory) / "chunks"
        self.directory.mkdir(parents=True, exist_ok=True)

    def replace_file_chunks(self, source_path: str, chunks: list[Chunk]) -> Path:
        digest = __import__("hashlib").sha256(source_path.encode("utf-8")).hexdigest()
        target = self.directory / f"{digest}.jsonl"
        with target.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk.to_dict(), sort_keys=True) + "\n")
        return target

    def delete_file_chunks(self, source_path: str) -> None:
        digest = __import__("hashlib").sha256(source_path.encode("utf-8")).hexdigest()
        (self.directory / f"{digest}.jsonl").unlink(missing_ok=True)

    def delete_chunk_file(self, path: Path) -> None:
        """Remove one persisted chunk file by store path."""

        path.unlink(missing_ok=True)

    def prune_unknown_sources(self, knowledge_id: str, allowed_sources: set[str]) -> int:
        """Remove chunk files for this instance whose source is no longer discoverable."""

        removed = 0
        for path in sorted(self.directory.glob("*.jsonl")):
            first_chunk = self._first_chunk(path)
            if first_chunk is None or first_chunk.knowledge_id != knowledge_id:
                continue
            candidates = {first_chunk.source_path}
            for key in ("path", "source_path", "git_path"):
                value = first_chunk.metadata.get(key)
                if value is not None:
                    candidates.add(str(value))
            if candidates.isdisjoint(allowed_sources):
                self.delete_chunk_file(path)
                removed += 1
        return removed

    def load_all_chunks(self) -> list[Chunk]:
        """Load all persisted chunks for sparse retrieval or maintenance."""

        chunks: list[Chunk] = []
        for path in sorted(self.directory.glob("*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        chunks.append(Chunk.from_dict(json.loads(line)))
        return chunks

    def _first_chunk(self, path: Path) -> Chunk | None:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return Chunk.from_dict(json.loads(line))
        return None
