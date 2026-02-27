"""Pydantic models for Aegis configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Shared LLM backend configuration."""

    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:7b"
    timeout: int = 120


class ServiceEntry(BaseModel):
    """Configuration for a downstream service."""

    name: str
    description: str = ""
    url: str
    health_endpoint: str = "/health"
    api_key_env: str = ""
    features: list[str] = Field(default_factory=list)
    repo_url: str = ""
    docs_url: str = ""


class WorkflowStepDef(BaseModel):
    """A single step in a workflow pipeline."""

    type: str
    service: str
    condition: str | None = None
    parallel: bool = False
    retries: int = 0
    retry_delay: float = 1.0
    timeout: float = 30.0


class WorkflowDef(BaseModel):
    """A named workflow pipeline definition."""

    name: str
    steps: list[WorkflowStepDef] = Field(default_factory=list)


class AegisIdentity(BaseModel):
    """Top-level Aegis identity metadata."""

    name: str = "Aegis"
    version: str = "0.1.0"


class AuthConfig(BaseModel):
    """Authentication configuration."""

    api_key: str = ""  # empty = auth disabled


class WebhookConfig(BaseModel):
    """Configuration for a single webhook endpoint."""

    url: str
    events: list[str] = Field(default_factory=lambda: ["workflow.completed"])
    secret: str = ""  # HMAC signing key, supports ${ENV_VAR}


class AegisConfig(BaseModel):
    """Root configuration model for .aegis.yaml."""

    aegis: AegisIdentity = Field(default_factory=AegisIdentity)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    services: dict[str, ServiceEntry] = Field(default_factory=dict)
    workflows: dict[str, WorkflowDef] = Field(default_factory=dict)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    history_db_path: str = "aegis_history.db"
    history_max_records: int = 0  # 0 = unlimited
    webhooks: list[WebhookConfig] = Field(default_factory=list)
    event_log_size: int = 100
