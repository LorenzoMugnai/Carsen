# ADR 0003: Canonical chunk store

## Status

Accepted.

## Context

Parsed source material needs stable chunk identities, citation ranges and metadata. Recomputing chunks differently for every retrieval or embedding pass would make citations fragile and re-indexing wasteful.

## Decision

Ariadne maintains a canonical chunk store per instance. Parsed chunks, source metadata and stable identifiers are recorded before being embedded or written to retrieval indexes.

## Alternatives

- Treat vector payloads as the only chunk store.
- Generate chunks dynamically at query time.
- Keep separate chunk representations for each retrieval backend.

## Consequences

- Re-embedding can reuse existing chunks without reparsing unchanged sources.
- Citations and diagnostics can refer to stable chunk metadata.
- The local state directory becomes part of the instance's durable operational data.
