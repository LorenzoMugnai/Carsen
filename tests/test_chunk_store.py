from __future__ import annotations

import json
from pathlib import Path

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore


def make(knowledge_id: str, source_path: str, symbol: str | None, text: str, order: int = 0, **metadata: object) -> Chunk:
    return Chunk(
        knowledge_id=knowledge_id,
        source_path=source_path,
        kind=str(metadata.pop("kind", "function")),
        symbol=symbol,
        start_line=order * 10 + 1,
        end_line=order * 10 + 5,
        text=text,
        order=order,
        metadata={"source_path": source_path, **metadata},
    )


def test_round_trip_fidelity(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path)
    original = make("kb", "src/a.py", "A.run", "def run(): return 1", 2, source_type="code", language="python", note="keep me")
    store.replace_file_chunks("src/a.py", [original])

    loaded = store.get_chunk(original.chunk_id)
    assert loaded is not None
    assert loaded.to_dict() == original.to_dict()
    assert store.count("kb") == 1
    assert store.source_count("kb") == 1


def test_replace_is_per_file_and_bumps_generation(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path)
    g0 = store.generation()
    store.replace_file_chunks("a.py", [make("kb", "a.py", "a", "alpha one"), make("kb", "a.py", "b", "alpha two", 1)])
    store.replace_file_chunks("b.py", [make("kb", "b.py", "c", "beta one")])
    assert store.count("kb") == 3
    assert store.generation() > g0

    store.replace_file_chunks("a.py", [make("kb", "a.py", "a", "alpha replaced")])
    assert store.count("kb") == 2
    assert store.chunks_for_source("a.py")[0].text == "alpha replaced"

    store.delete_file_chunks("b.py")
    assert store.count("kb") == 1


def test_prune_unknown_sources(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path)
    store.replace_file_chunks("/abs/keep.py", [make("kb", "keep.py", "k", "keep this")])
    store.replace_file_chunks("/abs/drop.py", [make("kb", "drop.py", "d", "drop this")])

    removed = store.prune_unknown_sources("kb", {"/abs/keep.py", "keep.py"})

    assert removed == 1
    assert [chunk.source_path for chunk in store.load_all_chunks()] == ["keep.py"]


def test_sparse_search_ranks_symbol_match_and_applies_filters(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path)
    store.replace_file_chunks(
        "src/detector.py",
        [make("kb", "src/detector.py", "Detector.calibrate", "def calibrate the detector threshold", source_type="code")],
    )
    store.replace_file_chunks(
        "docs/guide.md",
        [make("kb", "docs/guide.md", None, "calibrate the detector in the guide", kind="markdown", source_type="documents")],
    )

    top = store.search_sparse("Detector.calibrate", limit=5, knowledge_id="kb")
    assert top[0].metadata["source_path"] == "src/detector.py"

    docs_only = store.search_sparse("calibrate detector", limit=5, filters={"source_type": "documents"}, knowledge_id="kb")
    assert {result.metadata["source_path"] for result in docs_only} == {"docs/guide.md"}

    prefixed = store.search_sparse("calibrate detector", limit=5, filters={"path_prefix": "src/"}, knowledge_id="kb")
    assert {result.metadata["source_path"] for result in prefixed} == {"src/detector.py"}


def test_find_symbol_returns_all_matches_up_to_limit(tmp_path: Path) -> None:
    store = ChunkStore(tmp_path)
    store.replace_file_chunks("a.py", [make("kb", "a.py", "shared", "one")])
    store.replace_file_chunks("b.py", [make("kb", "b.py", "shared", "two")])
    store.replace_file_chunks("c.py", [make("kb", "c.py", "other", "three")])

    assert {chunk.source_path for chunk in store.find_symbol("shared")} == {"a.py", "b.py"}
    assert len(store.find_symbol("shared", limit=1)) == 1
    assert store.find_symbol("missing") == []


def test_imports_legacy_jsonl_directory_once(tmp_path: Path) -> None:
    legacy = tmp_path / "chunks"
    legacy.mkdir()
    chunk = make("kb", "legacy.py", "legacy", "legacy content")
    (legacy / "0001.jsonl").write_text(json.dumps(chunk.to_dict()) + "\n", encoding="utf-8")

    store = ChunkStore(tmp_path)
    assert store.count("kb") == 1
    assert store.get_chunk(chunk.chunk_id) is not None

    # A second open must not double-import.
    store.close()
    reopened = ChunkStore(tmp_path)
    assert reopened.count("kb") == 1
