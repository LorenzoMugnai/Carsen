"""Command line interface for Carsen."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from types import TracebackType
from typing import Annotated, Any, NoReturn

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

from .config import CarsenConfig, dump_config, load_config
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
        elif event == "file_parse_start" and self.parse_task is not None:
            path = Path(payload["path"])
            self._progress.update(
                self.parse_task,
                completed=payload["index"] - 1,
                description=f"Parsing/writing files ({path.name})",
            )
            self.console.print(f"Parsing {payload['index']}/{payload['total']}: {payload['path']}")
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
        elif event == "file_failed":
            if self.parse_task is not None:
                self._progress.update(self.parse_task, completed=payload["index"])
            self.console.print(
                f"Failed to parse {payload['path']}: {payload['error']}",
                style="yellow",
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
        elif event == "dense_failed":
            self.console.print(f"Dense vector indexing skipped: {payload['error']}", style="yellow")


def _preview(text: str, length: int = 120) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= length else f"{collapsed[: length - 1]}…"


def _resolve_config(name: str | None, config: Path | None) -> CarsenConfig:
    """Resolve an explicit path, a local config, or a registered knowledge name."""

    if config is not None:
        return load_config(config)
    if name is None:
        raise typer.BadParameter("provide a registered NAME or --config PATH")
    from .registry import config_path_for

    local_path = Path(name).expanduser()
    if local_path.is_file():
        return load_config(local_path)

    local_config = Path.cwd() / f"{name}.yaml"
    if local_config.is_file():
        return load_config(local_config)

    path = config_path_for(name)
    if not path.exists():
        raise typer.BadParameter(
            f"configuration '{name}' was not found in the current directory ({local_config}) or at {path}"
        )
    return load_config(path)


def _resolve_config_path(name: str | None, config: Path | None) -> Path | None:
    """Resolve the YAML path for commands that need to persist config changes."""

    if config is not None:
        return config.expanduser()
    if name is None:
        return None
    from .registry import config_path_for

    local_path = Path(name).expanduser()
    if local_path.is_file():
        return local_path

    local_config = Path.cwd() / f"{name}.yaml"
    if local_config.is_file():
        return local_config
    path = config_path_for(name)
    return path if path.exists() else None


def _embedding_failure(exc: Exception) -> NoReturn:
    typer.echo(
        "Embedding failed: "
        f"{exc}\n"
        "Try reducing the embedding batch size, using a smaller embedding model, "
        "running index without --embed, or checking available model memory.",
        err=True,
    )
    raise typer.Exit(1) from exc


def _compact_error(exc: Exception) -> str:
    messages: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        text = str(current)
        if text and text not in messages:
            messages.append(text)
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return ": ".join(messages) or exc.__class__.__name__


def _vector_failure(config: CarsenConfig, exc: Exception) -> NoReturn:
    typer.echo(
        "Qdrant/vector store connection failed: "
        f"{_compact_error(exc)}\n"
        f"Configured Qdrant URL: {config.storage.qdrant_url}\n"
        "Start Qdrant and retry, or update storage.qdrant_url to a reachable Qdrant service.",
        err=True,
    )
    raise typer.Exit(1) from exc


def _dense_warning(config: CarsenConfig, error: str) -> None:
    qdrant_target = (
        f"embedded path {config.storage.qdrant_path}"
        if config.storage.qdrant_path is not None
        else f"Qdrant URL {config.storage.qdrant_url}"
    )
    typer.echo(
        "Warning: dense vector indexing failed and was skipped. "
        f"Sparse/exact MCP search remains available. Dense error: {error}. "
        f"Vector store target: {qdrant_target}.",
        err=True,
    )


_NOISY_FILE_CATEGORIES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("binary/data", (".h5", ".fits", ".npy", ".npz", ".pkl", ".bin"), ()),
    ("archives", (".zip", ".tar", ".gz", ".tgz", ".whl"), ()),
    ("logs/cache/build", (".cache",), ("htmlcov", "_build", ".ipynb_checkpoints")),
    ("logs", (".log",), ()),
    ("images/media", (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".avi"), ()),
)


def _format_bytes(size: int) -> str:
    return f"{size} B"


def _review_noisy_files(cfg: CarsenConfig, config_path: Path | None, yes: bool) -> None:
    """Warn about common noisy files and optionally persist selected ignores."""

    from .ingestion.discovery import discover_files

    examples: list[tuple[int, str, tuple[str, ...], tuple[str, ...], int, int, int, list[str]]] = []
    ignored_exts = set(cfg.indexing.ignored_extensions)
    ignored_dirs = set(cfg.indexing.ignored_directories)
    for label, extensions, directories in _NOISY_FILE_CATEGORIES:
        category_exts = tuple(ext for ext in extensions if ext not in ignored_exts)
        category_dirs = tuple(directory for directory in directories if directory not in ignored_dirs)
        if not category_exts and not category_dirs:
            continue
        names: list[str] = []
        file_count = 0
        directory_count = 0
        total_bytes = 0
        for source in [*cfg.sources.code, *cfg.sources.documents]:
            if source.path is None or not source.path.exists():
                continue
            if category_exts:
                for path in discover_files(source.path, cfg.indexing):
                    if path.suffix not in category_exts:
                        continue
                    file_count += 1
                    total_bytes += path.stat().st_size
                    if path.name not in names and len(names) < 3:
                        names.append(path.name)
            if category_dirs:
                for path in source.path.rglob("*"):
                    if not path.is_dir() or path.name not in category_dirs:
                        continue
                    directory_count += 1
                    if path.name not in names and len(names) < 3:
                        names.append(path.name)
        if file_count or directory_count:
            examples.append((len(examples) + 1, label, category_exts, category_dirs, file_count, directory_count, total_bytes, names))

    if not examples:
        return

    typer.echo("Potential indexing noise:", err=True)
    for index, label, extensions, _directories, file_count, directory_count, total_bytes, names in examples:
        parts: list[str] = []
        if file_count:
            parts.append(f"{file_count} file(s)")
            parts.append(_format_bytes(total_bytes))
        if directory_count:
            parts.append(f"{directory_count} director{'y' if directory_count == 1 else 'ies'}")
        if extensions:
            parts.append(f"extensions: {', '.join(extensions)}")
        if names:
            parts.append(f"examples: {', '.join(names)}")
        typer.echo(f"{index}. {label}: {'; '.join(parts)}", err=True)

    if yes:
        typer.echo("Use interactive indexing without --yes to update ignored_extensions.", err=True)
        return

    selected = typer.prompt("Enter category numbers to ignore, comma-separated (blank to skip)", default="", show_default=False, err=True)
    selected_numbers = {int(part.strip()) for part in selected.replace(",", " ").split() if part.strip().isdigit()}
    if not selected_numbers:
        return

    added = False
    for index, _label, extensions, directories, _file_count, _directory_count, _total_bytes, _names in examples:
        if index not in selected_numbers:
            continue
        for extension in extensions:
            if extension not in cfg.indexing.ignored_extensions:
                cfg.indexing.ignored_extensions.append(extension)
                added = True
        for directory in directories:
            if directory not in cfg.indexing.ignored_directories:
                cfg.indexing.ignored_directories.append(directory)
                added = True
    if added and config_path is not None:
        config_path.write_text(dump_config(cfg), encoding="utf-8")


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
    yes: Annotated[bool, typer.Option("--yes", help="Skip interactive noisy-file ignore prompts.")] = False,
) -> None:
    """Index configured sources incrementally."""

    from .ingestion.indexer import EmbeddingIndexError, VectorIndexError, index_config

    cfg = _resolve_config(name, config)
    _review_noisy_files(cfg, _resolve_config_path(name, config), yes)
    try:
        with _IndexProgress() as progress:
            report = index_config(cfg, force=force, embed=embed, progress=progress)
    except VectorIndexError as exc:
        _vector_failure(cfg, exc)
    except EmbeddingIndexError as exc:
        if embed:
            _embedding_failure(exc)
        raise
    typer.echo(f"Indexed '{cfg.knowledge.id}': new={report.new} unchanged={report.unchanged} changed={report.changed} deleted={report.deleted} chunks={report.chunks}")
    if report.dense_error:
        _dense_warning(cfg, report.dense_error)


@app.command()
def watch(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to watch and index.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to watch.")] = None,
) -> None:
    """Watch configured sources and index after filesystem changes."""

    from .ingestion.watcher import watch_config

    cfg = _resolve_config(name, config)
    watch_config(cfg, log=lambda message: typer.echo(message, err=True))


@app.command()
def serve(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to serve.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to serve.")] = None,
    transport: Annotated[str | None, typer.Option(help="Override configured transport: stdio or http.")] = None,
    watch_sources: Annotated[
        bool | None,
        typer.Option("--watch/--no-watch", help="Override indexing.watch while serving."),
    ] = None,
) -> None:
    """Serve one knowledge MCP instance."""

    if transport is not None and transport not in {"stdio", "http"}:
        raise typer.BadParameter("transport must be 'stdio' or 'http'")
    from .mcp.server import MCPUnavailableError, run_mcp_server

    cfg = _resolve_config(name, config)
    selected_transport = transport or cfg.server.transport
    effective_watch = cfg.indexing.watch if watch_sources is None else watch_sources
    stop_event = None
    if effective_watch:
        from .ingestion.watcher import start_watch_thread

        _thread, stop_event = start_watch_thread(cfg, log=lambda message: typer.echo(message, err=True))
    typer.echo(f"Serving Carsen instance '{cfg.knowledge.id}' ({cfg.knowledge.name}) via {selected_transport}...", err=True)
    try:
        run_mcp_server(cfg, transport=transport)
    except MCPUnavailableError as exc:
        raise typer.BadParameter(str(exc)) from exc
    finally:
        if stop_event is not None:
            stop_event.set()


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

    from .ingestion.indexer import EmbeddingIndexError, VectorIndexError, reembed_config

    cfg = _resolve_config(name, config)
    try:
        count = reembed_config(cfg)
    except VectorIndexError as exc:
        _vector_failure(cfg, exc)
    except EmbeddingIndexError as exc:
        _embedding_failure(exc)
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
