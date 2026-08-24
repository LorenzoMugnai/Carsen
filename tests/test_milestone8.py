from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from carsen_mcp.chunks.model import Chunk
from carsen_mcp.chunks.store import ChunkStore
from carsen_mcp.cli import app
from carsen_mcp.config import CarsenConfig, KnowledgeConfig, ServerConfig, StorageConfig, dump_config
from carsen_mcp.mcp.runtime import InstanceRuntime
from carsen_mcp.registry import instance_metadata


def make_config(root: Path, name: str, port: int) -> CarsenConfig:
    return CarsenConfig(
        knowledge=KnowledgeConfig(id=name),
        storage=StorageConfig(data_directory=root / "data" / name),
        server=ServerConfig(transport="http", port=port),
    )


def write_registered(root: Path, config: CarsenConfig) -> Path:
    path = root / "registry" / f"{config.knowledge.id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_config(config), encoding="utf-8")
    return path


def store_chunk(config: CarsenConfig, text: str, symbol: str) -> Chunk:
    assert config.storage.data_directory is not None
    chunk = Chunk(
        config.knowledge.id,
        f"src/{config.knowledge.id}.py",
        "function",
        symbol,
        1,
        3,
        text,
        metadata={"source_type": "code", "source_path": f"src/{config.knowledge.id}.py", "repository": config.knowledge.id},
    )
    ChunkStore(config.storage.data_directory).replace_file_chunks(chunk.source_path, [chunk])
    return chunk


def test_alpha_beta_runtime_isolation_and_ids(tmp_path: Path) -> None:
    alpha = make_config(tmp_path, "alpha", 9101)
    beta = make_config(tmp_path, "beta", 9102)
    alpha_chunk = store_chunk(alpha, "CALIBRATION_CONSTANT = 42", "alpha_calibration")
    beta_chunk = store_chunk(beta, "CALIBRATION_CONSTANT = 91", "beta_calibration")

    alpha_hits = InstanceRuntime(alpha).search_knowledge("42")
    beta_hits = InstanceRuntime(beta).search_knowledge("91")

    assert alpha_hits and "42" in alpha_hits[0]["text"]
    assert InstanceRuntime(alpha).search_knowledge("91") == []
    assert beta_hits and "91" in beta_hits[0]["text"]
    assert alpha_chunk.chunk_id != beta_chunk.chunk_id
    assert alpha.storage.data_directory != beta.storage.data_directory
    assert alpha_chunk.source_path != beta_chunk.source_path


def test_instance_metadata_counts_chunks_sources(tmp_path: Path) -> None:
    config = make_config(tmp_path, "alpha", 9101)
    store_chunk(config, "CALIBRATION_CONSTANT = 42", "alpha_calibration")
    meta = instance_metadata(config)
    assert meta["status"] == "runnable"
    assert meta["chunks"] == 1
    assert meta["sources"] == 1
    assert meta["port"] == 9101


def test_cli_list_and_status_multiple_configs(tmp_path: Path, monkeypatch) -> None:
    alpha = make_config(tmp_path, "alpha", 9101)
    beta = make_config(tmp_path, "beta", 9102)
    store_chunk(alpha, "CALIBRATION_CONSTANT = 42", "alpha_calibration")
    store_chunk(beta, "CALIBRATION_CONSTANT = 91", "beta_calibration")
    write_registered(tmp_path, alpha)
    write_registered(tmp_path, beta)
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(tmp_path / "registry"))

    runner = CliRunner()
    listed = runner.invoke(app, ["list"])
    assert listed.exit_code == 0
    assert "alpha\trunnable\t9101\t1\t1" in listed.stdout
    assert "beta\trunnable\t9102\t1\t1" in listed.stdout

    status = runner.invoke(app, ["status", "alpha"])
    assert status.exit_code == 0
    assert "Status: runnable" in status.stdout
    assert "Chunks: 1" in status.stdout


def test_cli_serve_all_monkeypatched_transport(tmp_path: Path, monkeypatch) -> None:
    alpha = make_config(tmp_path, "alpha", 9101)
    beta = make_config(tmp_path, "beta", 9102)
    write_registered(tmp_path, alpha)
    write_registered(tmp_path, beta)
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(tmp_path / "registry"))
    calls: list[tuple[str, str | None, int]] = []

    def fake_run(config: CarsenConfig, transport: str | None = None) -> None:
        calls.append((config.knowledge.id, transport, config.server.port))

    monkeypatch.setattr("carsen_mcp.mcp.server.run_mcp_server", fake_run)
    result = CliRunner().invoke(app, ["serve-all", "alpha", "beta", "--transport", "http"])

    assert result.exit_code == 0
    assert calls == [("alpha", "http", 9101), ("beta", "http", 9102)]


def test_stop_reports_external_supervisor(tmp_path: Path, monkeypatch) -> None:
    alpha = make_config(tmp_path, "alpha", 9101)
    write_registered(tmp_path, alpha)
    monkeypatch.setenv("CARSEN_CONFIG_DIR", str(tmp_path / "registry"))
    result = CliRunner().invoke(app, ["stop", "alpha"])
    assert result.exit_code == 0
    assert "external supervisor" in result.stdout
