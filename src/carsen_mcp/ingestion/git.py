"""Best-effort Git metadata collection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def git_metadata(path: Path) -> dict[str, str]:
    try:
        commit = subprocess.check_output(["git", "-C", str(path.parent), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        rel = subprocess.check_output(["git", "-C", str(path.parent), "ls-files", "--full-name", str(path)], text=True, stderr=subprocess.DEVNULL).strip()
        return {"commit": commit, "git_path": rel or str(path)}
    except Exception:
        return {}


@dataclass(frozen=True)
class PublicRemote:
    web_url: str
    provider: str


def public_remote_url(remote_url: str) -> PublicRemote | None:
    """Normalize common public GitHub/GitLab remote URLs to web URLs."""

    value = remote_url.strip()
    if value.startswith("git@"):
        host, _, repo = value[4:].partition(":")
        path = repo.removesuffix(".git")
    else:
        parsed = urlparse(value)
        host = parsed.netloc
        path = parsed.path.lstrip("/").removesuffix(".git")
    host = host.lower()
    if host == "github.com" and path.count("/") >= 1:
        return PublicRemote(f"https://github.com/{path}", "github")
    if host == "gitlab.com" and path.count("/") >= 1:
        return PublicRemote(f"https://gitlab.com/{path}", "gitlab")
    return None


def origin_remote(path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(path.parent), "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def citation_url(web_url: str, provider: str, commit: str, git_path: str, start_line: int | None, end_line: int | None) -> str | None:
    if not start_line or not end_line:
        return None
    if provider == "github":
        return f"{web_url}/blob/{commit}/{git_path}#L{start_line}-L{end_line}"
    if provider == "gitlab":
        return f"{web_url}/-/blob/{commit}/{git_path}#L{start_line}-{end_line}"
    return None


def checked_out_commit(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()


def clone_or_update(repo_url: str, destination: Path, ref: str | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        subprocess.check_call(["git", "-C", str(destination), "fetch", "--all", "--tags"], stderr=subprocess.DEVNULL)
    else:
        subprocess.check_call(["git", "clone", repo_url, str(destination)], stderr=subprocess.DEVNULL)
    if ref:
        subprocess.check_call(["git", "-C", str(destination), "checkout", ref], stderr=subprocess.DEVNULL)
    return destination
