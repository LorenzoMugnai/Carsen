"""Command line interface for Carsen."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from types import TracebackType
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .config import CarsenConfig, load_config
from .registry import (
    create_config,
    create_self_docs_config,
    discover_configs,
    instance_metadata,
    list_configs,
)

app = typer.Typer(help="Carsen Knowledge Engine: manage isolated knowledge MCP instances.")


class _IndexProgress:
    def __init__(self) -> None:
        self.console = Console(stderr=True)
        self.started = monotonic()
        self.fingerprint_task: TaskID | None = None
        self.parse_task: TaskID | None = None
        self._progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=False,
        )

    def __enter__(self) -> _IndexProgress:
        self._progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._progress.__exit__(exc_type, exc, traceback)

    def __call__(self, event: str, payload: dict[str, Any]) -> None:
        elapsed = monotonic() - self.started
        if event == "discovered":
            self.console.print(f"Discovered {payload['files']} file(s).")
        elif event == "fingerprint_start":
            self.console.print(f"Fingerprinting {payload['total']} file(s) for incremental changes...")
            self.fingerprint_task = self._progress.add_task(
                "Fingerprinting files",
                total=payload["total"],
            )
        elif event == "file_fingerprinted" and self.fingerprint_task is not None:
            path = Path(payload["path"])
            self._progress.update(
                self.fingerprint_task,
                completed=payload["index"],
                description=f"Fingerprinting files ({path.name})",
            )
            if payload["index"] == payload["total"] or payload["index"] % 100 == 0:
                self.console.print(
                    f"Fingerprinted {payload['index']}/{payload['total']} file(s); current={path.name}"
                )
        elif event == "fingerprint_complete":
            self.console.print(f"Fingerprinting complete: {payload['total']} file(s) in {elapsed:.1f}s.")
        elif event == "classified":
            self.console.print(
                "Classified files: "
                f"new={payload['new']} unchanged={payload['unchanged']} changed={payload['changed']} "
                f"deleted={payload['deleted']} to_parse={payload['to_parse']}"
            )
        elif event == "parse_start":
            self.parse_task = self._progress.add_task(
                "Parsing/writing files",
                total=payload["total"],
            )
        elif event == "file_parsed" and self.parse_task is not None:
            description = (
                f"Parsing/writing files ({Path(payload['path']).name}, "
                f"chunks={payload['chunk_total']})"
            )
            self._progress.update(
                self.parse_task,
                completed=payload["index"],
                description=description,
            )
        elif event == "parse_complete":
            self.console.print(
                f"Parsed/wrote {payload['total']} file(s), chunks={payload['chunks']} "
                f"in {elapsed:.1f}s."
            )
        elif event == "deleted":
            self.console.print(f"Deleted stale file entries: {payload['files']}.")
        elif event == "embed_start":
            self.console.print(f"Embedding/upsert phase starting: chunks={payload['chunks']}.")
        elif event == "embed_complete":
            self.console.print(f"Embedding complete: chunks={payload['chunks']}.")
        elif event == "upsert_start":
            self.console.print(f"Upserting vectors: chunks={payload['chunks']}.")
        elif event == "upsert_complete":
            self.console.print(f"Vector upsert complete: chunks={payload['chunks']}.")


def _preview(text: str, length: int = 120) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= length else f"{collapsed[: length - 1]}…"


def _resolve_config(name: str | None, config: Path | None) -> CarsenConfig:
    """Resolve either an explicit YAML path or a registered knowledge name."""

    if config is not None:
        return load_config(config)
    if name is None:
        raise typer.BadParameter("provide a registered NAME or --config PATH")
    from .registry import config_path_for

    path = config_path_for(name)
    if not path.exists():
        raise typer.BadParameter(f"configuration '{name}' was not found at {path}")
    return load_config(path)


@app.command()
def create(
    name: Annotated[str, typer.Argument(help="Knowledge instance identifier to create.")],
    code: Annotated[list[Path] | None, typer.Option(help="Code source directory to include in the starter YAML.")] = None,
    documents: Annotated[list[Path] | None, typer.Option(help="Document source directory to include in the starter YAML.")] = None,
    overwrite: Annotated[bool, typer.Option(help="Replace an existing registry configuration.")] = False,
) -> None:
    """Create a starter YAML configuration in the local Carsen registry."""
    try:
        path = create_config(name, overwrite=overwrite, code=code, documents=documents)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Created configuration: {path}")


@app.command("init-self")
def init_docs(
    name: Annotated[
        str,
        typer.Option(help="Knowledge instance identifier for the Carsen self-reference instance."),
    ] = "carsen-self",
    source: Annotated[
        Path | None,
        typer.Option(help="Carsen source checkout containing a docs/ directory."),
    ] = None,
    docs_path: Annotated[
        Path | None,
        typer.Option(help="Explicit Carsen documentation directory to include."),
    ] = None,
    index_after_create: Annotated[
        bool,
        typer.Option("--index", help="Run indexing after writing the configuration."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace an existing registry configuration."),
    ] = False,
) -> None:
    """Create a local Carsen self-reference knowledge instance."""

    try:
        path = create_self_docs_config(
            name=name,
            source=source,
            docs_path=docs_path,
            overwrite=force,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Created Carsen self-reference configuration: {path}")
    if index_after_create:
        from .ingestion.indexer import index_config

        cfg = load_config(path)
        report = index_config(cfg)
        typer.echo(
            f"Indexed '{cfg.knowledge.id}': new={report.new} unchanged={report.unchanged} "
            f"changed={report.changed} deleted={report.deleted} chunks={report.chunks}"
        )
    else:
        typer.echo(f"Next: carsen index {name}")
    typer.echo(f"Search: carsen search {name} \"How do I connect Carsen to an LLM?\"")
    typer.echo(f"Serve: carsen serve {name} --transport stdio")


@app.command("list")
def list_command(config: Annotated[Path | None, typer.Option("--config", help="Include an explicit YAML configuration.")] = None) -> None:
    """List discoverable Carsen knowledge-instance configurations."""
    paths = discover_configs(config)
    if not paths:
        typer.echo("No Carsen configurations found.")
        return
    typer.echo("NAME\tSTATUS\tPORT\tCHUNKS\tSOURCES\tCOLLECTION\tDATA DIRECTORY")
    for cfg in list_configs(config):
        meta = instance_metadata(cfg)
        typer.echo(f"{meta['name']}\t{meta['status']}\t{meta['port']}\t{meta['chunks']}\t{meta['sources']}\t{meta['collection']}\t{meta['data_directory']}")


@app.command()
def validate(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to validate.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to validate.")] = None,
) -> None:
    """Validate a registered or explicit YAML knowledge configuration."""
    cfg = _resolve_config(name, config)
    typer.echo(f"Configuration '{cfg.knowledge.id}' is valid.")


@app.command()
def search(
    args: Annotated[list[str], typer.Argument(help="NAME QUERY, or QUERY when --config is provided.")],
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to search.")] = None,
    corpus: Annotated[str, typer.Option(help="Corpus to search: all, code or documents.")] = "all",
    limit: Annotated[int, typer.Option(help="Maximum results to return.")] = 8,
    debug: Annotated[bool, typer.Option(help="Show redacted retrieval diagnostics.")] = False,
) -> None:
    """Search a local Carsen chunk store."""

    if corpus not in {"all", "code", "documents"}:
        raise typer.BadParameter("corpus must be 'all', 'code' or 'documents'")
    if config is None:
        if len(args) < 2:
            raise typer.BadParameter("provide NAME and QUERY, or --config PATH and QUERY")
        name = args[0]
        query = " ".join(args[1:])
    else:
        if not args:
            raise typer.BadParameter("provide QUERY")
        name = None
        query = " ".join(args)
    from .mcp.runtime import InstanceRuntime

    cfg = _resolve_config(name, config)
    runtime = InstanceRuntime(cfg)
    payload: dict[str, Any] | None = None
    if debug:
        payload = runtime.search_debug(query, limit=limit)
        results = payload["results"]
    elif corpus == "code":
        results = runtime.search_code(query, limit=limit)
    elif corpus == "documents":
        results = runtime.search_documents(query, limit=limit)
    else:
        results = runtime.search_knowledge(query, limit=limit)
    for index, result in enumerate(results, start=1):
        typer.echo(f"{index}. {result['citation']} score={result['score']:.4f}")
        typer.echo(f"   {_preview(result['text'])}")
    if debug:
        diagnostics = payload["diagnostics"] if payload is not None else {}
        typer.echo("Diagnostics:")
        typer.echo(f"  mode: {diagnostics.get('mode')}")
        if diagnostics.get("fallback_reason"):
            typer.echo(f"  fallback: {diagnostics['fallback_reason']}")
        typer.echo(f"  sparse_candidates: {diagnostics.get('sparse_candidates', 0)}")
        typer.echo(f"  dense_candidates: {diagnostics.get('dense_candidates', 0)}")
        typer.echo(f"  ranking: {[item['chunk_id'] for item in diagnostics.get('fused_ranking') or diagnostics.get('ranking', [])]}")


@app.command()
def evaluate(
    args: Annotated[list[str], typer.Argument(help="NAME DATASET, or DATASET when --config is provided.")],
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to evaluate.")] = None,
) -> None:
    """Evaluate local retrieval against a YAML dataset."""

    if config is None:
        if len(args) != 2:
            raise typer.BadParameter("provide NAME and DATASET, or --config PATH and DATASET")
        name = args[0]
        dataset_path = Path(args[1])
    else:
        if len(args) != 1:
            raise typer.BadParameter("provide DATASET")
        name = None
        dataset_path = Path(args[0])
    from .evaluation import average_metrics, evaluate_results, load_evaluation_dataset
    from .mcp.runtime import InstanceRuntime

    cfg = _resolve_config(name, config)
    runtime = InstanceRuntime(cfg)
    dataset = load_evaluation_dataset(dataset_path)
    rows = []
    for case in dataset.queries:
        results = runtime.search_knowledge(case.query, limit=10)
        rows.append(evaluate_results(case.expected, results, ks=(5, 10)))
    metrics = average_metrics(rows)
    typer.echo(f"query_count: {len(dataset.queries)}")
    typer.echo(f"recall@5: {metrics['recall@5']:.4f}")
    typer.echo(f"recall@10: {metrics['recall@10']:.4f}")
    typer.echo(f"mrr: {metrics['mrr']:.4f}")


@app.command()
def status(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to inspect.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to inspect.")] = None,
) -> None:
    """Show the current skeleton status for a knowledge instance."""
    cfg = _resolve_config(name, config) if (name or config) else None
    if cfg is None:
        count = len(discover_configs())
        typer.echo(f"Carsen is installed; {count} configuration(s) discovered. Use 'carsen list' for per-instance counts.")
        return
    meta = instance_metadata(cfg)
    typer.echo(f"Knowledge: {cfg.knowledge.id}")
    typer.echo(f"Status: {meta['status']}")
    typer.echo(f"Transport: {cfg.server.transport}")
    typer.echo(f"Endpoint: {cfg.server.host}:{cfg.server.port}")
    typer.echo(f"Collection: {cfg.storage.collection}")
    typer.echo(f"State directory: {cfg.storage.data_directory}")
    typer.echo(f"Chunks: {meta['chunks']}")
    typer.echo(f"Sources: {meta['sources']}")


def _runtime_stub(command: str, name: str | None, config: Path | None) -> None:
    """Validate instance selection, then explain that runtime work starts later."""

    cfg = _resolve_config(name, config)
    typer.echo(f"{command} for '{cfg.knowledge.id}' is not implemented in Milestone 1; the runtime is absent.")


@app.command()
def index(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to index.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to index.")] = None,
    force: Annotated[bool, typer.Option(help="Reprocess all configured sources when indexing is implemented.")] = False,
    embed: Annotated[bool, typer.Option(help="Embed canonical chunks and upsert the configured Qdrant collection.")] = False,
) -> None:
    """Index configured sources incrementally."""

    from .ingestion.indexer import index_config

    cfg = _resolve_config(name, config)
    with _IndexProgress() as progress:
        report = index_config(cfg, force=force, embed=embed, progress=progress)
    typer.echo(f"Indexed '{cfg.knowledge.id}': new={report.new} unchanged={report.unchanged} changed={report.changed} deleted={report.deleted} chunks={report.chunks}")


@app.command()
def serve(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to serve.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to serve.")] = None,
    transport: Annotated[str | None, typer.Option(help="Override configured transport: stdio or http.")] = None,
) -> None:
    """Serve one knowledge MCP instance."""

    if transport is not None and transport not in {"stdio", "http"}:
        raise typer.BadParameter("transport must be 'stdio' or 'http'")
    from .mcp.server import MCPUnavailableError, run_mcp_server

    cfg = _resolve_config(name, config)
    selected_transport = transport or cfg.server.transport
    typer.echo(f"Serving Carsen instance '{cfg.knowledge.id}' ({cfg.knowledge.name}) via {selected_transport}...", err=True)
    try:
        run_mcp_server(cfg, transport=transport)
    except MCPUnavailableError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("serve-all")
def serve_all(
    names: Annotated[list[str] | None, typer.Argument(help="Registered knowledge instances to serve; defaults to all registered instances.")] = None,
    transport: Annotated[str | None, typer.Option(help="Override configured transport: stdio or http.")] = None,
) -> None:
    """Serve multiple registered knowledge instances sequentially under an external supervisor."""

    if transport is not None and transport not in {"stdio", "http"}:
        raise typer.BadParameter("transport must be 'stdio' or 'http'")
    from .mcp.server import MCPUnavailableError, run_mcp_server

    configs = [_resolve_config(name, None) for name in names] if names else list_configs()
    if not configs:
        typer.echo("No Carsen configurations found.")
        return
    if not names:
        typer.echo(f"Serving all registered Carsen configurations ({len(configs)} found).", err=True)
    for cfg in configs:
        selected_transport = transport or cfg.server.transport
        typer.echo(f"Starting Carsen instance '{cfg.knowledge.id}' ({cfg.knowledge.name}) via {selected_transport}...", err=True)
        try:
            run_mcp_server(cfg, transport=transport)
        except MCPUnavailableError as exc:
            raise typer.BadParameter(str(exc)) from exc


@app.command()
def stop(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to stop.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to stop.")] = None) -> None:
    """Stop a running instance when lifecycle management is implemented."""

    cfg = _resolve_config(name, config)
    typer.echo(f"Stop for '{cfg.knowledge.id}' is managed by the external supervisor; no local process registry is active.")


@app.command()
def reembed(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to re-embed.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to re-embed.")] = None) -> None:
    """Re-embed canonical chunks without reparsing."""

    from .ingestion.indexer import reembed_config

    cfg = _resolve_config(name, config)
    count = reembed_config(cfg)
    typer.echo(f"Re-embedded '{cfg.knowledge.id}': chunks={count}")


@app.command("delete-index")
def delete_index(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance whose index will be deleted.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration whose index will be deleted.")] = None) -> None:
    """Delete an instance-specific local and dense index."""

    from .ingestion.indexer import delete_index_config

    cfg = _resolve_config(name, config)
    existed, vector_error = delete_index_config(cfg)
    typer.echo(f"Deleted index for '{cfg.knowledge.id}': local={existed}")
    if vector_error:
        typer.echo(f"Vector collection clear skipped: {vector_error}")


if __name__ == "__main__":
    app()
