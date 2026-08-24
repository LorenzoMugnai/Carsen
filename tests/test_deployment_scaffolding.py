from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dockerfile_and_ignore_keep_runtime_single_image() -> None:
    dockerfile = read("Dockerfile")
    ignored = read(".dockerignore")
    assert "FROM python:3.12-slim" in dockerfile
    assert 'ENTRYPOINT ["ariadne"]' in dockerfile
    assert ".venv" in ignored
    assert "data" in ignored
    assert ".git" in ignored


def test_compose_uses_one_image_for_multiple_instances() -> None:
    compose = yaml.safe_load(read("docker-compose.example.yml"))
    services = compose["services"]
    assert services["qdrant"]["image"].startswith("qdrant/qdrant")
    assert services["ariadne-alpha"]["image"] == "ariadne-mcp:latest"
    assert services["ariadne-beta"]["image"] == "ariadne-mcp:latest"
    assert services["ariadne-alpha"]["ports"] == ["8765:8765"]
    assert services["ariadne-beta"]["ports"] == ["8766:8766"]
    assert "docker-alpha.yaml" in " ".join(services["ariadne-alpha"]["volumes"])
    assert "docker-beta.yaml" in " ".join(services["ariadne-beta"]["volumes"])


def test_example_configs_are_public_and_isolated() -> None:
    configs = sorted((ROOT / "configs" / "examples").glob("*.yaml"))
    assert {path.name for path in configs} >= {"minimal.yaml", "code-only.yaml", "documents-only.yaml", "mixed.yaml", "remote-server.yaml"}
    collections = set()
    for path in configs:
        text = path.read_text(encoding="utf-8")
        assert "/home/lorenzo" not in text
        assert "Dropbox" not in text
        data = yaml.safe_load(text)
        collections.add(data["storage"]["collection"])
        if path.name == "remote-server.yaml":
            assert data["server"]["host"] == "127.0.0.1"
    assert len(collections) == len(configs)


def test_systemd_template_uses_instance_name_and_registry_convention() -> None:
    unit = read("deployment/systemd/ariadne@.service")
    assert "Ariadne Knowledge MCP instance %i" in unit
    assert "ARIADNE_CONFIG_DIR=/etc/ariadne" in unit
    assert "ariadne serve %i --transport http" in unit
    assert "Restart=on-failure" in unit
