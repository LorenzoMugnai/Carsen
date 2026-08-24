# MCP

Ariadne exposes one MCP server per knowledge instance.

## Serving

```bash
ariadne serve NAME
ariadne serve --config path/to/config.yaml --transport http
```

Supported transports are `stdio` and `http`. HTTP uses streamable HTTP at `/mcp` with configured `host` and `port`.

## Tools

- `knowledge_info()`: returns instance ID, name, description, chunk count and source count.
- `search_knowledge(query, limit=8, filters=None)`: searches all indexed chunks.
- `search_code(query, limit=8, filters=None)`: searches code-like chunks.
- `search_documents(query, limit=8, filters=None)`: searches document chunks.
- `find_symbol(symbol, limit=8)`: looks up matching symbols.
- `read_source(source_id=None, chunk_id=None, previous=0, next=0)`: returns a target chunk and surrounding chunks.
- `get_source_metadata(source_id=None, chunk_id=None)`: returns metadata without text.
- `get_related_sources(source_id=None, chunk_id=None, limit=5)`: finds related chunks from target metadata and text.
