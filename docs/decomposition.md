# qaagent Decomposition Analysis

## Overview

qaagent is currently a monolithic application that handles route discovery, risk analysis, test generation, and orchestration. As the tool suite grows, extracting these capabilities into standalone services will enable independent scaling, testing, and deployment. This document analyzes the current architecture and proposes an extraction strategy.

## Current Architecture

qaagent's modular structure naturally groups into four domains:

1. **Route Discovery** — Crawls target applications to discover API endpoints, pages, and routes. Produces a route map used by downstream components.
2. **Risk Analyzer** — Evaluates discovered routes for security and quality risks. Assigns risk scores and prioritizes testing targets.
3. **Test Generator** — Generates test cases based on discovered routes and risk analysis. Produces executable test suites.
4. **Orchestrator** — Coordinates the above components in sequence, manages execution state, and reports results.

## Proposed Extraction Order

### Phase A: Route Discovery Service (First)

**Why first:** Route discovery is the most self-contained module with the clearest API boundary. It has no dependencies on other qaagent modules — it takes a target URL and returns a route map. Other components depend on its output, but it depends on nothing.

**Proposed API contract:**
```
POST /api/discover
  Body: {"target_url": str, "options": {...}}
  Response: {"routes": [...], "metadata": {...}}

GET /api/discover/{job_id}
  Response: {"status": str, "routes": [...]}
```

**Migration path:**
1. Extract route discovery logic into a standalone FastAPI service
2. Register as an Aegis service in `.aegis.yaml`
3. Update qaagent's orchestrator to call the discovery service via HTTP instead of direct import
4. qaagent can optionally keep a thin adapter for standalone use

### Phase B: Risk Analyzer Service (Second)

**Why second:** Risk analysis depends only on route discovery output (a route map). Once discovery is extracted, the risk analyzer's inputs are well-defined HTTP payloads rather than internal data structures.

**Proposed API contract:**
```
POST /api/analyze
  Body: {"routes": [...], "config": {...}}
  Response: {"risks": [...], "summary": {...}}
```

**Migration path:**
1. Extract risk analysis into a standalone service
2. Register in Aegis
3. Update qaagent orchestrator and Aegis workflow steps

### Phase C: Test Generator Service (Third)

**Why third:** Test generation depends on both route discovery and risk analysis output. It's the most complex module with LLM integration, so it benefits from the patterns established in Phases A and B.

**Proposed API contract:**
```
POST /api/generate
  Body: {"routes": [...], "risks": [...], "config": {...}}
  Response: {"tests": [...], "coverage": {...}}
```

**Migration path:**
1. Extract test generation into a standalone service
2. Register in Aegis
3. The orchestrator in qaagent becomes a thin coordination layer (or is replaced by Aegis workflows entirely)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking qaagent during extraction | High | Extract copies first, run both paths in parallel, switch over when stable |
| Network latency between services | Medium | Services run on same host for portfolio; latency is negligible for demo scale |
| Increased deployment complexity | Medium | Docker Compose or similar for local dev; Aegis health monitoring catches failures |
| LLM dependency in test generator | Low | LLM config is already centralized in Aegis; generator service reads from shared config |

## Benefits

- **Independent scaling:** Each service can be developed, tested, and deployed independently
- **Clear API contracts:** Forces well-defined interfaces between components
- **Portfolio narrative:** Demonstrates microservices architecture and platform thinking
- **Aegis integration:** Each extracted service becomes a first-class Aegis-managed tool, enriching the control plane story

## Timeline

This is a documentation-only deliverable. Actual extraction is planned for future phases as the tool suite matures. The extraction order (discovery → risk → generator) follows the dependency chain and minimizes risk at each step.
