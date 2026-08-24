from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DOCS = {
    "README.md",
    "CHANGELOG.md",
    "docs/index.md",
    "docs/architecture.md",
    "docs/configuration.md",
    "docs/knowledge-instances.md",
    "docs/indexing.md",
    "docs/retrieval.md",
    "docs/citations.md",
    "docs/mcp.md",
    "docs/deployment.md",
    "docs/security.md",
    "docs/development.md",
    "docs/testing.md",
    "docs/extending.md",
    "docs/troubleshooting.md",
    "docs/adr/0001-separate-knowledge-instances.md",
    "docs/adr/0002-qdrant-per-instance-collections.md",
    "docs/adr/0003-canonical-chunk-store.md",
    "docs/adr/0004-hybrid-dense-sparse-retrieval.md",
    "docs/adr/0005-metadata-backed-citations.md",
    "docs/adr/0006-generative-llm-independence.md",
}


def test_required_documentation_files_exist_and_are_non_empty() -> None:
    for relative_path in REQUIRED_DOCS:
        path = ROOT / relative_path
        assert path.exists(), relative_path
        assert path.read_text(encoding="utf-8").strip(), relative_path


def test_architecture_and_retrieval_docs_include_mermaid_diagrams() -> None:
    assert "```mermaid" in (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "```mermaid" in (ROOT / "docs" / "retrieval.md").read_text(encoding="utf-8")


def test_mkdocs_site_configuration_exists() -> None:
    config = ROOT / "mkdocs.yml"

    assert config.exists()
    text = config.read_text(encoding="utf-8")
    assert "site_name: Carsen" in text
    assert "theme:" in text
    assert "material" in text
    assert "quickstart.md" in text
    assert "concepts/qdrant.md" in text


def test_didactic_documentation_pages_exist() -> None:
    required = [
        ROOT / "docs/quickstart.md",
        ROOT / "docs/academic-users.md",
        ROOT / "docs/concepts.md",
        ROOT / "docs/concepts/mcp.md",
        ROOT / "docs/concepts/qdrant.md",
        ROOT / "docs/concepts/embeddings.md",
        ROOT / "docs/concepts/chunks-and-citations.md",
    ]

    for path in required:
        assert path.exists(), f"Missing documentation page: {path}"


def test_didactic_documentation_includes_diagrams() -> None:
    diagram_pages = [
        ROOT / "docs/quickstart.md",
        ROOT / "docs/concepts/mcp.md",
        ROOT / "docs/concepts/qdrant.md",
        ROOT / "docs/concepts/embeddings.md",
        ROOT / "docs/concepts/chunks-and-citations.md",
    ]

    for path in diagram_pages:
        text = path.read_text(encoding="utf-8")
        assert "```mermaid" in text, f"Missing Mermaid diagram in {path}"
