# Carsen documentation

Carsen is a local-first MCP knowledge engine for indexed code and document collections. These docs are written for researchers, developers and academic teams who need reliable retrieval with traceable citations.

If you are new to vector search or MCP, start here:

- [Quickstart for academic users](quickstart.md)
- [Core concepts](concepts.md)
- [Carsen for academic groups](academic-users.md)

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
