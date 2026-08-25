from __future__ import annotations

from pathlib import Path

from carsen_mcp.config import CarsenConfig, KnowledgeConfig, SourcePathConfig, SourcesConfig, StorageConfig
from carsen_mcp.ingestion import watcher


def test_source_roots_only_existing_and_deduped(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        sources=SourcesConfig(
            code=[SourcePathConfig(path=src)],
            documents=[SourcePathConfig(path=src), SourcePathConfig(path=tmp_path / "missing")],
        ),
    )

    assert watcher.source_roots(cfg) == [src.resolve()]


def test_watch_indexer_debounces_and_uses_single_flight(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src"
    src.mkdir()
    cfg = CarsenConfig(
        knowledge=KnowledgeConfig(id="kb"),
        storage=StorageConfig(data_directory=tmp_path / "data"),
        sources=SourcesConfig(code=[SourcePathConfig(path=src)]),
    )
    cfg.indexing.watch_embed = True
    calls: list[tuple[str, bool]] = []

    def fake_index_config(config: CarsenConfig, embed: bool = False) -> None:
        calls.append((config.knowledge.id, embed))

    monkeypatch.setattr(watcher, "sleep", lambda _seconds: None)
    monkeypatch.setattr(watcher, "index_config", fake_index_config)

    runner = watcher.WatchIndexer(cfg)

    assert runner.handle_changes({("modified", src / "a.py"), ("modified", src / "b.py")}, debounce_seconds=0) is True
    assert calls == [("kb", True)]

    assert runner._lock.acquire(blocking=False) is True
    try:
        assert runner.index_once() is False
    finally:
        runner._lock.release()
    assert calls == [("kb", True)]
