from __future__ import annotations

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.normalize import normalize_chunks


def make(text: str, start_line: int = 1, order: int = 0, symbol: str | None = None) -> Chunk:
    end_line = start_line + max(0, text.count("\n"))
    return Chunk("kb", "src/a.py", "function", symbol, start_line, end_line, text, order=order, metadata={"source_path": "src/a.py"})


def test_small_chunks_pass_through_but_order_is_densified() -> None:
    chunks = [make("one", order=5), make("two", order=9)]
    result = normalize_chunks(chunks, max_tokens=1000, overlap_tokens=100)
    assert [chunk.text for chunk in result] == ["one", "two"]
    assert [chunk.order for chunk in result] == [0, 1]
    assert [chunk.metadata["order"] for chunk in result] == [0, 1]


def test_oversized_chunk_is_split_into_overlapping_line_windows() -> None:
    lines = [f"line {i} " + "x" * 30 + "\n" for i in range(40)]
    big = make("".join(lines), start_line=10, order=0, symbol="Big.method")

    pieces = normalize_chunks([big], max_tokens=25, overlap_tokens=5)  # ~100 char windows

    assert len(pieces) > 1
    assert "".join(dict.fromkeys(piece.text for piece in pieces))  # non-empty
    # every source line appears in at least one piece
    joined = "\n".join(piece.text for piece in pieces)
    for i in range(40):
        assert f"line {i} " in joined
    # metadata records the split lineage
    assert pieces[0].metadata["parent_chunk_id"] == big.chunk_id
    assert pieces[0].metadata["sub_chunk_count"] == len(pieces)
    assert [piece.metadata["sub_chunk_index"] for piece in pieces] == list(range(len(pieces)))
    # line ranges advance and stay within the parent
    assert pieces[0].start_line == 10
    assert all(piece.symbol == "Big.method" for piece in pieces)
    assert pieces[-1].end_line <= big.end_line
    # consecutive windows overlap
    assert pieces[1].start_line <= pieces[0].end_line


def test_max_tokens_none_disables_splitting() -> None:
    big = make("x" * 100_000)
    result = normalize_chunks([big], max_tokens=None)
    assert len(result) == 1
    assert result[0].text == big.text
