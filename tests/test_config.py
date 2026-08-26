from pathlib import Path

import pytest
from pydantic import ValidationError

from carsen_mcp.config import CarsenConfig, KnowledgeConfig, load_config


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
    monkeypatch.setenv("CARSEN_TEST_DATA", str(tmp_path / "data"))
    path = write_config(tmp_path / "env.yaml", "knowledge:\n  id: env\nstorage:\n  data_directory: ${CARSEN_TEST_DATA}/project\n")
    assert load_config(path).storage.data_directory == tmp_path / "data" / "project"


def test_relative_paths_resolve_against_config(tmp_path: Path) -> None:
    path = write_config(tmp_path / "rel.yaml", "knowledge:\n  id: rel\nstorage:\n  data_directory: data/rel\n  qdrant_path: data/rel/qdrant\nsources:\n  code:\n    - path: src\n")
    cfg = load_config(path)
    assert cfg.storage.data_directory == tmp_path / "data" / "rel"
    assert cfg.storage.qdrant_path == tmp_path / "data" / "rel" / "qdrant"
    assert cfg.sources.code[0].path == tmp_path / "src"


def test_qdrant_path_expands_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CARSEN_QDRANT", str(tmp_path / "qdrant"))
    path = write_config(tmp_path / "qdrant.yaml", "knowledge:\n  id: q\nstorage:\n  qdrant_path: ${CARSEN_QDRANT}\n")

    assert load_config(path).storage.qdrant_path == tmp_path / "qdrant"


def test_default_document_parsing_is_fast_pdf_mode() -> None:
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="docs"))

    assert cfg.parsing.documents.ocr is False
    assert cfg.parsing.documents.table_structure is False
    assert cfg.parsing.documents.force_backend_text is True


def test_default_watch_indexing_options() -> None:
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="watch"))

    assert cfg.indexing.watch is False
    assert cfg.indexing.watch_debounce_seconds == 10.0
    assert cfg.indexing.watch_embed is False


def test_default_embedding_memory_safety_options() -> None:
    cfg = CarsenConfig(knowledge=KnowledgeConfig(id="embed"))

    assert cfg.models.embedding.batch_size == 8
    assert cfg.models.embedding.max_seq_length == 1024


def test_embedding_memory_safety_options_load_from_yaml(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "embed.yaml",
        """
knowledge:
  id: embed
models:
  embedding:
    provider: sentence_transformers
    model: test/model
    dimensions: 3
    batch_size: 2
    max_seq_length: 128
""",
    )

    cfg = load_config(path)

    assert cfg.models.embedding.batch_size == 2
    assert cfg.models.embedding.max_seq_length == 128


def test_remote_source_fields_load_from_yaml(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "remote.yaml",
        """
knowledge:
  id: remote
sources:
  code:
    - repo_url: https://github.com/example/project.git
      ref: main
      subpath: src
      repository_name: example/project
""",
    )

    source = load_config(path).sources.code[0]

    assert source.path is None
    assert source.repo_url == "https://github.com/example/project.git"
    assert source.ref == "main"
    assert source.subpath == Path("src")
    assert source.repository_name == "example/project"


def test_document_parsing_options_load_from_yaml(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "parse.yaml",
        """
knowledge:
  id: docs
parsing:
  documents:
    ocr: true
    table_structure: true
    force_backend_text: false
""",
    )

    cfg = load_config(path)

    assert cfg.parsing.documents.ocr is True
    assert cfg.parsing.documents.table_structure is True
    assert cfg.parsing.documents.force_backend_text is False


@pytest.mark.parametrize(
    "body",
    [
        "knowledge:\n  id: bad\nserver:\n  port: 0\n",
        "knowledge:\n  id: bad/name\n",
        "knowledge:\n  id: bad\nserver:\n  transport: tcp\n",
        "knowledge:\n  id: bad\nretrieval:\n  fusion: weighted\n",
        "knowledge:\n  id: bad\nindexing:\n  watch_debounce_seconds: 0\n",
        "knowledge:\n  id: bad\nmodels:\n  embedding:\n    model: fake\n    batch_size: 0\n",
        "knowledge:\n  id: bad\nmodels:\n  embedding:\n    model: fake\n    max_seq_length: 0\n",
    ],
)
def test_invalid_ports_settings(tmp_path: Path, body: str) -> None:
    with pytest.raises(ValidationError):
        load_config(write_config(tmp_path / "bad.yaml", body))
