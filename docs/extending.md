# Extending

## Parsers

Add parser support in `ariadne_mcp.parsers` and route extensions through `parse_file`. Parsers should return canonical `Chunk` objects with stable boundaries, useful metadata and sensible `kind` and `symbol` values.

## Retrieval

Retrievers operate on `SearchResult` records. New dense or sparse implementations can be plugged into `HybridRetriever` if they expose `search(query, limit, filters)`.

## MCP tools

Add runtime behaviour to `InstanceRuntime`, then expose it in `create_mcp_server`. Keep tool responses serialisable dictionaries or lists and include citations where source text is returned.

## Storage

Preserve the distinction between canonical chunks, content hashes and vector/index storage. Instance IDs and collection names must remain isolated.
