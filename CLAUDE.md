# CLAUDE.md — Aegis Project Instructions

## Project Overview

Aegis is the AI Quality Control Plane — a lightweight orchestration layer that sits above qaagent and bugalizer, providing unified service management, workflow pipelines, and a portfolio landing page.

## Package Structure

- **Import as:** `aegis_qa`
- **PyPI name:** `aegis-qa`
- **CLI command:** `aegis`
- **Source layout:** `src/aegis_qa/`

## Key Modules

- `config/models.py` — Pydantic config models (AegisConfig, ServiceEntry, LLMConfig, WorkflowDef)
- `config/loader.py` — YAML loading with `${ENV_VAR}` interpolation
- `registry/` — Service registry and async health checks
- `workflows/` — Sequential pipeline runner with conditional steps
- `api/` — FastAPI endpoints for services, workflows, portfolio
- `landing/` — Static HTML/CSS/JS portfolio landing page
- `cli.py` — Typer CLI entry point

## Patterns

- Follow qaagent Pydantic patterns: leaf models first, Field(default_factory=...) for mutables
- FastAPI app factory pattern in `api/app.py`
- Async httpx for health checks and workflow step execution
- Typer CLI with Rich console output
- All downstream HTTP calls must be mocked in tests
