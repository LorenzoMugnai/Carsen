from pathlib import Path

import anyio
from mcp.client import Client

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, StorageConfig
from carsen_mcp.mcp.server import create_mcp_server


def test_mcp_client_calls_instance_tools_in_process(tmp_path: Path) -> None:
    async def scenario() -> None:
        config = CarsenConfig(
            knowledge=KnowledgeConfig(id="client_smoke"),
            storage=StorageConfig(data_directory=tmp_path / "data"),
        )
        chunk = Chunk(
            "client_smoke",
            "src/demo.py",
            "function",
            "apply_read_noise",
            10,
            14,
            "def apply_read_noise(signal):\n    return signal",
            metadata={"source_type": "code", "source_path": "src/demo.py"},
        )
        assert config.storage.data_directory is not None
        ChunkStore(config.storage.data_directory).replace_file_chunks(chunk.source_path, [chunk])

        async with Client(create_mcp_server(config), raise_exceptions=True) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} >= {"knowledge_info", "find_symbol", "read_source"}

            info = await client.call_tool("knowledge_info", {})
            assert info.structured_content["knowledge_id"] == "client_smoke"
            assert info.structured_content["chunk_count"] == 1

            symbol = await client.call_tool("find_symbol", {"symbol": "apply_read_noise"})
            result = symbol.structured_content["result"][0]
            assert result["chunk_id"] == chunk.chunk_id
            assert result["citation"] == "src/demo.py:10-14"

            source = await client.call_tool("read_source", {"chunk_id": chunk.chunk_id})
            assert source.structured_content["found"] is True
            assert source.structured_content["chunk"]["chunk_id"] == chunk.chunk_id

    anyio.run(scenario)
