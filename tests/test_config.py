from pathlib import Path

import pytest
from pydantic import ValidationError

from ariadne_mcp.config import load_config


def write_config(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_config_validation(tmp_path: Path) -> None:
    path = write_config(tmp_path / "valid.yaml", "knowledge:\n  id: demo\nstorage:\n  data_directory: /tmp/demo\nserver:\n  port: 9000\n")
    cfg = load_config(path)
    assert cfg.knowledge.id == "demo"
    assert cfg.server.port == 9000
    assert cfg.storage.collection == "kb_demo"


def test_env_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIADNE_TEST_DATA", str(tmp_path / "data"))
    path = write_config(tmp_path / "env.yaml", "knowledge:\n  id: env\nstorage:\n  data_directory: ${ARIADNE_TEST_DATA}/project\n")
    assert load_config(path).storage.data_directory == tmp_path / "data" / "project"


def test_relative_paths_resolve_against_config(tmp_path: Path) -> None:
    path = write_config(tmp_path / "rel.yaml", "knowledge:\n  id: rel\nstorage:\n  data_directory: data/rel\nsources:\n  code:\n    - path: src\n")
    cfg = load_config(path)
    assert cfg.storage.data_directory == tmp_path / "data" / "rel"
    assert cfg.sources.code[0].path == tmp_path / "src"


@pytest.mark.parametrize(
    "body",
    [
        "knowledge:\n  id: bad\nserver:\n  port: 0\n",
        "knowledge:\n  id: bad/name\n",
        "knowledge:\n  id: bad\nserver:\n  transport: tcp\n",
        "knowledge:\n  id: bad\nretrieval:\n  fusion: weighted\n",
    ],
)
def test_invalid_ports_settings(tmp_path: Path, body: str) -> None:
    with pytest.raises(ValidationError):
        load_config(write_config(tmp_path / "bad.yaml", body))
