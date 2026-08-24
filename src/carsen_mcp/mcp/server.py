"""MCP server factory for Carsen knowledge instances."""

from __future__ import annotations

import importlib
from typing import Any

from carsen_mcp.config import CarsenConfig

from .runtime import InstanceRuntime


class MCPUnavailableError(RuntimeError):
    """Raised when the optional MCP SDK is unavailable."""


def _server_class():
    try:
        module = importlib.import_module("mcp.server.mcpserver")
    except Exception as exc:
        raise MCPUnavailableError("The 'mcp' package is required to serve Carsen over MCP") from exc
    return module.MCPServer


def create_mcp_server(config: CarsenConfig):
    """Create an MCP server exposing tools for one knowledge instance."""
    runtime = InstanceRuntime(config)
    server = _server_class()(f"carsen-{config.knowledge.id}")

    @server.tool()
    def knowledge_info() -> dict[str, Any]:
        return runtime.knowledge_info()

    @server.tool()
    def search_knowledge(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return runtime.search_knowledge(query, limit, filters)

    @server.tool()
    def search_code(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return runtime.search_code(query, limit, filters)

    @server.tool()
    def search_documents(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return runtime.search_documents(query, limit, filters)

    @server.tool()
    def find_symbol(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        return runtime.find_symbol(symbol, limit)

    @server.tool()
    def read_source(source_id: str | None = None, chunk_id: str | None = None, previous: int = 0, next: int = 0) -> dict[str, Any]:
        return runtime.read_source(source_id, chunk_id, previous, next)

    @server.tool()
    def get_source_metadata(source_id: str | None = None, chunk_id: str | None = None) -> dict[str, Any]:
        return runtime.get_source_metadata(source_id, chunk_id)

    @server.tool()
    def get_related_sources(source_id: str | None = None, chunk_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return runtime.get_related_sources(source_id, chunk_id, limit)

    return server


def run_mcp_server(config: CarsenConfig, transport: str | None = None) -> None:
    server = create_mcp_server(config)
    selected = transport or config.server.transport
    if selected == "stdio":
        server.run("stdio")
        return
    if selected == "http":
        server.run("streamable-http", host=config.server.host, port=config.server.port, streamable_http_path="/mcp")
        return
    raise ValueError("transport must be 'stdio' or 'http'")
