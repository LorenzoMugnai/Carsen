# Knowledge instances

A knowledge instance is a single configured knowledge base. It is selected by a registered name or by `--config PATH`.

## Registry workflow

- Create a starter configuration: `ariadne create NAME --code PATH --documents PATH`.
- List configurations: `ariadne list`.
- Validate: `ariadne validate NAME` or `ariadne validate --config path/to/file.yaml`.
- Inspect status: `ariadne status NAME`.

The registry stores discoverable configurations for local use. Explicit `--config` paths are also supported and are useful for containers or systemd.

## Multi-instance operation

Each instance should have a unique `knowledge.id`, port, data directory and, when Qdrant is used, collection. Docker examples run `ariadne-alpha` and `ariadne-beta` as separate services with separate mounted data volumes and HTTP ports.

The runtime filters loaded chunks by `knowledge_id`, so an instance only serves chunks belonging to its configured ID.
