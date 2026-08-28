"""MCP server factory for Carsen knowledge instances."""

from __future__ import annotations

import functools
import importlib
from collections.abc import Callable
from typing import Any

import anyio

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


async def _offload[T](func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking runtime call in a worker thread so one slow query (an
    embedding pass, a reranker) does not block other HTTP clients."""

    return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))


def create_mcp_server(config: CarsenConfig):
    """Create an MCP server exposing tools for one knowledge instance."""
    runtime = InstanceRuntime(config)
    server = _server_class()(f"carsen-{config.knowledge.id}")

    @server.tool()
    async def knowledge_info() -> dict[str, Any]:
        return await _offload(runtime.knowledge_info)

    @server.tool()
    async def search_knowledge(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await _offload(runtime.search_knowledge, query, limit, filters)

    @server.tool()
    async def search_debug(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        return await _offload(runtime.search_debug, query, limit, filters)

    @server.tool()
    async def search_code(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await _offload(runtime.search_code, query, limit, filters)

    @server.tool()
    async def search_documents(query: str, limit: int = 8, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return await _offload(runtime.search_documents, query, limit, filters)

    @server.tool()
    async def find_symbol(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        return await _offload(runtime.find_symbol, symbol, limit)

    @server.tool()
    async def read_source(source_id: str | None = None, chunk_id: str | None = None, previous: int = 0, next: int = 0) -> dict[str, Any]:
        return await _offload(runtime.read_source, source_id, chunk_id, previous, next)

    @server.tool()
    async def get_source_metadata(source_id: str | None = None, chunk_id: str | None = None) -> dict[str, Any]:
        return await _offload(runtime.get_source_metadata, source_id, chunk_id)

    @server.tool()
    async def get_related_sources(source_id: str | None = None, chunk_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return await _offload(runtime.get_related_sources, source_id, chunk_id, limit)

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
