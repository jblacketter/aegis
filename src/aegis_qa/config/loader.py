"""YAML config loader with environment variable interpolation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from aegis_qa.config.models import AegisConfig

CONFIG_FILENAME = ".aegis.yaml"

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _interpolate_env(value: str) -> str:
    """Replace ${VAR} and ${VAR:-default} patterns with environment values."""

    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1)
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
            return os.environ.get(var_name.strip(), default)
        return os.environ.get(expr.strip(), match.group(0))

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _interpolate_recursive(data: Any) -> Any:
    """Walk a nested data structure and interpolate env vars in strings."""
    if isinstance(data, str):
        return _interpolate_env(data)
    if isinstance(data, dict):
        return {k: _interpolate_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate_recursive(item) for item in data]
    return data


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default cwd) looking for .aegis.yaml."""
    current = (start or Path.cwd()).resolve()
    for ancestor in [current, *current.parents]:
        candidate = ancestor / CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return None


def load_config(path: Path | None = None) -> AegisConfig:
    """Load and validate .aegis.yaml, applying env-var interpolation."""
    config_path = path or find_config_file()
    if not config_path or not config_path.exists():
        raise FileNotFoundError(
            f"Could not find {CONFIG_FILENAME}. Create one from .aegis.yaml.example or specify a path."
        )
    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    data = _interpolate_recursive(raw)
    try:
        return AegisConfig(**data)
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration in {config_path}: {exc}") from exc
