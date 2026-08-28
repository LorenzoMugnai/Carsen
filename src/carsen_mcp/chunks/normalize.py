"""Post-parse chunk normalisation: split oversized chunks and renumber order.

Parsers emit one chunk per element (function, section, XML node), which can be
far larger than an embedding model's context and dilutes lexical scoring. This
pass splits any chunk over a token budget into overlapping line-aligned
sub-chunks and renumbers ``order`` densely per file so neighbour expansion and
FTS ordering stay correct.
"""

from __future__ import annotations

from dataclasses import replace

from .model import Chunk

#: Rough characters-per-token ratio for budgeting without a real tokeniser.
CHARS_PER_TOKEN = 4


def normalize_chunks(chunks: list[Chunk], max_tokens: int | None, overlap_tokens: int = 0) -> list[Chunk]:
    """Return chunks with oversized entries split and ``order`` renumbered per file."""

    if not max_tokens or max_tokens < 1:
        return _renumbered(chunks)
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = max(0, min(overlap_tokens, max_tokens // 2)) * CHARS_PER_TOKEN
    expanded: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.text) <= max_chars:
            expanded.append(chunk)
        else:
            expanded.extend(_split_chunk(chunk, max_chars, overlap_chars))
    return _renumbered(expanded)


def _renumbered(chunks: list[Chunk]) -> list[Chunk]:
    result: list[Chunk] = []
    for index, chunk in enumerate(chunks):
        metadata = {**chunk.metadata, "order": index}
        result.append(replace(chunk, order=index, metadata=metadata, chunk_id="", content_hash="", indexed_at=""))
    return result


def _split_chunk(chunk: Chunk, max_chars: int, overlap_chars: int) -> list[Chunk]:
    lines = chunk.text.splitlines(keepends=True)
    if not lines:
        return [chunk]
    windows = _line_windows(lines, max_chars, overlap_chars)
    pieces: list[Chunk] = []
    for piece_index, (start, end) in enumerate(windows):
        text = "".join(lines[start:end])
        start_line = chunk.start_line + start
        end_line = min(chunk.end_line, chunk.start_line + end - 1) if chunk.end_line else chunk.start_line + end - 1
        metadata = {
            **chunk.metadata,
            "parent_chunk_id": chunk.chunk_id,
            "sub_chunk_index": piece_index,
            "sub_chunk_count": len(windows),
        }
        pieces.append(
            replace(
                chunk,
                start_line=start_line,
                end_line=end_line,
                text=text,
                metadata=metadata,
                chunk_id="",
                content_hash="",
                indexed_at="",
            )
        )
    return pieces


def _line_windows(lines: list[str], max_chars: int, overlap_chars: int) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    start = 0
    total = len(lines)
    while start < total:
        end = start
        size = 0
        while end < total and (end == start or size + len(lines[end]) <= max_chars):
            size += len(lines[end])
            end += 1
        windows.append((start, end))
        if end >= total:
            break
        back = 0
        overlap = 0
        while end - 1 - back > start and overlap < overlap_chars:
            overlap += len(lines[end - 1 - back])
            back += 1
        start = max(start + 1, end - back)
    return windows
