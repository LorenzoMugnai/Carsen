# ADR 0001: Separate knowledge instances

## Status

Accepted.

## Context

Ariadne needs to serve knowledge for multiple projects, document sets and trust boundaries. Combining all sources into one shared runtime would make configuration, indexing, access control and operational diagnosis harder.

## Decision

Ariadne uses named knowledge instances. Each instance has its own configuration, source list, state directory, Qdrant collection and MCP endpoint. Operators can run one or many instances under the same installation.

## Alternatives

- A single global index with metadata filters for every project.
- One full Ariadne installation per project.
- Client-side filtering without server-side instance boundaries.

## Consequences

- Project isolation is explicit and easy to reason about.
- Instances can be started, indexed, diagnosed and redeployed independently.
- Operators must manage multiple configurations and ports when running many instances.
