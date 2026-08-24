# ADR 0002: Qdrant per-instance collections

## Status

Accepted.

## Context

Qdrant stores vectors and payload metadata for retrieval. Ariadne's instance model requires storage isolation so that one knowledge base cannot accidentally return chunks from another.

## Decision

Each Ariadne knowledge instance writes to its own Qdrant collection. The collection name is part of the instance configuration and should be unique across deployed instances.

## Alternatives

- Store every instance in one collection and filter by instance id.
- Run a separate Qdrant service for every Ariadne instance.
- Use a non-vector database as the primary retrieval store.

## Consequences

- Collection-level isolation matches Ariadne's operational model.
- Index deletion and rebuilds can target one instance without disturbing others.
- Shared Qdrant infrastructure remains possible, but naming conventions and backups must account for multiple collections.
