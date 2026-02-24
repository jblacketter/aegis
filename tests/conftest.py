"""Shared fixtures for Aegis tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from aegis_qa.config.models import AegisConfig


SAMPLE_CONFIG: Dict[str, Any] = {
    "aegis": {"name": "Aegis", "version": "0.1.0"},
    "llm": {
        "ollama_base_url": "http://localhost:11434",
        "default_model": "qwen2.5-coder:7b",
        "timeout": 120,
    },
    "services": {
        "qaagent": {
            "name": "QA Agent",
            "description": "Route discovery and test generation",
            "url": "http://localhost:8080",
            "health_endpoint": "/health",
            "api_key_env": "QAAGENT_API_KEY",
            "features": ["Route Discovery", "Test Generation"],
            "repo_url": "https://github.com/jblacketter/qaagent",
            "docs_url": "",
        },
        "bugalizer": {
            "name": "Bugalizer",
            "description": "Bug triage and code localization",
            "url": "http://localhost:8090",
            "health_endpoint": "/health",
            "api_key_env": "",
            "features": ["Bug Triage"],
            "repo_url": "https://github.com/jblacketter/bugalizer",
            "docs_url": "",
        },
    },
    "workflows": {
        "full_pipeline": {
            "name": "Full QA Pipeline",
            "steps": [
                {"type": "discover", "service": "qaagent"},
                {"type": "test", "service": "qaagent"},
                {"type": "submit_bugs", "service": "bugalizer", "condition": "has_failures"},
            ],
        },
    },
}


@pytest.fixture()
def sample_config() -> AegisConfig:
    """Return a parsed AegisConfig from sample data."""
    return AegisConfig(**SAMPLE_CONFIG)


@pytest.fixture()
def sample_config_dict() -> Dict[str, Any]:
    """Return raw sample config dict."""
    return dict(SAMPLE_CONFIG)


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    """Write sample config to a temp .aegis.yaml and return the path."""
    path = tmp_path / ".aegis.yaml"
    with path.open("w") as fh:
        yaml.dump(SAMPLE_CONFIG, fh)
    return path
