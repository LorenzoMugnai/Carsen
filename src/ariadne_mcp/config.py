"""Configuration loading and validation for Ariadne knowledge instances.

Ariadne is configured per knowledge base.  This module validates one YAML file
as one isolated knowledge instance and normalises filesystem paths without
loading models, connecting to Qdrant, or requiring a generative LLM.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class KnowledgeConfig(BaseModel):
    """Human and machine identity for a knowledge instance."""

    id: str = Field(min_length=1)
    name: str | None = None
    description: str = ""

    @field_validator("id")
    @classmethod
    def filesystem_safe_id(cls, value: str) -> str:
        """Require an identifier suitable for paths, source IDs and collections."""

        if any(part in value for part in ("/", "\\", "..")) or not value.replace("-", "_").replace("_", "").isalnum():
            raise ValueError("knowledge.id must be filesystem-safe")
        return value


class ServerConfig(BaseModel):
    """Default MCP server binding for one knowledge instance."""

    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65_535)

    @field_validator("transport")
    @classmethod
    def supported_transport(cls, value: str) -> str:
        if value not in {"stdio", "http"}:
            raise ValueError("server.transport must be 'stdio' or 'http'")
        return value


class StorageConfig(BaseModel):
    """Instance-specific persistent storage locations."""

    qdrant_url: str = "http://127.0.0.1:6333"
    collection: str | None = None
    data_directory: Path | None = None


class ModelProviderConfig(BaseModel):
    """Configurable provider and model selection for embeddings or reranking."""

    provider: str = "sentence_transformers"
    model: str
    dimensions: int | None = Field(default=None, ge=1)
    device: str = "auto"
    query_instruction: str | None = None


class ModelsConfig(BaseModel):
    """Retrieval model configuration; no generative model is configured here."""

    embedding: ModelProviderConfig = Field(
        default_factory=lambda: ModelProviderConfig(model="Qwen/Qwen3-Embedding-0.6B", dimensions=1024)
    )
    reranker: ModelProviderConfig | None = Field(
        default_factory=lambda: ModelProviderConfig(model="Qwen/Qwen3-Reranker-0.6B")
    )


class RetrievalConfig(BaseModel):
    """Hybrid retrieval limits and behaviour for one instance."""

    dense_candidates: int = Field(default=40, ge=0)
    sparse_candidates: int = Field(default=40, ge=0)
    fused_candidates: int = Field(default=30, ge=1)
    final_results: int = Field(default=8, ge=1)
    fusion: str = "rrf"
    max_results_per_source: int = Field(default=3, ge=1)

    @field_validator("fusion")
    @classmethod
    def supported_fusion(cls, value: str) -> str:
        if value != "rrf":
            raise ValueError("retrieval.fusion currently supports only 'rrf'")
        return value


class IndexingConfig(BaseModel):
    """File discovery and incremental indexing settings."""

    incremental: bool = True
    follow_symlinks: bool = False
    ignored_directories: list[str] = Field(default_factory=lambda: [".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"])
    ignored_extensions: list[str] = Field(default_factory=lambda: [".pyc", ".so", ".dll", ".dylib"])


class SourcePathConfig(BaseModel):
    """A configured source root for code or documents."""

    path: Path
    repository_name: str | None = None
    type: str | None = None
    tags: list[str] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    """All filesystem sources belonging to one knowledge instance."""

    code: list[SourcePathConfig] = Field(default_factory=list)
    documents: list[SourcePathConfig] = Field(default_factory=list)


class PolicyConfig(BaseModel):
    """Policy metadata exposed to clients; it is not an enforcement boundary."""

    allow_external_llm: bool = False


class AriadneConfig(BaseModel):
    """Validated YAML configuration for exactly one knowledge instance."""

    knowledge: KnowledgeConfig
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)

    @model_validator(mode="after")
    def derive_instance_storage(self) -> AriadneConfig:
        """Derive collection and data directory from the knowledge ID when absent."""

        if self.storage.collection is None:
            self.storage.collection = f"kb_{self.knowledge.id.replace('-', '_')}"
        if self.storage.data_directory is None:
            self.storage.data_directory = Path.home() / ".local" / "share" / "ariadne" / self.knowledge.id
        if self.knowledge.name is None:
            self.knowledge.name = self.knowledge.id
        return self

    @property
    def name(self) -> str:
        """Return the registry name for compatibility with CLI listings."""

        return self.knowledge.id


def expand_env(value: Any) -> Any:
    """Recursively expand environment variables and ``~`` in YAML values."""

    if isinstance(value, str):
        return os.path.expanduser(os.path.expandvars(value))
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    return value


def _resolve_relative_paths(config: AriadneConfig, base_dir: Path) -> AriadneConfig:
    """Resolve relative data and source paths against the configuration file."""

    if config.storage.data_directory and not config.storage.data_directory.is_absolute():
        config.storage.data_directory = (base_dir / config.storage.data_directory).resolve()
    for source in [*config.sources.code, *config.sources.documents]:
        if not source.path.is_absolute():
            source.path = (base_dir / source.path).resolve()
    return config


def load_config(path: str | Path) -> AriadneConfig:
    """Load a YAML file and return a validated knowledge-instance config."""

    config_path = Path(path).expanduser()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("configuration must be a YAML mapping")
    try:
        return _resolve_relative_paths(AriadneConfig.model_validate(expand_env(raw)), config_path.parent)
    except ValidationError:
        raise


def default_config(name: str) -> AriadneConfig:
    """Build a default local configuration for a registry entry."""

    return AriadneConfig(knowledge=KnowledgeConfig(id=name, name=f"{name} Knowledge Base"))


def dump_config(config: AriadneConfig) -> str:
    """Serialise a configuration as YAML for local registry storage."""

    data = config.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(data, sort_keys=False)
