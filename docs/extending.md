# Extending

## Parsers

Add parser support in `carsen_mcp.parsers` and route extensions through `parse_file`. Parsers should return canonical `Chunk` objects with stable boundaries, useful metadata and sensible `kind` and `symbol` values.

## Retrieval

Retrievers operate on `SearchResult` records. New dense or sparse implementations can be plugged into `HybridRetriever` if they expose `search(query, limit, filters)`.

## Embedding providers

Implement the `EmbeddingProvider` protocol (`dimensions`, `embed_texts`, `embed_query`) in `carsen_mcp.embeddings.providers` and add a branch to `embedding_provider_from_config`. Load heavy dependencies lazily inside the provider so `carsen validate` and sparse-only search never import them. `embed_query` may apply an asymmetric query instruction; `embed_texts` (used for indexing) must not. Built-in providers: `sentence_transformers` (PyTorch), `fastembed` (ONNX, no PyTorch, needs an explicit `dimensions`), `fake` (tests).

## MCP tools

Add runtime behaviour to `InstanceRuntime`, then expose it in `create_mcp_server`. Keep tool responses serialisable dictionaries or lists and include citations where source text is returned.

## Storage

Preserve the distinction between canonical chunks, content hashes and vector/index storage. Instance IDs and collection names must remain isolated.
