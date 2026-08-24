"""Command line interface for Ariadne."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .config import AriadneConfig, load_config
from .registry import create_config, discover_configs, list_configs

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
    typer.echo("NAME\tSTATUS\tPORT\tCOLLECTION\tDATA DIRECTORY")
    for cfg in list_configs(config):
        typer.echo(f"{cfg.knowledge.id}\tstopped\t{cfg.server.port}\t{cfg.storage.collection}\t{cfg.storage.data_directory}")


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
        typer.echo(f"Ariadne is installed; {count} configuration(s) discovered. Runtime commands are not active yet.")
        return
    typer.echo(f"Knowledge: {cfg.knowledge.id}")
    typer.echo(f"Status: stopped")
    typer.echo(f"Transport: {cfg.server.transport}")
    typer.echo(f"Endpoint: {cfg.server.host}:{cfg.server.port}")
    typer.echo(f"Collection: {cfg.storage.collection}")
    typer.echo(f"State directory: {cfg.storage.data_directory}")


def _runtime_stub(command: str, name: str | None, config: Path | None) -> None:
    """Validate instance selection, then explain that runtime work starts later."""

    cfg = _resolve_config(name, config)
    typer.echo(f"{command} for '{cfg.knowledge.id}' is not implemented in Milestone 1; the runtime is absent.")


@app.command()
def index(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to index.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to index.")] = None,
    force: Annotated[bool, typer.Option(help="Reprocess all configured sources when indexing is implemented.")] = False,
) -> None:
    """Index configured sources incrementally."""

    from .ingestion.indexer import index_config

    cfg = _resolve_config(name, config)
    report = index_config(cfg, force=force)
    typer.echo(f"Indexed '{cfg.knowledge.id}': new={report.new} unchanged={report.unchanged} changed={report.changed} deleted={report.deleted} chunks={report.chunks}")


@app.command()
def serve(
    name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to serve.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to serve.")] = None,
    transport: Annotated[str | None, typer.Option(help="Override configured transport: stdio or http.")] = None,
) -> None:
    """Serve one knowledge MCP instance; currently a Milestone 1 stub."""

    if transport is not None and transport not in {"stdio", "http"}:
        raise typer.BadParameter("transport must be 'stdio' or 'http'")
    _runtime_stub("Serve", name, config)


@app.command()
def stop(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to stop.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to stop.")] = None) -> None:
    """Stop a running instance when lifecycle management is implemented."""

    _runtime_stub("Stop", name, config)


@app.command()
def reembed(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance to re-embed.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration to re-embed.")] = None) -> None:
    """Re-embed canonical chunks without reparsing when implemented."""

    _runtime_stub("Re-embed", name, config)


@app.command("delete-index")
def delete_index(name: Annotated[str | None, typer.Argument(help="Registered knowledge instance whose index will be deleted.")] = None, config: Annotated[Path | None, typer.Option("--config", help="Explicit YAML configuration whose index will be deleted.")] = None) -> None:
    """Delete an instance-specific index when storage is implemented."""

    _runtime_stub("Delete index", name, config)


if __name__ == "__main__":
    app()
