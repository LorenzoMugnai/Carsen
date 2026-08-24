# Carsen documentation

Carsen is a Python 3.12 MCP knowledge server for indexing local code and document sources into isolated knowledge instances. This documentation describes the implemented repository state.

## Contents

- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Knowledge instances](knowledge-instances.md)
- [Indexing](indexing.md)
- [Retrieval](retrieval.md)
- [Citations](citations.md)
- [MCP](mcp.md)
- [Deployment](deployment.md)
- [Security](security.md)
- [Development](development.md)
- [Testing](testing.md)
- [Extending](extending.md)
- [Troubleshooting](troubleshooting.md)

## Current scope

Implemented features include YAML configuration validation, local registry commands, incremental file discovery, canonical chunk storage, sparse lexical retrieval, hybrid retrieval primitives, citation formatting, MCP tool wiring, Docker examples and a systemd unit template.

Dense embeddings and Qdrant configuration are present in the model and storage settings. The active MCP runtime currently serves from the local chunk store using sparse retrieval.
