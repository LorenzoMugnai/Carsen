# ADR 0006: Generative LLM independence

## Status

Accepted.

## Context

Ariadne is an MCP knowledge service, not an answer-generation platform. Users may connect different clients and LLM providers over time, and those choices should not require rebuilding indexes or changing storage formats.

## Decision

Ariadne stays independent of the generative LLM. It indexes sources, retrieves relevant chunks and returns citation metadata through MCP. The client or external model is responsible for composing final answers.

## Alternatives

- Bundle one supported chat model into Ariadne.
- Store prompts and answer-generation policy as part of each index.
- Optimise the API for a single client or LLM vendor.

## Consequences

- Ariadne can serve multiple MCP clients and model providers from the same indexes.
- Retrieval and citation behaviour can be tested without invoking a generative model.
- Some end-user features, such as answer style and prompt policy, remain outside Ariadne and must be handled by clients.
