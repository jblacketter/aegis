# Phase 4: Production Readiness — Persistence, Auth & Dashboard

## Status
- [x] Planning
- [x] In Review
- [x] Approved
- [x] Implementation
- [x] Implementation Review
- [x] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human

## Summary
**What:** Make Aegis production-worthy with persistent execution history (SQLite), API key authentication, a live execution dashboard on the landing page, config validation CLI, and mypy strict mode.
**Why:** A QA orchestration platform without persistent history, security, or validation is a demo, not a product. Phase 4 crosses the line from "works" to "production-ready" — the kind of engineering maturity a QA lead brings to a team. Persistent history means workflow runs survive restarts. Auth protects the API. Config validation catches mistakes before runtime. The dashboard makes the portfolio demo tangible and impressive.
**Depends on:** Phase 3 (complete)

## Scope

### In Scope

#### 1. Persistent Execution History (SQLite)
- **Storage backend:** SQLite via `aiosqlite`. Single `aegis_history.db` file in a configurable location.
- **Schema:** `workflow_runs` table (run-level data) and `step_runs` table (per-step data). Normalized, not JSON blobs.
- **History protocol:** Abstract `ExecutionHistoryBackend` protocol. Both `InMemoryHistory` (existing, for tests) and `SqliteHistory` (new) implement it.
- **App wiring:** `create_app()` creates the history backend and stores it on `app.state.history`. Route handlers access it via `request.app.state.history`. No module-level singletons — prevents the Phase 3 bug class where run and history were disconnected.
- **Test wiring:** Tests create `InMemoryHistory`, set it on `app.state.history`. Same access path, different backend.
- **Migration:** Auto-create tables on first use (no migration framework needed for v1).
- **Retention:** `history_max_records: int = 0` in `AegisConfig` (0 = unlimited). When > 0, `SqliteHistory.record()` prunes after insertion: deletes oldest records for that workflow beyond the limit. Pruning SQL: `DELETE FROM workflow_runs WHERE id IN (SELECT id FROM workflow_runs WHERE workflow_name = ? ORDER BY started_at ASC LIMIT ?)` where the limit is `total - max_records`.

#### 2. API Key Authentication
- **Config:** New optional `auth.api_key` field in `AegisConfig`. When set, write endpoints require `X-API-Key` header.
- **Middleware:** FastAPI dependency that checks the key. Returns 401 on mismatch, skips check when no key configured.
- **Protected endpoints:** `POST /api/workflows/{name}/run`. Read endpoints stay public.
- **Env var support:** Key can come from `${AEGIS_API_KEY}` in `.aegis.yaml` via existing interpolation.

#### 3. Execution History Dashboard
- **Landing page section:** New "Recent Runs" section showing last 10 workflow executions across all workflows.
- **Data source:** `GET /api/history` (new top-level endpoint — avoids route conflict with `GET /api/workflows/{name}`).
- **Display:** Workflow name, timestamp, success/failure badge, step count, total duration.
- **Static fallback:** Shows "No execution history available" when API is offline.

#### 4. Config Validation CLI
- **Command:** `aegis config validate [--path PATH]`
- **Checks:**
  - YAML parses correctly
  - Pydantic validation passes
  - All workflow step services exist in the `services` dict
  - All workflow step types exist in `STEP_REGISTRY`
  - Service URLs are syntactically valid
- **Output:** Green checkmarks for passing checks, red errors with details for failures.
- **Exit code:** 0 on success, 1 on validation errors.

#### 5. Mypy Strict Mode
- **Enable:** `strict = true` in `[tool.mypy]` config.
- **Fix:** All resulting type errors across the codebase.
- **Scope:** `src/` only (tests can remain non-strict).

### Out of Scope
- Webhook/event triggers — Phase 5
- qaagent decomposition — Phase 5
- Multi-user auth / OAuth / RBAC — overkill for portfolio
- Database migrations framework (Alembic) — not needed for v1 schema
- Real-time WebSocket updates on dashboard — future enhancement
- History export/import — future enhancement

## Technical Approach

### SQLite History

New dependency: `aiosqlite>=0.20` added to `pyproject.toml`.

**Protocol:**
```python
class ExecutionHistoryBackend(Protocol):
    async def record(self, execution: ExecutionRecord) -> None: ...
    async def get_history(self, workflow_name: str) -> list[ExecutionRecord]: ...
    async def get_all(self) -> dict[str, list[ExecutionRecord]]: ...
    async def get_recent(self, limit: int = 10) -> list[ExecutionRecord]: ...
```

The existing `ExecutionHistory` (in-memory) keeps its interface and is renamed to `InMemoryHistory`. New `SqliteHistory` implements the same protocol.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    success INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL,
    service TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    duration_ms REAL,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 1
);
```

**Config:**
```python
class AegisConfig(BaseModel):
    # ... existing fields ...
    history_db_path: str = "aegis_history.db"
    history_max_records: int = 0  # 0 = unlimited
```

**Retention pruning** (in `SqliteHistory.record()`):
```python
if self._max_records > 0:
    count = await db.execute_fetchone(
        "SELECT COUNT(*) FROM workflow_runs WHERE workflow_name = ?", (name,)
    )
    excess = count[0] - self._max_records
    if excess > 0:
        await db.execute(
            "DELETE FROM workflow_runs WHERE id IN ("
            "  SELECT id FROM workflow_runs WHERE workflow_name = ? "
            "  ORDER BY started_at ASC LIMIT ?"
            ")", (name, excess)
        )
        # step_runs cascade-deleted via ON DELETE CASCADE (added to FK)
```

**Wiring — Dependency injection via `app.state`:**
```
create_app()
  ├─ config = load_config()
  ├─ history = SqliteHistory(config.history_db_path, config.history_max_records)
  ├─ app.state.history = history       ← stored once
  │
  ├─ workflow_list routes
  │   └─ GET /api/workflows/{name}/history
  │       └─ request.app.state.history.get_history(name)  ← reads from shared instance
  │
  ├─ workflows routes
  │   └─ POST /api/workflows/{name}/run
  │       └─ PipelineRunner(config, history=request.app.state.history)  ← writes to shared instance
  │
  └─ history routes (new router in workflow_list.py or separate file)
      └─ GET /api/history
          └─ request.app.state.history.get_recent()  ← reads from shared instance

Tests:
  app.state.history = InMemoryHistory()  ← same access path, in-memory backend
```

This eliminates the module-level `_history` singleton from `workflow_list.py`. All routes access `request.app.state.history`, guaranteed to be the same instance.

### API Key Auth

New config model:
```python
class AuthConfig(BaseModel):
    api_key: str = ""  # empty = auth disabled

class AegisConfig(BaseModel):
    # ... existing fields ...
    auth: AuthConfig = Field(default_factory=AuthConfig)
```

FastAPI dependency:
```python
async def require_api_key(request: Request) -> None:
    config = load_config()
    if not config.auth.api_key:
        return  # auth disabled
    key = request.headers.get("X-API-Key", "")
    if key != config.auth.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

Applied to `POST /api/workflows/{name}/run` via `Depends(require_api_key)`.

### Dashboard

New endpoint `GET /api/history` (top-level, not under `/api/workflows/` to avoid `{name}` capture) returns all recent runs (limit 10 by default, configurable via `?limit=N` query param).

Landing page adds a "Recent Runs" section after the workflows section. Fetches from `GET /api/history`. Renders a table with: workflow name, timestamp (relative), status badge, step summary, duration.

### Config Validation

New CLI command in `cli.py`:
```python
@config_app.command("validate")
def config_validate(path: Path | None = ...) -> None:
    # 1. Load and validate YAML/Pydantic
    # 2. Check workflow step services exist
    # 3. Check workflow step types exist
    # 4. Check service URLs are valid
```

### Mypy Strict

Add to `pyproject.toml`:
```toml
[tool.mypy]
strict = true
```

Fix all resulting errors. Common fixes: add return types, add parameter types, add `# type: ignore` only where truly necessary (e.g., dynamic imports).

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `src/aegis_qa/workflows/history_sqlite.py` | SQLite-backed execution history |
| `src/aegis_qa/api/auth.py` | API key authentication dependency |
| `tests/test_history.py` | Tests for both in-memory and SQLite history backends |
| `tests/test_auth.py` | Tests for API key auth middleware |

### Modified Files
| File | Changes |
|------|---------|
| `src/aegis_qa/config/models.py` | Add `AuthConfig`, `history_db_path` to `AegisConfig` |
| `src/aegis_qa/workflows/history.py` | Rename class to `InMemoryHistory`, add `ExecutionHistoryBackend` protocol, add `get_recent()` |
| `src/aegis_qa/workflows/pipeline.py` | Type annotation updates for protocol |
| `src/aegis_qa/api/routes/workflows.py` | Add `Depends(require_api_key)` to run endpoint |
| `src/aegis_qa/api/routes/workflow_list.py` | Remove module-level singleton, access `request.app.state.history`, add `GET /api/history` endpoint |
| `src/aegis_qa/api/app.py` | Create history backend in `create_app()`, store on `app.state.history` |
| `src/aegis_qa/cli.py` | Add `config validate` command |
| `src/aegis_qa/landing/app.js` | Add "Recent Runs" section |
| `pyproject.toml` | Add `aiosqlite` dependency, enable mypy strict |
| `.aegis.yaml.example` | Add `auth` and `history_db_path` config |
| `tests/test_cli.py` | Tests for `config validate` command |
| `tests/test_api.py` | Tests for auth on run endpoint |
| `tests/test_integration.py` | Integration tests with auth and persistent history |
| `tests/test_workflows.py` | Update for protocol type changes |

## Success Criteria
- [ ] SQLite history persists workflow runs across process restarts
- [ ] `InMemoryHistory` and `SqliteHistory` both pass the same interface tests
- [ ] `GET /api/history` returns recent runs from persistent store (no route conflict with `GET /api/workflows/{name}`)
- [ ] Retention pruning deletes oldest records per workflow when `history_max_records > 0`
- [ ] API key auth blocks unauthorized POST requests with 401
- [ ] API key auth is disabled when no key is configured (backwards compatible)
- [ ] Landing page shows "Recent Runs" section with live data
- [ ] `aegis config validate` catches: missing services, unknown step types, invalid URLs
- [ ] `aegis config validate` returns exit code 0 on valid config, 1 on invalid
- [ ] `mypy --strict src/` passes clean
- [ ] All existing tests still pass
- [ ] `ruff check` passes clean
- [ ] Overall coverage ≥85%

## Open Questions
None — all decisions are documented above.

## Risks
- **Mypy strict may require significant type annotation work:** Mitigation: fix src/ only, tests stay non-strict. Use targeted `# type: ignore` for truly dynamic code.
- **SQLite locking under concurrent requests:** Mitigation: aiosqlite uses a single connection with WAL mode. For a portfolio-scale app, this is sufficient.
- **Config validation may need to handle edge cases:** Mitigation: start with the core checks listed above, add more in future phases.
