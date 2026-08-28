# Set up with an AI agent

This page is written for an AI coding agent — or a user who has asked their assistant
to "install and set up Carsen". Run the steps in order. Each step has a check;
stop and report if a check fails.

Carsen works in a **sparse-only mode** with no vector database and no embedding
model, so the default path below needs nothing beyond Python and `uv`. Dense
semantic retrieval is an opt-in extra covered at the end.

## 1. Prerequisites

```bash
python --version   # need >= 3.12
uv --version       # if missing: curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Check:** both commands print a version. Python must be 3.12 or newer.

## 2. Get Carsen

```bash
git clone https://github.com/LorenzoMugnai/Carsen.git
cd Carsen
uv sync
```

**Check:** `uv sync` completes without error and creates `.venv/`.

## 3. Verify the install

```bash
uv run carsen --help
uv run carsen status
```

**Check:** `carsen --help` lists commands including `create`, `index`, `search`,
`serve`. `carsen status` reports that Carsen is installed.

## 4. Create a knowledge instance

Pick a short, filesystem-safe name and point it at the code and/or document
directories to index.

```bash
uv run carsen create my-kb --code /abs/path/to/code --documents /abs/path/to/docs
uv run carsen validate my-kb
```

`create` writes a YAML file under the Carsen config directory (`~/.config/carsen`
by default). To index without any dense retrieval, edit that file and set
`retrieval.dense_candidates: 0` — or leave it and simply skip `--embed` below.

**Check:** `carsen validate my-kb` reports the configuration is valid.

## 5. Index the sources

```bash
uv run carsen index my-kb
```

**Check:** the command prints `Indexed 'my-kb': new=<N> ... chunks=<M>` with
`M > 0`. This builds the local SQLite chunk store; it needs no Qdrant and no model.

## 6. Test retrieval

```bash
uv run carsen search my-kb "a phrase you know appears in the sources"
```

**Check:** results are printed, each with a citation like `path/to/file.py:12-31`.

## 7. Serve over MCP

For a local MCP client (Claude Code, an editor, an Orchestral agent):

```bash
uv run carsen serve my-kb --transport stdio
```

Register it in an MCP client config (`.mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "carsen-my-kb": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/Carsen", "carsen", "serve", "my-kb", "--transport", "stdio"]
    }
  }
}
```

For an Orchestral agent (e.g. inside an ASTER-style toolkit):

```python
from orchestral.mcp import MCPClient

carsen = MCPClient(server_command=[
    "uv", "run", "--directory", "/abs/path/to/Carsen",
    "carsen", "serve", "my-kb", "--transport", "stdio",
])
carsen.connect()
tools += carsen.get_orchestral_tools()  # search_knowledge, search_code, find_symbol, read_source, ...
```

Or serve over HTTP and connect by URL:

```bash
uv run carsen serve my-kb --transport http   # streamable HTTP at http://127.0.0.1:8765/mcp
```

**Check:** an MCP client can list the Carsen tools and a `search_knowledge` call
returns cited results.

## 8. Optional: dense semantic retrieval

Dense retrieval adds meaning-based matching on top of lexical search. It needs a
running Qdrant and an embedding model.

```bash
docker run --rm -p 6333:6333 -p 6334:6334 qdrant/qdrant       # in another terminal
uv run carsen index my-kb --embed
```

To avoid a PyTorch download, set `models.embedding.provider: fastembed` (install
`uv sync --extra fastembed`) or `provider: openai_compatible` with a `base_url`.
See [Configuration](configuration.md).

## If a step fails

| Symptom | Fix |
| --- | --- |
| `carsen` not found | Use `uv run carsen ...` from the repo directory, or activate `.venv`. |
| "SQLite FTS5 module missing" | The Python build lacks FTS5; use a standard Python distribution (most have it) via `uv`/`pyenv`. |
| `index` finds 0 chunks | Check the `--code`/`--documents` paths exist and are not excluded by `indexing.ignored_directories`; re-run with `--force`. |
| Dense phase fails / Qdrant refused | Sparse search still works. Set `retrieval.dense_candidates: 0` and skip `--embed`. |
| Embedding model download is slow | Use `provider: fastembed` or a remote `openai_compatible` endpoint. |

## Going further

- `AGENTS.md` in the repository root is the canonical operating guide for agents
  working *on* Carsen.
- `carsen init-self --index` creates a knowledge instance of Carsen's own docs and
  source, so an agent can ask Carsen how to configure and operate Carsen.
