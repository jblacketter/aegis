# Project Roadmap

## Overview
Aegis is the AI Quality Control Plane — a unified orchestration layer and portfolio showcase for Jack Blacketter's suite of AI-powered QA tools. It serves both as real infrastructure (service registry, workflow pipelines, health monitoring) and as the storefront that demonstrates platform-level thinking to potential employers and collaborators.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Typer, httpx, HTML/CSS/JS

**Workflow:** Lead (claude) / Reviewer (codex) with Human Arbiter (see ai-handoff.yaml)

## Phases

### Phase 1: Landing Page & Portfolio Polish
- **Status:** Complete
- **Description:** Transform the landing page from a functional scaffold into an impressive portfolio piece. Live health indicators, polished architecture diagram, tool descriptions that sell the story, GitHub links, and responsive design. This is the public face of the project.
- **Key Deliverables:**
  - Redesigned landing page with professional visual identity
  - Live service health indicators with graceful offline states
  - Interactive architecture diagram
  - Tool cards with GitHub links, feature highlights, and usage context
  - Responsive design that works on mobile
  - Connection to the main portfolio site (jblacketter.github.io)

### Phase 2: CI/CD & Engineering Maturity
- **Status:** Complete
- **Description:** GitHub Actions pipeline, test coverage reporting, linting, type checking, pre-commit hooks, and status badges on the README. Signals engineering discipline and production-readiness.
- **Key Deliverables:**
  - GitHub Actions CI pipeline (lint, type check, test, coverage)
  - CI status and coverage badges on README
  - Pre-commit hooks (ruff, mypy)
  - Ruff linting/formatting, mypy type checking (basic mode)

### Phase 3: Workflow Engine Hardening & Test Coverage
- **Status:** Complete
- **Description:** Harden the workflow engine with retry logic, parallel step execution, and in-memory execution history. Fill the critical test coverage gap (CLI at 0%, integration tests missing). Add API endpoints for live workflow data on the landing page.
- **Key Deliverables:**
  - Retry logic with configurable exponential backoff (opt-in, runner-level)
  - Parallel step execution via `asyncio.gather()`
  - Per-step timeout
  - In-memory workflow execution history (persistence deferred to Phase 4+)
  - Richer condition expressions (`on_success`, `on_failure`, `always`)
  - `GET /api/workflows` and `GET /api/workflows/{name}` endpoints
  - CLI tests (0% → >90%), integration tests, overall coverage ≥85%
  - `--cov-fail-under=80` enforced in CI

### Phase 4: Production Readiness — Persistence, Auth & Dashboard
- **Status:** Complete
- **Description:** Make Aegis production-worthy with persistent execution history, API authentication, a live execution dashboard on the landing page, and config validation. Demonstrates data persistence design, security awareness, and developer experience polish.
- **Key Deliverables:**
  - Persistent execution history (SQLite via aiosqlite)
  - API key authentication middleware (optional, protects write endpoints)
  - Execution history dashboard on landing page
  - Config validation CLI (`aegis config validate`)
  - Mypy strict mode

### Phase 5: Workflow Events & Tool Suite Expansion
- **Status:** Complete
- **Description:** Add a workflow event system with webhook delivery for CI/CD integration. Create a new `report` step type that generates workflow summary reports. Document the qaagent decomposition strategy for future extraction. Update the landing page with event activity and ecosystem narrative.
- **Key Deliverables:**
  - Workflow event system (emit events at pipeline lifecycle points)
  - Webhook delivery (configurable external endpoints, fire-and-forget)
  - `report` step type (generates structured execution reports)
  - Webhook config in `.aegis.yaml` with env var support
  - `GET /api/events` endpoint for recent event log
  - qaagent decomposition analysis document
  - Updated landing page with event activity section
  - Updated architecture diagram showing event flow

### Phase 6: Containerization & Deployment Readiness
- **Status:** Planning
- **Description:** Containerize Aegis with Docker, enhance the health endpoint for production monitoring, add Docker build verification to CI, and update the README with deployment documentation. Completes the CI/CD story and makes Aegis immediately runnable by anyone with Docker installed.
- **Key Deliverables:**
  - Multi-stage Dockerfile (small production image, non-root user)
  - docker-compose.yml with SQLite volume persistence
  - Enhanced `/health` endpoint (version, uptime, config summary)
  - CI Docker build verification job
  - README deployment section and updated architecture diagram

## Decision Log
See `docs/decision_log.md`

## Getting Started
1. Use `/handoff status` to check current state
2. Use `/handoff start [phase]` to begin planning
3. Use `/handoff` to continue the active cycle
