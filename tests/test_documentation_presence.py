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
    "docs/llm-integration.md",
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


def test_contributing_documentation_is_present_and_linked() -> None:
    root_guide = ROOT / "CONTRIBUTING.md"
    docs_guide = ROOT / "docs" / "contributing.md"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    assert root_guide.exists()
    assert docs_guide.exists()

    root_text = root_guide.read_text(encoding="utf-8")
    docs_text = docs_guide.read_text(encoding="utf-8")
    required_phrases = [
        "uv pip install -e '.[dev]'",
        "python -m ruff check .",
        "PYTHONPATH=src python -m mypy",
        "python -m pytest",
        "Pull request checklist",
        "Release checklist",
        "tag-based versioning",
    ]
    for phrase in required_phrases:
        assert phrase in root_text
    for phrase in ["Carsen", "quality gates", "tag-based versioning", "Release checklist"]:
        assert phrase in docs_text

    assert "CONTRIBUTING.md" in readme
    assert "contributing.md" in mkdocs


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


def test_llm_integration_and_init_self_are_documented() -> None:
    llm = (ROOT / "docs" / "llm-integration.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
    cli = (ROOT / "docs" / "cli-reference.md").read_text(encoding="utf-8")
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

    for text in [llm, quickstart, cli]:
        assert "carsen init-self" in text
        assert "carsen-self" in text
        assert "LLM" in text
        assert "MCP" in text
    assert "llm-integration.md" in mkdocs


def test_cli_reference_init_self_documents_checkout_root_source() -> None:
    text = (ROOT / "docs" / "cli-reference.md").read_text(encoding="utf-8")

    assert "--source ./src/carsen_mcp" not in text
    assert "carsen init-self --docs-path ./docs --source . --name carsen-self" in text
    assert "Carsen checkout root" in text
    assert "PATH/src/carsen_mcp" in text


def test_llm_integration_documents_retrieval_not_generation_framing() -> None:
    text = (ROOT / "docs" / "llm-integration.md").read_text(encoding="utf-8")

    assert "Carsen is not an LLM" in text
    assert "retrieves cited context" in text
    assert "LLM remains replaceable" in text
    assert "local-first" in text
    assert (
        "does not require a specific LLM provider" in text
        or "without making Carsen depend on any provider" in text
    )


def test_beginner_llm_docs_use_english_and_current_project_names() -> None:
    required_phrases_by_page = {
        ROOT / "docs" / "llm-integration.md": [
            "Carsen is not an LLM",
            "retrieves cited context",
            "LLM client",
            "local-first",
            "MCP",
            "provider",
        ],
        ROOT / "docs" / "quickstart.md": [
            "Carsen",
            "retrieves cited context",
            "LLM client",
            "local-first",
            "MCP",
            "provider",
        ],
        ROOT / "docs" / "cli-reference.md": [
            "Carsen",
            "carsen init-self",
            "carsen-self",
            "MCP",
        ],
    }
    stale_names = ["Ariadne", "ariadne", "ariadne_mcp"]

    for path, required_phrases in required_phrases_by_page.items():
        text = path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            assert phrase in text, f"Missing required English phrase {phrase!r} in {path}"
        for stale_name in stale_names:
            assert stale_name not in text, f"Stale project name {stale_name!r} in {path}"


def test_mkdocs_uses_brand_assets_and_custom_stylesheet() -> None:
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "logo: assets/logo_character.png" in text
    assert "favicon: assets/logo_character.png" in text
    assert "stylesheets/extra.css" in text
    assert (ROOT / "docs" / "assets" / "logo.png").exists()
    assert (ROOT / "docs" / "assets" / "logo_character.png").exists()
    assert (ROOT / "docs" / "assets" / "logo_text.png").exists()
    assert (ROOT / "docs" / "stylesheets" / "extra.css").exists()
