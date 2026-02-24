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
- **Status:** Not Started
- **Description:** GitHub Actions pipeline, test coverage reporting, linting, pre-commit hooks, and status badges on the README. Signals engineering discipline and production-readiness.
- **Key Deliverables:**
  - GitHub Actions CI pipeline (lint, test, coverage)
  - Coverage badge on README
  - Pre-commit hooks (ruff, mypy)
  - Automated release workflow

### Phase 3: Workflow Engine Hardening
- **Status:** Not Started
- **Description:** Evolve the workflow pipeline from sequential-only to a robust execution engine. Parallel steps, retry logic, webhook triggers, and execution history. Makes the orchestration story real, not just scaffolding.
- **Key Deliverables:**
  - Parallel step execution
  - Retry logic with configurable backoff
  - Workflow execution history and persistence
  - Webhook triggers for CI/CD integration

### Phase 4: Tool Suite Expansion & qaagent Decomposition
- **Status:** Not Started
- **Description:** Evaluate qaagent for decomposition opportunities. Break out self-contained capabilities into focused tools (e.g., route discovery, risk analysis). Each gets its own repo, tests, and Aegis service entry. Grow the suite to tell a bigger story.
- **Key Deliverables:**
  - Decomposition analysis of qaagent
  - 1-2 new standalone tools extracted or created
  - Each tool registered in Aegis with health checks
  - Updated landing page and architecture diagram

## Decision Log
See `docs/decision_log.md`

## Getting Started
1. Use `/handoff status` to check current state
2. Use `/handoff start [phase]` to begin planning
3. Use `/handoff` to continue the active cycle
