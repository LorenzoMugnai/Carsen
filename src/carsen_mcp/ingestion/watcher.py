"""Filesystem watch indexing for Carsen sources."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from time import sleep

from carsen_mcp.config import CarsenConfig

from .indexer import index_config

LogFn = Callable[[str], None]


def source_roots(config: CarsenConfig) -> list[Path]:
    """Return existing configured source roots to watch."""

    roots = [source.path for source in [*config.sources.code, *config.sources.documents] if source.path.exists()]
    return sorted({path.resolve() for path in roots})


class WatchIndexer:
    """Debounced single-flight index runner for filesystem watcher events."""

    def __init__(self, config: CarsenConfig, log: LogFn | None = None) -> None:
        self.config = config
        self.log = log or (lambda _message: None)
        self._lock = threading.Lock()
        self.runs = 0

    def index_once(self) -> bool:
        """Run indexing if no run is already active; return whether it ran."""

        if not self._lock.acquire(blocking=False):
            self.log("Index already running; coalescing filesystem changes.")
            return False
        try:
            self.log(f"Indexing '{self.config.knowledge.id}' after filesystem changes...")
            index_config(self.config, embed=self.config.indexing.watch_embed)
            self.runs += 1
            self.log(f"Indexing complete for '{self.config.knowledge.id}'.")
            return True
        finally:
            self._lock.release()

    def handle_changes(self, changes: Iterable[object], debounce_seconds: float | None = None) -> bool:
        """Coalesce a batch of watcher changes, debounce, and run one index pass."""

        change_count = sum(1 for _change in changes)
        if change_count == 0:
            return False
        seconds = self.config.indexing.watch_debounce_seconds if debounce_seconds is None else debounce_seconds
        self.log(f"Detected {change_count} filesystem change(s); indexing in {seconds:.1f}s...")
        if seconds > 0:
            sleep(seconds)
        return self.index_once()


def watch_config(config: CarsenConfig, stop_event: threading.Event | None = None, log: LogFn | None = None) -> None:
    """Watch configured source roots and index after debounced changes until stopped."""

    from watchfiles import watch

    logger = log or (lambda _message: None)
    roots = source_roots(config)
    if not roots:
        logger(f"No existing source roots to watch for '{config.knowledge.id}'.")
        return
    logger(f"Watching {len(roots)} source root(s) for '{config.knowledge.id}'.")
    runner = WatchIndexer(config, log=logger)
    for changes in watch(*roots, stop_event=stop_event):
        runner.handle_changes(changes)


def start_watch_thread(config: CarsenConfig, log: LogFn | None = None) -> tuple[threading.Thread, threading.Event]:
    """Start foreground watcher logic in a daemon thread and return thread plus stop event."""

    stop_event = threading.Event()
    thread = threading.Thread(
        target=watch_config,
        args=(config, stop_event, log),
        name=f"carsen-watch-{config.knowledge.id}",
        daemon=True,
    )
    thread.start()
    return thread, stop_event
