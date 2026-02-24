"""Pydantic models for Aegis configuration."""

from __future__ import annotations

from typing import Dict, List, Optional

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
    features: List[str] = Field(default_factory=list)


class WorkflowStepDef(BaseModel):
    """A single step in a workflow pipeline."""

    type: str
    service: str
    condition: Optional[str] = None


class WorkflowDef(BaseModel):
    """A named workflow pipeline definition."""

    name: str
    steps: List[WorkflowStepDef] = Field(default_factory=list)


class AegisIdentity(BaseModel):
    """Top-level Aegis identity metadata."""

    name: str = "Aegis"
    version: str = "0.1.0"


class AegisConfig(BaseModel):
    """Root configuration model for .aegis.yaml."""

    aegis: AegisIdentity = Field(default_factory=AegisIdentity)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    services: Dict[str, ServiceEntry] = Field(default_factory=dict)
    workflows: Dict[str, WorkflowDef] = Field(default_factory=dict)
