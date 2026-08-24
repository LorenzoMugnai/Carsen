# ADR 0005: Metadata-backed citations

## Status

Accepted.

## Context

MCP clients and downstream LLMs need evidence they can display or quote. Citations based only on generated text are difficult to audit and can drift from the indexed source.

## Decision

Carsen citations are backed by chunk metadata captured during parsing and indexing, including source identifiers and location information where available. Retrieval responses should carry enough metadata for clients to inspect the cited source.

## Alternatives

- Let the generative LLM invent or format citations from retrieved text.
- Return raw chunks without citation metadata.
- Store citation data only in client-specific formats.

## Consequences

- Citations remain tied to indexed source material rather than generated prose.
- Clients can render citations consistently across LLM providers.
- Parsers must preserve useful source metadata for each chunk.
