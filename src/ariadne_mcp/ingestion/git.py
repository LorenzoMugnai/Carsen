"""Best-effort Git metadata collection."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_metadata(path: Path) -> dict[str, str]:
    try:
        commit = subprocess.check_output(["git", "-C", str(path.parent), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        rel = subprocess.check_output(["git", "-C", str(path.parent), "ls-files", "--full-name", str(path)], text=True, stderr=subprocess.DEVNULL).strip()
        return {"commit": commit, "git_path": rel or str(path)}
    except Exception:
        return {}
