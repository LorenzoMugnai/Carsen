# Deployment

## Local development

Install the package in a Python 3.12 environment, create or provide a YAML configuration, index sources, then serve:

```bash
carsen validate --config config.example.yaml
carsen index --config config.example.yaml --embed
carsen serve --config config.example.yaml
```

Use `carsen reembed --config config.example.yaml` after changing embedding settings, and `carsen delete-index --config config.example.yaml` when intentionally removing an instance index.

Before a release, run an operational smoke with a temporary Qdrant container and a local streamable HTTP MCP server. The smoke should prove that `index --embed` writes the configured collection and that an MCP client can call `knowledge_info` and a retrieval tool through `/mcp`.

## Remote HTTP

Set `server.transport: http`, bind an appropriate `host` and use a unique `port` per instance. Place an authenticating reverse proxy in front if exposing beyond trusted local networks.

MCP tool calls run in a worker-thread pool, so a shared HTTP instance stays responsive to other clients while one request runs a slow embedding or reranking pass.

## Scaling a shared instance

As a shared knowledge base grows, tune the Qdrant collection through `storage.tuning` rather than adding hardware first: raise `hnsw_ef` if dense recall drops, enable `quantization: scalar` when the collection outgrows RAM, then the `on_disk` options for larger-than-memory corpora. See [Tuning Qdrant for large collections](configuration.md#tuning-qdrant-for-large-collections). Changing `quantization` or the `on_disk` settings requires `carsen reembed`.

## Docker

The repository includes a `Dockerfile` and `docker-compose.example.yml`. The compose file demonstrates Qdrant plus two Carsen services with separate configs, ports and data volumes.

## systemd

`deployment/systemd/carsen@.service` runs `carsen serve %i --transport http` under an `carsen` user with `CARSEN_CONFIG_DIR=/etc/carsen`. Enable one unit per registered instance, for example `carsen@example.service`.
