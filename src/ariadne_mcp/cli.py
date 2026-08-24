"""Command line interface for Ariadne."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .config import AriadneConfig, load_config
from .registry import create_config, discover_configs, instance_metadata, list_configs

app = typer.Typer(help="Ariadne Knowledge Engine: manage isolated knowledge MCP instances.")


def _resolve_config(name: str | None, config: Path | None) -> AriadneConfig:
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
    """Create a starter YAML configuration in the local Ariadne registry."""
    try:
        path = create_config(name, overwrite=overwrite, code=code, documents=documents)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Created configuration: {path}")


@app.command("list")
def list_command(config: Annotated[Path | None, typer.Option("--config", help="Include an explicit YAML configuration.")] = None) -> None:
    """List discoverable Ariadne knowledge-instance configurations."""
    paths = discover_configs(config)
    if not paths:
        typer.echo("No Ariadne configurations found.")
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
def status(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to inspect.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to inspect.")] = None,
) -> None:
    """Show the current skeleton status for a knowledge instance."""
    cfg = _resolve_config(name, config) if (name or config) else None
    if cfg is None:
        count = len(discover_configs())
        typer.echo(f"Ariadne is installed; {count} configuration(s) discovered. Use 'ariadne list' for per-instance counts.")
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
    report = index_config(cfg, force=force, embed=embed)
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
        typer.echo("No Ariadne configurations found.")
        return
    for cfg in configs:
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
