from pathlib import Path

import pytest

from ariadne_mcp.registry import create_config, discover_configs, list_configs


def test_create_no_overwrite(tmp_path: Path) -> None:
    first = create_config("demo", base_dir=tmp_path)
    assert first.exists()
    with pytest.raises(FileExistsError):
        create_config("demo", base_dir=tmp_path)


def test_registry_discovery_and_list_basics(tmp_path: Path) -> None:
    create_config("one", base_dir=tmp_path)
    create_config("two", base_dir=tmp_path)
    paths = discover_configs(base_dir=tmp_path)
    assert [path.name for path in paths] == ["one.yaml", "two.yaml"]
    assert [cfg.name for cfg in list_configs(base_dir=tmp_path)] == ["one", "two"]


def test_create_with_starter_sources(tmp_path: Path) -> None:
    create_config("demo", base_dir=tmp_path, code=[tmp_path / "code"], documents=[tmp_path / "docs"])
    cfg = list_configs(base_dir=tmp_path)[0]
    assert cfg.sources.code[0].path == tmp_path / "code"
    assert cfg.sources.documents[0].path == tmp_path / "docs"
