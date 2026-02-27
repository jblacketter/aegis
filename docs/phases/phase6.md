# Phase 6: Containerization & Deployment Readiness

## Status
- [x] Planning
- [ ] In Review
- [ ] Approved
- [ ] Implementation
- [ ] Implementation Review
- [ ] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human

## Summary
**What:** Containerize Aegis with Docker, enhance the health endpoint for production monitoring, add a Docker build verification step to CI, and update the README with deployment documentation.
**Why:** A production-quality orchestration platform must be deployable. Docker is the industry standard for packaging Python services. This phase completes the CI/CD story (Phase 2 added CI, Phase 6 adds the "CD" side) and makes Aegis immediately runnable by anyone with Docker installed — no Python environment setup required. The enhanced health endpoint follows 12-factor app conventions. For the portfolio, this signals "I ship things that are ready to run in production."
**Depends on:** Phase 5 (complete)

## Scope

### In Scope

#### 1. Multi-stage Dockerfile
- **Build stage:** `python:3.11-slim` base, installs the package with `pip install --no-cache-dir .`
- **Production stage:** Fresh `python:3.11-slim` base, copies installed packages from builder. Non-root `aegis` user. Exposes port 8000.
- **HEALTHCHECK:** Built-in Docker healthcheck using `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`.
- **CMD:** `["aegis", "serve", "--host", "0.0.0.0", "--port", "8000"]`
- **Why multi-stage:** Keeps the production image small by excluding build tools, source code, and dev dependencies.

#### 2. docker-compose.yml
- **Service:** `aegis` — builds from Dockerfile, maps port 8000, mounts a named volume for SQLite persistence (`aegis-data:/app/data`), sets `AEGIS_DB_PATH=/app/data/aegis_history.db` via environment.
- **Health check:** Uses the `/health` endpoint with 30s interval.
- **Config mount:** Bind-mounts `.aegis.yaml` into the container as read-only.
- **Profiles:** Default profile runs the API server only. Simple, single-service compose for now — no external dependencies needed.

#### 3. .dockerignore
- Standard Python exclusions: `.venv`, `__pycache__`, `*.pyc`, `.git`, `.github`, `tests/`, `docs/`, `coverage.xml`, `.ruff_cache`, `.mypy_cache`, `*.egg-info`.
- Keeps the Docker build context small and fast.

#### 4. Enhanced Health Endpoint
- **Current:** `GET /health` returns `{"status": "ok"}` — minimal.
- **Enhanced:** Returns structured response with:
  - `status`: `"ok"`
  - `version`: Read from package metadata (`importlib.metadata.version("aegis-qa")`)
  - `uptime_seconds`: Computed from `app.state.start_time` (set at startup)
  - `services_configured`: Number of services in config
  - `workflows_configured`: Number of workflows in config
- **Why:** Production health endpoints should expose version and basic diagnostics. This follows the convention used by Kubernetes liveness/readiness probes and monitoring tools.
- **Backward compatible:** The response still includes `"status": "ok"` — existing checks that look for this field continue to work.

#### 5. CI Docker Build Verification
- **New job:** `docker` job in `.github/workflows/ci.yml` that runs `docker build .` to verify the Dockerfile builds successfully.
- **Build-only:** Does not push to any registry. Just validates that the image builds without errors on every PR and push to main.
- **Runs in parallel** with existing `lint`, `typecheck`, and `test` jobs.

#### 6. README Deployment Section
- **New section:** "Deployment" after "Quick Start" with:
  - Docker quick start: `docker build -t aegis .` + `docker run -p 8000:8000 aegis`
  - Docker Compose: `docker compose up`
  - Configuration notes: how to mount `.aegis.yaml` and persist the SQLite database
  - Environment variables: `AEGIS_DB_PATH` for database location
- **Update API table:** Add missing endpoints (`GET /api/events`, `GET /api/workflows`).
- **Update architecture diagram:** The mermaid diagram is outdated — it's missing the event system, webhooks, history, and health endpoint. Update to reflect current architecture.

### Out of Scope
- Docker registry push (GHCR, Docker Hub) — add when there's a release workflow
- Kubernetes manifests / Helm chart — overkill for current stage
- Docker Compose with external services (Redis, Postgres) — SQLite is sufficient
- Nginx reverse proxy — not needed for portfolio demo
- Multi-architecture builds (ARM64) — add later if needed
- Production secrets management — env vars are sufficient for now

## Technical Approach

### Dockerfile

```dockerfile
# ── Build stage ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml setup.cfg* ./
COPY src/ src/
RUN pip install --no-cache-dir .

# ── Production stage ─────────────────────────────────────────
FROM python:3.11-slim

RUN useradd --create-home --shell /bin/bash aegis
WORKDIR /app

# Copy installed packages and CLI entry point from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/aegis /usr/local/bin/aegis

# Create data directory for SQLite persistence
RUN mkdir -p /app/data && chown aegis:aegis /app/data

USER aegis
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["aegis", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
services:
  aegis:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - aegis-data:/app/data
      - ./.aegis.yaml:/app/.aegis.yaml:ro
    environment:
      AEGIS_DB_PATH: /app/data/aegis_history.db
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  aegis-data:
```

### Enhanced Health Endpoint

```python
import time
import importlib.metadata

@app.get("/health", tags=["meta"])
async def healthcheck() -> dict[str, object]:
    uptime = time.monotonic() - app.state.start_time
    return {
        "status": "ok",
        "version": importlib.metadata.version("aegis-qa"),
        "uptime_seconds": round(uptime, 1),
        "services_configured": len(config.services),
        "workflows_configured": len(config.workflows),
    }
```

`app.state.start_time` is set in `create_app()` right after app creation:
```python
app.state.start_time = time.monotonic()
```

### Config Loader Enhancement

The config loader needs to support `AEGIS_DB_PATH` environment variable for Docker deployments. The existing `${ENV_VAR}` interpolation in `.aegis.yaml` handles this, but the Docker compose sets it as a plain env var. The `history_db_path` field in `AegisConfig` should respect this env var as an override when present:

```python
import os

# In create_app() or config loading:
db_path = os.environ.get("AEGIS_DB_PATH", config.history_db_path)
```

This is a minimal change — the env var override is only applied in `create_app()` when constructing the history backend, keeping the config model clean.

### CI Docker Job

```yaml
docker:
  name: Docker Build
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Build Docker image
      run: docker build -t aegis:ci .
```

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage Docker build for production image |
| `docker-compose.yml` | Single-service compose for local development and deployment |
| `.dockerignore` | Exclude unnecessary files from Docker build context |

### Modified Files
| File | Changes |
|------|---------|
| `src/aegis_qa/api/app.py` | Enhanced `/health` endpoint with version, uptime, config summary; set `app.state.start_time`; `AEGIS_DB_PATH` env var support |
| `.github/workflows/ci.yml` | Add `docker` build job |
| `README.md` | Add Deployment section, update API table, update architecture diagram |
| `tests/test_api.py` | Update health endpoint test for new response shape |

## Success Criteria
- [ ] `docker build -t aegis .` produces a working image under 200MB
- [ ] `docker run -p 8000:8000 aegis` starts the server and `GET /health` returns structured response
- [ ] `docker compose up` starts the service with SQLite persistence on a named volume
- [ ] Non-root user: container runs as `aegis` user, not root
- [ ] `GET /health` returns `status`, `version`, `uptime_seconds`, `services_configured`, `workflows_configured`
- [ ] `AEGIS_DB_PATH` env var overrides the default SQLite path
- [ ] CI `docker` job builds successfully (added to `.github/workflows/ci.yml`)
- [ ] README includes Docker deployment instructions with build, run, and compose commands
- [ ] README architecture diagram reflects current system (events, webhooks, history)
- [ ] README API table includes all current endpoints
- [ ] `.dockerignore` excludes tests, docs, .git, caches
- [ ] All existing tests still pass
- [ ] `mypy --strict src/` passes clean
- [ ] `ruff check` passes clean
- [ ] Overall coverage >= 85%

## Open Questions
None — all decisions documented above.

## Risks
- **Image size:** Mitigation: multi-stage build strips build tools. Python 3.11-slim base is ~45MB. Total image should be well under 200MB.
- **SQLite concurrency in Docker:** Mitigation: single-process server (uvicorn without workers). SQLite handles single-writer well. Not a concern until horizontal scaling (out of scope).
- **Config file access in container:** Mitigation: bind-mount `.aegis.yaml` as read-only volume in compose. Document the mount path.
