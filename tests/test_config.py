"""Tests for config models and YAML loader."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from aegis_qa.config.loader import (
    _interpolate_env,
    _interpolate_recursive,
    find_config_file,
    load_config,
)
from aegis_qa.config.models import (
    AegisConfig,
    LLMConfig,
    ServiceEntry,
    WorkflowDef,
    WorkflowStepDef,
)

# ─── Model tests ───


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.ollama_base_url == "http://localhost:11434"
        assert cfg.default_model == "qwen2.5-coder:7b"
        assert cfg.timeout == 120

    def test_custom_values(self):
        cfg = LLMConfig(ollama_base_url="http://192.168.1.50:11434", default_model="llama3", timeout=60)
        assert cfg.ollama_base_url == "http://192.168.1.50:11434"
        assert cfg.default_model == "llama3"


class TestServiceEntry:
    def test_minimal(self):
        entry = ServiceEntry(name="Test", url="http://localhost:9000")
        assert entry.name == "Test"
        assert entry.health_endpoint == "/health"
        assert entry.api_key_env == ""
        assert entry.features == []

    def test_full(self):
        entry = ServiceEntry(
            name="QA Agent",
            description="Test gen",
            url="http://localhost:8080",
            health_endpoint="/healthz",
            api_key_env="QA_KEY",
            features=["A", "B"],
        )
        assert entry.features == ["A", "B"]
        assert entry.api_key_env == "QA_KEY"


class TestWorkflowDef:
    def test_empty_steps(self):
        wf = WorkflowDef(name="Empty")
        assert wf.steps == []

    def test_with_steps(self):
        wf = WorkflowDef(
            name="Pipeline",
            steps=[
                WorkflowStepDef(type="discover", service="qa"),
                WorkflowStepDef(type="test", service="qa", condition="has_failures"),
            ],
        )
        assert len(wf.steps) == 2
        assert wf.steps[1].condition == "has_failures"


class TestAegisConfig:
    def test_defaults(self):
        cfg = AegisConfig()
        assert cfg.aegis.name == "Aegis"
        assert cfg.services == {}
        assert cfg.workflows == {}

    def test_from_dict(self, sample_config_dict):
        cfg = AegisConfig(**sample_config_dict)
        assert "qaagent" in cfg.services
        assert cfg.services["qaagent"].name == "QA Agent"
        assert "full_pipeline" in cfg.workflows
        assert len(cfg.workflows["full_pipeline"].steps) == 3


# ─── Loader tests ───


class TestEnvInterpolation:
    def test_simple_var(self):
        with patch.dict(os.environ, {"MY_URL": "http://example.com"}):
            assert _interpolate_env("${MY_URL}") == "http://example.com"

    def test_var_with_default(self):
        os.environ.pop("MISSING_VAR", None)
        assert _interpolate_env("${MISSING_VAR:-fallback}") == "fallback"

    def test_var_with_default_overridden(self):
        with patch.dict(os.environ, {"MY_VAR": "real"}):
            assert _interpolate_env("${MY_VAR:-fallback}") == "real"

    def test_unset_var_preserved(self):
        os.environ.pop("UNSET_12345", None)
        assert _interpolate_env("${UNSET_12345}") == "${UNSET_12345}"

    def test_no_interpolation(self):
        assert _interpolate_env("plain string") == "plain string"

    def test_recursive_dict(self):
        with patch.dict(os.environ, {"PORT": "9090"}):
            data = {"url": "http://host:${PORT}", "nested": {"key": "${PORT}"}}
            result = _interpolate_recursive(data)
            assert result["url"] == "http://host:9090"
            assert result["nested"]["key"] == "9090"

    def test_recursive_list(self):
        with patch.dict(os.environ, {"TAG": "v1"}):
            data = ["${TAG}", "plain"]
            result = _interpolate_recursive(data)
            assert result == ["v1", "plain"]

    def test_non_string_passthrough(self):
        assert _interpolate_recursive(42) == 42
        assert _interpolate_recursive(None) is None
        assert _interpolate_recursive(True) is True


class TestFindConfigFile:
    def test_finds_in_directory(self, tmp_path: Path):
        config = tmp_path / ".aegis.yaml"
        config.touch()
        result = find_config_file(tmp_path)
        assert result == config

    def test_finds_in_parent(self, tmp_path: Path):
        config = tmp_path / ".aegis.yaml"
        config.touch()
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        result = find_config_file(child)
        assert result == config

    def test_returns_none_when_missing(self, tmp_path: Path):
        result = find_config_file(tmp_path)
        assert result is None


class TestLoadConfig:
    def test_loads_valid_config(self, config_file: Path):
        cfg = load_config(path=config_file)
        assert cfg.aegis.name == "Aegis"
        assert "qaagent" in cfg.services

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Could not find"):
            load_config(path=tmp_path / "nonexistent.yaml")

    def test_raises_on_invalid_config(self, tmp_path: Path):
        bad = tmp_path / ".aegis.yaml"
        bad.write_text("services:\n  qaagent:\n    name: 123\n    url: true\n")
        with pytest.raises(ValueError, match="Invalid configuration"):
            load_config(path=bad)

    def test_env_interpolation_in_file(self, tmp_path: Path):
        config = tmp_path / ".aegis.yaml"
        config.write_text(
            "aegis:\n  name: Aegis\nservices:\n  svc:\n    name: Svc\n    url: ${TEST_SVC_URL:-http://default:80}\n"
        )
        os.environ.pop("TEST_SVC_URL", None)
        cfg = load_config(path=config)
        assert cfg.services["svc"].url == "http://default:80"
