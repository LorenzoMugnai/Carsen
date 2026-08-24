# Core concepts

Carsen combines several ideas that may be unfamiliar if you mostly work with traditional scripts, notebooks and file systems. This section explains the vocabulary before going deeper into configuration or deployment.

```mermaid
flowchart TD
    A[Source material] --> B[Chunks]
    B --> C[Embeddings]
    C --> D[Qdrant]
    B --> E[Metadata and citations]
    F[MCP client] --> G[Carsen]
    G --> D
    G --> E
    G --> H[Cited retrieval results]
```

Start with:

- [MCP](concepts/mcp.md)
- [Qdrant](concepts/qdrant.md)
- [Embeddings](concepts/embeddings.md)
- [Chunks and citations](concepts/chunks-and-citations.md)
