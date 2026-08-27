from __future__ import annotations

from typing import Any

from carsen_mcp.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
    SearchResult,
    SparseRetriever,
    lookup_symbol,
    rrf_fuse,
)


def result(chunk_id: str, text: str, score: float = 1.0, **metadata: Any) -> SearchResult:
    return SearchResult(chunk_id=chunk_id, score=score, text=text, metadata=metadata)


class FixedRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.last_limit: int | None = None
        self.last_filters: dict[str, Any] | None = None

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        self.last_limit = limit
        self.last_filters = filters
        rows = self.results
        if filters:
            from carsen_mcp.retrieval.filters import filter_results
            rows = filter_results(rows, filters)
        return rows[:limit]


def corpus() -> list[SearchResult]:
    return [
        result("1", "def calibrate(self): return threshold", symbol="Detector.calibrate", source_path="src/detector.py", repository="core", language="python", document_type="code", source_type="code"),
        result("2", "async def process(self): return detection", symbol="Detector.process", source_path="src/detector.py", repository="core", language="python", document_type="code", source_type="code"),
        result("3", "Calibration guide and detector notes", symbol=None, source_path="docs/guide.md", repository="docs", language="markdown", document_type="markdown", source_type="documents"),
        result("4", "unrelated helper", symbol="helper", source_path="src/helper.py", repository="core", language="python", document_type="code", source_type="code"),
    ]


def test_sparse_retrieval_exact_identifier() -> None:
    hits = SparseRetriever(results=corpus()).search("Detector.calibrate", limit=3)
    assert hits[0].metadata["symbol"] == "Detector.calibrate"


def test_sparse_retrieval_finds_xml_detector_pixel_facts_from_natural_language_query() -> None:
    hits = SparseRetriever(
        results=[
            result(
                "xml-target",
                '<channel name="AIRS-CH1"><detector pixels="64 x 64" /></channel>',
                source_path="payload/arielrad_config.xml",
                document_type="xml",
                source_type="documents",
            ),
            result(
                "xml-other",
                '<channel name="AIRS-CH0"><detector pixels="32 x 32" /></channel>',
                source_path="payload/arielrad_config.xml",
                document_type="xml",
                source_type="documents",
            ),
        ]
    ).search("numero di pixel di airs ch1", limit=2)

    assert hits[0].chunk_id == "xml-target"


def test_sparse_retrieval_matches_hyphenated_xml_identifiers_without_exact_punctuation() -> None:
    hits = SparseRetriever(
        results=[
            result(
                "xml-target",
                '<channel name="AIRS-CH1"><detector pixels="64 x 64" /></channel>',
                source_path="payload/exosim.xml",
                document_type="xml",
                source_type="documents",
            )
        ]
    ).search("AIRS CH1 detector pixels", limit=1)

    assert hits[0].chunk_id == "xml-target"


def test_sparse_retrieval_matches_xml_config_path_and_pix_abbreviations() -> None:
    hits = SparseRetriever(
        results=[
            result(
                "airs-ch1",
                "<detector><spatial_pix>64</spatial_pix><spectral_pix>64</spectral_pix></detector>",
                source_path="payload/20250506_mpdb/airs_ch1.xml",
                document_type="xml",
                source_type="documents",
            ),
            result(
                "fgs",
                "<detector><spatial_pix>32</spatial_pix><spectral_pix>32</spectral_pix></detector>",
                source_path="payload/20250506_mpdb/fgs1.xml",
                document_type="xml",
                source_type="documents",
            ),
        ]
    ).search("numero di pixel di airs ch1", limit=2)

    assert hits[0].chunk_id == "airs-ch1"


def test_sparse_retrieval_bounds_huge_text_indexing_but_keeps_metadata_searchable() -> None:
    huge_text = "start token " + ("noise " * 100_000) + "zzzendmarker"

    retriever = SparseRetriever(
        results=[
            result(
                "huge",
                huge_text,
                source_path="payload/20250506_mpdb/airs_ch1.xml",
                document_type="xml",
                source_type="documents",
            )
        ]
    )

    assert retriever.search("airs ch1", limit=1)[0].chunk_id == "huge"
    assert retriever.search("zzzendmarker", limit=1) == []


def test_rrf_ordering_rewards_cross_retriever_agreement() -> None:
    a = result("a", "a")
    b = result("b", "b")
    c = result("c", "c")
    fused = rrf_fuse([[a, b], [b, c]], limit=3, k=10)
    assert [hit.chunk_id for hit in fused] == ["b", "a", "c"]


def test_filters_cover_metadata_predicates() -> None:
    retriever = SparseRetriever(results=corpus())
    hits = retriever.search("detector", limit=10, filters={"repository": "core", "path_prefix": "src/", "language": "python", "document_type": "code", "source_type": "code"})
    assert {hit.metadata["source_path"] for hit in hits} == {"src/detector.py"}
    symbol_hits = retriever.search("Detector.process", limit=10, filters={"symbol": "Detector.process"})
    assert [hit.metadata["symbol"] for hit in symbol_hits] == ["Detector.process"]


def test_hybrid_combination_limits_and_filter_plumbing() -> None:
    dense = FixedRetriever([result("dense", "semantic", source_path="a.py", repository="core"), result("shared", "shared", source_path="b.py", repository="core")])
    sparse = FixedRetriever([result("shared", "shared", source_path="b.py", repository="core"), result("sparse", "lexical", source_path="c.py", repository="other")])
    hybrid = HybridRetriever(dense, sparse, HybridRetrievalConfig(dense_candidates=2, sparse_candidates=2, final_results=2))
    hits = hybrid.search("query", filters={"repository": "core"})
    assert [hit.chunk_id for hit in hits] == ["shared", "dense"]
    assert dense.last_limit == 2 and sparse.last_limit == 2
    assert dense.last_filters == {"repository": "core"}


def test_result_limit_and_max_results_per_source() -> None:
    fused = rrf_fuse([
        [result("1", "one", source_path="same.py"), result("2", "two", source_path="same.py"), result("3", "three", source_path="other.py")]
    ], limit=3, max_results_per_source=1)
    assert [hit.chunk_id for hit in fused] == ["1", "3"]


def test_exact_symbol_lookup() -> None:
    hits = lookup_symbol(corpus(), "Detector.process", filters={"repository": "core"})
    assert len(hits) == 1
    assert hits[0].metadata["source_path"] == "src/detector.py"
