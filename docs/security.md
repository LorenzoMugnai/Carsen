# Security

## Assumptions

Ariadne indexes files it can read and serves retrieved text to MCP clients. It assumes configurations, source paths and connected clients are trusted unless external controls are added.

## Boundaries

- `policy.allow_external_llm` is advisory metadata, not runtime enforcement.
- The MCP server does not implement authentication or authorisation itself.
- Local filesystem permissions and deployment-level controls define what can be indexed.
- HTTP deployments should be protected by network policy, TLS and authentication at a proxy or gateway.

## Multi-instance considerations

Use separate data directories, Qdrant collections, ports and service users where stronger separation is required. Do not share writable source mounts with untrusted users.
