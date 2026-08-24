from pathlib import Path

import pytest

from carsen_mcp.registry import create_config, discover_configs, list_configs


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


def test_create_self_docs_config_from_source_tree(tmp_path: Path) -> None:
    source = tmp_path / "carsen"
    docs = source / "docs"
    package = source / "src" / "carsen_mcp"
    docs.mkdir(parents=True)
    package.mkdir(parents=True)

    from carsen_mcp.registry import create_self_docs_config

    config_path = create_self_docs_config(source=source, base_dir=tmp_path)
    assert config_path == tmp_path / "carsen-self.yaml"

    cfg = list_configs(base_dir=tmp_path)[0]
    assert cfg.knowledge.id == "carsen-self"
    assert cfg.knowledge.name == "Carsen self-reference"
    assert "Carsen documentation and source package" in cfg.knowledge.description
    assert cfg.sources.documents[0].path == docs
    assert cfg.sources.code[0].path == package
    assert cfg.storage.collection == "kb_carsen_self"
    assert cfg.server.transport == "stdio"


def test_create_self_docs_config_from_current_source_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "carsen"
    docs = source / "docs"
    package = source / "src" / "carsen_mcp"
    docs.mkdir(parents=True)
    package.mkdir(parents=True)
    monkeypatch.chdir(source)

    from carsen_mcp.registry import create_self_docs_config

    create_self_docs_config(base_dir=tmp_path)

    cfg = list_configs(base_dir=tmp_path)[0]
    assert cfg.sources.documents[0].path == docs
    assert cfg.sources.code[0].path == package


def test_create_self_docs_config_with_explicit_docs_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "published-docs"
    docs.mkdir()
    monkeypatch.chdir(tmp_path)

    from carsen_mcp.registry import create_self_docs_config

    create_self_docs_config(name="docs-help", docs_path=docs, base_dir=tmp_path)

    cfg = list_configs(base_dir=tmp_path)[0]
    assert cfg.knowledge.id == "docs-help"
    assert cfg.sources.documents[0].path == docs
    assert cfg.sources.code == []


def test_create_self_docs_config_fails_when_docs_are_missing(tmp_path: Path) -> None:
    source = tmp_path / "carsen"
    source.mkdir()

    from carsen_mcp.registry import create_self_docs_config
    with pytest.raises(FileNotFoundError, match="Could not find Carsen documentation directory for self-reference"):
        create_self_docs_config(source=source, base_dir=tmp_path)


def test_create_self_docs_config_requires_overwrite(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()

    from carsen_mcp.registry import create_self_docs_config
    create_self_docs_config(docs_path=docs, base_dir=tmp_path)

    with pytest.raises(FileExistsError, match="already exists"):
        create_self_docs_config(docs_path=docs, base_dir=tmp_path)

    create_self_docs_config(docs_path=docs, overwrite=True, base_dir=tmp_path)
