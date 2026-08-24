"""Incremental SQLite indexing state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    path: str
    mtime: float
    size: int
    sha256: str
    commit: str | None = None


class IndexState:
    def __init__(self, data_directory: Path) -> None:
        Path(data_directory).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(data_directory) / "index_state.sqlite3")
        self.db.execute("create table if not exists files (path text primary key, mtime real, size integer, sha256 text, git_commit text)")

    def classify(self, records: list[FileRecord]) -> dict[str, list[str]]:
        current = {r.path: r for r in records}
        previous = {row[0]: row for row in self.db.execute("select path, mtime, size, sha256, git_commit from files")}
        new = [p for p in current if p not in previous]
        unchanged = [p for p, r in current.items() if p in previous and previous[p][1:4] == (r.mtime, r.size, r.sha256)]
        changed = [p for p, r in current.items() if p in previous and p not in unchanged]
        deleted = [p for p in previous if p not in current]
        return {"new": sorted(new), "unchanged": sorted(unchanged), "changed": sorted(changed), "deleted": sorted(deleted)}

    def upsert(self, records: list[FileRecord]) -> None:
        self.db.executemany("insert or replace into files values (?, ?, ?, ?, ?)", [(r.path, r.mtime, r.size, r.sha256, r.commit) for r in records])
        self.db.commit()

    def delete(self, paths: list[str]) -> None:
        self.db.executemany("delete from files where path = ?", [(p,) for p in paths])
        self.db.commit()
