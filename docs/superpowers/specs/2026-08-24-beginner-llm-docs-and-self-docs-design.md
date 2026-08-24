# Beginner LLM Docs, Visual Refresh and Self-Docs Init Design

## Goal

Make Carsen easier to adopt for users who may know Python or research workflows but may not know MCP, local retrieval, embeddings, Qdrant or LLM client configuration.

The project should provide a clearer beginner path from installation to first LLM-assisted use, a more polished documentation site, and a small `carsen init-docs` command that lets users create a Carsen knowledge instance for Carsen's own documentation.

## Audience

Primary audience:

- Students, academic researchers and lab engineers.
- Users who want to connect their files, papers or code to an LLM but do not yet understand MCP.
- Users who need practical setup guidance more than internal architecture details.

Secondary audience:

- Developers integrating Carsen into editor, desktop or agent clients.
- Existing MCP users who need concise command references.

All repository-facing documentation and UI copy must be written in English.

## Recommended approach

Implement a focused combined milestone:

1. Expand the quickstart into a complete beginner path.
2. Add a dedicated LLM/MCP integration guide.
3. Modernize the MkDocs presentation using the existing three logo assets.
4. Add `carsen init-docs` as a small CLI convenience command for creating an isolated Carsen documentation instance.

This is intentionally smaller than a full onboarding wizard. It keeps Carsen's named-instance model intact while giving new users a practical, copy-adaptable path.

## User journey

The updated documentation should teach this sequence:

1. Install Carsen.
2. Understand, in plain language, that Carsen is not a chat model. Carsen retrieves cited context; the LLM client generates final answers.
3. Create a named knowledge instance.
4. Index local documents or code.
5. Run a terminal search to prove retrieval works before involving an LLM.
6. Serve the instance over MCP.
7. Add Carsen to an LLM-capable MCP client.
8. Ask a question and check that the answer is grounded in cited retrieved context.
9. Optionally run `carsen init-docs --index` to create a self-documentation instance and ask an LLM how to configure Carsen itself.

The quickstart should stay practical and short enough to complete in one sitting. Longer explanations belong in the new LLM integration guide and existing reference pages.

## Documentation changes

### `docs/quickstart.md`

Rewrite the quickstart as the main beginner path. It should include:

- A short explanation of Carsen, MCP and LLM roles.
- Installation and validation commands.
- `carsen create`, `carsen index`, `carsen search` and `carsen serve` examples.
- A generic MCP client configuration example for local stdio use.
- A short “first question to ask your LLM” example.
- A final section for `carsen init-docs --index` as an optional self-help path.
- Links to deeper LLM integration, MCP, indexing and configuration pages.

Tone: clear, calm and beginner-friendly. Avoid assuming that the reader knows what an MCP server is.

### `docs/llm-integration.md`

Add a new step-by-step guide for connecting Carsen to LLM clients. It should explain:

- Carsen retrieves context; the LLM remains replaceable.
- MCP as the connection layer between an LLM client and Carsen.
- Stdio transport for local desktop/editor/agent clients.
- HTTP transport only where appropriate, with local-first safety notes.
- How to create, index and verify an instance before connecting it to a client.
- Generic MCP configuration snippets that users can adapt to Claude Desktop, Cursor, VS Code, OpenCode or another MCP-capable client without making Carsen depend on any provider.
- A more advanced Python-oriented path for users who want to retrieve context and pass it to their own LLM code.
- Troubleshooting for common failures:
  - Qdrant is not running or dense search is unavailable.
  - The instance has no chunks.
  - The LLM client cannot start or see the MCP server.
  - The user expects Carsen to write final answers rather than retrieve cited context.

### `docs/mcp.md`

Keep this as the technical MCP reference. Update it to link to the LLM integration guide and include a concise sequence diagram or flow that shows:

```text
User question -> LLM client -> Carsen MCP server -> Carsen retrieval -> cited context -> LLM client -> final answer
```

### `docs/cli-reference.md`

Add `carsen init-docs` with options, defaults and examples.

### `docs/index.md`

Refresh the homepage with:

- A hero section using the full logo.
- Clear CTAs: Quickstart, Connect to an LLM, Core concepts.
- Feature cards for local-first operation, isolated instances, MCP serving and cited retrieval.
- A simple “how it works” flow.
- A self-docs card showing `carsen init-docs --index`.

## Visual design

Carsen already has three logo assets. Use them intentionally:

- `docs/assets/logo_character.png`: MkDocs theme logo and favicon.
- `docs/assets/logo.png`: homepage hero and major brand moments.
- `docs/assets/logo_text.png`: wordmark usage inside homepage sections or cards.

Update `mkdocs.yml` to use Material features that improve navigation without heavy custom behavior:

- `navigation.instant`
- `navigation.instant.prefetch`
- `navigation.tracking`
- `search.suggest`
- `search.highlight`

Add `extra_css: [stylesheets/extra.css]` and create `docs/stylesheets/extra.css` for restrained polish:

- responsive hero layout;
- card grid styling;
- restrained shadows and borders;
- readable spacing for academic documentation;
- responsive logo sizing.

The visual style should feel modern, trustworthy and research-oriented, not like a loud marketing landing page.

## `carsen init-docs` command

Add a CLI command:

```bash
carsen init-docs
```

Default behavior:

- Create a registered config named `carsen-docs`.
- Use the current working directory as the source root by default.
- Validate that `<source>/docs` exists.
- Set `sources.documents` to the Carsen docs path.
- Set `sources.code` to `<source>/src/carsen_mcp` when that directory exists, otherwise leave code sources empty.
- Preserve existing per-instance defaults for storage, chunk store, Qdrant collection and MCP transport.
- Do not expose HTTP publicly by default.
- Print next commands after success.

Options:

```bash
carsen init-docs --docs-path PATH
carsen init-docs --source PATH
carsen init-docs --name NAME
carsen init-docs --index
carsen init-docs --force
```

Option semantics:

- `--name`: override the default instance id/name from `carsen-docs`.
- `--source`: point to a Carsen source checkout; the command looks for `docs/` under it.
- `--docs-path`: explicitly point to the docs directory when source detection is not enough.
- `--index`: create the config and run the existing indexing flow for the new instance.
- `--force`: overwrite an existing registry config for the same instance.

If both `--source` and `--docs-path` are accepted, `--docs-path` should take precedence for documents. `--source` may still be used to discover `src/carsen_mcp`.

Failure when docs cannot be found should be actionable:

```text
Could not find Carsen documentation at <path>. Run this command from a Carsen source checkout or pass --docs-path PATH.
```

Recommended user workflow:

```bash
carsen init-docs --index
carsen search carsen-docs "How do I connect Carsen to an LLM?"
carsen serve carsen-docs --transport stdio
```

## Constraints

- Preserve named-instance isolation.
- Do not add provider-specific LLM SDK dependencies.
- Do not turn Carsen into an answer-generation system.
- Do not make Qdrant mandatory for documentation-only setup or config inspection paths.
- Keep local-first defaults.
- Keep generated configs compatible with existing registry and config models.
- Keep docs and UI copy in English.
- Do not reintroduce Ariadne naming.

## Testing and verification

Implementation should include or update tests for:

- CLI help includes `init-docs`.
- `init-docs` creates a config from a temp source tree containing `docs/`.
- `init-docs --docs-path` works without relying on current working directory detection.
- missing docs path fails with an actionable message.
- `--force` or existing-config behavior is deterministic.
- documentation presence checks cover the new LLM guide and `init-docs` references.

Recommended verification commands:

```bash
uv run mkdocs build --strict
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m pytest tests/test_documentation_presence.py tests/test_ci_scaffolding.py -v
.venv/bin/python -m pytest tests/test_config.py tests/test_registry.py tests/test_mcp_runtime.py -v
```

For the final implementation branch, run the full test suite if the CLI command or config generation touches shared runtime paths.

## Out of scope

- A full interactive setup wizard.
- Automatic LLM provider configuration.
- Public remote MCP deployment defaults.
- New embedding providers or rerankers.
- Changing MCP tool semantics.
- Reworking the core retrieval architecture.

## Open implementation notes

- Prefer a small helper in CLI/config/registry code over embedding all logic directly in a Typer command if tests would otherwise become awkward.
- Keep `--index` simple by reusing existing indexing code. If that coupling becomes large, implement config creation first and document `carsen index carsen-docs` as the immediate next step.
- Use the existing specs and plans in `docs/superpowers/` as prior context, but this combined design is the approved direction for the next implementation plan.
