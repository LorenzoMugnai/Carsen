from __future__ import annotations

import subprocess
from pathlib import Path

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.citations import CitationFormatter
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, SourcePathConfig, SourcesConfig, StorageConfig
from carsen_mcp.ingestion.git import citation_url, public_remote_url
from carsen_mcp.ingestion.indexer import index_config, resolve_source_path


def test_public_remote_url_and_line_anchors() -> None:
    github = public_remote_url("git@github.com:org/repo.git")
    gitlab = public_remote_url("https://gitlab.com/org/repo.git")

    assert github is not None
    assert github.web_url == "https://github.com/org/repo"
    assert citation_url(github.web_url, github.provider, "abc123", "src/app.py", 10, 20) == "https://github.com/org/repo/blob/abc123/src/app.py#L10-L20"
    assert gitlab is not None
    assert gitlab.web_url == "https://gitlab.com/org/repo"
    assert citation_url(gitlab.web_url, gitlab.provider, "abc123", "src/app.py", 10, 20) == "https://gitlab.com/org/repo/-/blob/abc123/src/app.py#L10-20"
    assert public_remote_url("ssh://git@example.com/private/repo.git") is None


def test_indexer_enriches_chunks_with_online_citation_url(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=repo)
    subprocess.check_call(["git", "remote", "add", "origin", "https://github.com/org/repo.git"], cwd=repo)
    source = repo / "app.py"
    source.write_text("def helper():\n    return 1\n", encoding="utf-8")
    subprocess.check_call(["git", "add", "app.py"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "add app"], cwd=repo, stdout=subprocess.DEVNULL)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(code=[SourcePathConfig(path=repo, repository_name="org/repo")]),
    )

    index_config(cfg)

    chunks = list(ChunkStore(tmp_path / "data").load_all_chunks())
    assert chunks
    metadata = next(chunk.metadata for chunk in chunks if chunk.metadata.get("git_path") == "app.py")
    assert metadata["repository_name"] == "org/repo"
    assert metadata["git_commit"] == commit
    assert metadata["git_path"] == "app.py"
    assert metadata["repository_url"] == "https://github.com/org/repo"
    assert metadata["citation_url"].startswith(f"https://github.com/org/repo/blob/{commit}/app.py#L")


def test_remote_source_resolution_uses_instance_cache(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_clone(repo_url: str, destination: Path, ref: str | None = None) -> Path:
        calls.append((repo_url, destination, ref))
        destination.mkdir(parents=True)
        (destination / "src").mkdir()
        return destination

    monkeypatch.setattr("carsen_mcp.ingestion.indexer.clone_or_update", fake_clone)
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="kb"), storage=StorageConfig(data_directory=tmp_path / "data"))
    source = SourcePathConfig(repo_url="https://github.com/org/repo.git", ref="v1", subpath=Path("src"))

    resolved = resolve_source_path(cfg, source)

    assert resolved == calls[0][1] / "src"
    assert calls[0][0] == "https://github.com/org/repo.git"
    assert calls[0][1].parent == tmp_path / "data" / "remotes"
    assert calls[0][2] == "v1"


def test_citation_formatter_displays_citation_url() -> None:
    chunk = Chunk(
        "kb",
        "app.py",
        "function",
        "helper",
        1,
        2,
        "def helper(): pass",
        metadata={"repository_name": "org/repo", "git_commit": "abc", "citation_url": "https://github.com/org/repo/blob/abc/app.py#L1-L2"},
    )

    assert CitationFormatter().format(chunk) == "org/repo@abc:app.py:1-2 (https://github.com/org/repo/blob/abc/app.py#L1-L2)"
