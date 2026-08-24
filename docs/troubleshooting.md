# Troubleshooting

## Configuration not found

Use `ariadne list` to inspect registered instances, or pass `--config path/to/config.yaml` explicitly.

## Invalid knowledge ID

`knowledge.id` must be filesystem-safe. Use letters, numbers, underscores or hyphens, and avoid slashes or `..`.

## No chunks after indexing

Check that source paths exist from the configuration file's directory, ignored directories are not excluding the target, and the process can read the files. Run with `--force` to reprocess unchanged files.

## MCP package unavailable

Serving requires the `mcp` package. Install project dependencies in the environment running `ariadne serve`.

## HTTP port conflicts

Give each instance a unique `server.port`, especially when running multiple Docker services or systemd units.

## Unexpected search results

The runtime currently searches the local chunk store with sparse lexical retrieval. Ensure content has been indexed and use filters only for metadata keys present on chunks.
