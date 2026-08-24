# ADR 0004: Hybrid dense/sparse retrieval

## Status

Accepted.

## Context

Code and technical documents contain both semantic concepts and exact identifiers. Dense retrieval is useful for conceptual similarity, while sparse and exact retrieval are better for symbols, filenames and precise phrases.

## Decision

Ariadne supports hybrid retrieval that can combine dense, sparse and exact results over the same canonical chunk set. Fusion and optional reranking can be applied after candidate retrieval.

## Alternatives

- Dense vector retrieval only.
- Keyword or exact search only.
- Separate tools for semantic search and exact lookup with no result fusion.

## Consequences

- Retrieval quality improves across mixed code and prose corpora.
- Query diagnostics can expose how candidates were found.
- Indexing and configuration are more complex because multiple retrieval paths may need to be maintained.
