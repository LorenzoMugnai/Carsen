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
