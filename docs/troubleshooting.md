# Troubleshooting

## Configuration not found

Use `carsen list` to inspect registered instances, or pass `--config path/to/config.yaml` explicitly.

## Invalid knowledge ID

`knowledge.id` must be filesystem-safe. Use letters, numbers, underscores or hyphens, and avoid slashes or `..`.

## No chunks after indexing

Check that source paths exist from the configuration file's directory, ignored directories are not excluding the target, and the process can read the files. Run with `--force` to reprocess unchanged files.

## MCP package unavailable

Serving requires the `mcp` package. Install project dependencies in the environment running `carsen serve`.

## SQLite FTS5 module missing

The chunk store uses SQLite FTS5 for lexical search. If Carsen reports that FTS5 is unavailable, the Python interpreter is linked against a SQLite build compiled without it; use a Python distribution with a standard SQLite (most do), or install one via `uv`/`pyenv`.

## Migrating an older chunk store

Instances created before the SQLite chunk store keep a `chunks/` directory of `.jsonl` files. Carsen imports it automatically the first time the new store opens. After confirming search works you can delete the old `chunks/` directory; `carsen index --force` also rebuilds cleanly.

## HTTP port conflicts

Give each instance a unique `server.port`, especially when running multiple Docker services or systemd units.

## Unexpected search results

The runtime currently searches the local chunk store with sparse lexical retrieval. Ensure content has been indexed and use filters only for metadata keys present on chunks.
