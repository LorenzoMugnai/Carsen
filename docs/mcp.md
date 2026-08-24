# MCP

Carsen exposes one MCP server per knowledge instance.

## Serving

```bash
carsen serve NAME
carsen serve --config path/to/config.yaml --transport http
```

Supported transports are `stdio` and `http`. HTTP uses streamable HTTP at `/mcp` with configured `host` and `port`.

At runtime Carsen first attempts hybrid retrieval over the configured dense Qdrant collection plus the local sparse index. If the dense store or embedding provider is unavailable, the MCP tools fall back to sparse retrieval from the instance-local chunk store rather than crossing into another instance.

## Tools

- `knowledge_info()`: returns instance ID, name, description, chunk count and source count.
- `search_knowledge(query, limit=8, filters=None)`: searches all indexed chunks.
- `search_code(query, limit=8, filters=None)`: searches code-like chunks.
- `search_documents(query, limit=8, filters=None)`: searches document chunks.
- `find_symbol(symbol, limit=8)`: looks up matching symbols.
- `read_source(source_id=None, chunk_id=None, previous=0, next=0)`: returns a target chunk and surrounding chunks.
- `get_source_metadata(source_id=None, chunk_id=None)`: returns metadata without text.
- `get_related_sources(source_id=None, chunk_id=None, limit=5)`: finds related chunks from target metadata and text.
