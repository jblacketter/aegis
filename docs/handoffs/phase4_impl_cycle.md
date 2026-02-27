# Handoff: Phase 4 (Production Readiness — Persistence, Auth & Dashboard) — Implementation Review

**Phase:** phase4
**Type:** impl
**Date:** 2026-02-27
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase4.md`
- Plan review: `docs/handoffs/phase4_plan_cycle.md` (approved Round 2)

## Implementation Summary

Phase 4 implements all five pillars from the approved plan. 154 tests pass, 93.64% coverage, ruff clean, mypy strict clean.

### 1. Persistent Execution History (SQLite)

**Protocol** (`src/aegis_qa/workflows/history.py`):
- Added `ExecutionHistoryBackend` protocol with `record()`, `get_history()`, `get_all()`, `get_recent()` methods
- Renamed `ExecutionHistory` to `InMemoryHistory` (backwards-compatible alias kept)
- Added `get_recent(limit)` method to `InMemoryHistory`
- Added `duration_ms` and `step_count` to `ExecutionRecord.to_dict()`

**SQLite backend** (`src/aegis_qa/workflows/history_sqlite.py` — NEW):
- `SqliteHistory` class using `aiosqlite`
- Normalized schema: `workflow_runs` + `step_runs` tables with `ON DELETE CASCADE` FK
- Auto-creates tables on first use (no migration framework needed)
- Retention pruning in `record()`: when `max_records > 0`, deletes oldest excess records per workflow after insertion

**Config** (`src/aegis_qa/config/models.py`):
- Added `history_db_path: str = "aegis_history.db"` to `AegisConfig`
- Added `history_max_records: int = 0` to `AegisConfig` (0 = unlimited)

### 2. API Key Authentication

**Auth dependency** (`src/aegis_qa/api/auth.py` — NEW):
- `require_api_key()` FastAPI dependency reads config from `request.app.state.config`
- Returns early (no-op) when `config.auth.api_key` is empty — backwards compatible
- Returns 401 when key is missing or incorrect

**Config** (`src/aegis_qa/config/models.py`):
- Added `AuthConfig(api_key: str = "")` model
- Added `auth: AuthConfig = Field(default_factory=AuthConfig)` to `AegisConfig`

**Route protection** (`src/aegis_qa/api/routes/workflows.py`):
- `POST /api/workflows/{name}/run` now uses `dependencies=[Depends(require_api_key)]`
- Read endpoints remain public (no auth required)

### 3. Execution History Dashboard

**New endpoint** (`src/aegis_qa/api/routes/workflow_list.py`):
- `GET /api/history` — top-level path (avoids route conflict with `GET /api/workflows/{name}`)
- Returns most recent execution records across all workflows (default limit=10, configurable via `?limit=N`)
- Reads from `request.app.state.history`

**Landing page** (`src/aegis_qa/landing/index.html`, `styles.css`, `app.js`):
- New "Recent Runs" section after Workflows
- Rows show: pass/fail badge, workflow name, step count, duration, relative timestamp
- Fetches from `GET /api/history` with graceful fallback ("No execution history available")

### 4. Config Validation CLI

**New command** (`src/aegis_qa/cli.py`):
- `aegis config validate [--path PATH]`
- Checks: YAML parsing, Pydantic validation, service URL validity, workflow step service references, workflow step type existence
- Green checkmarks for passing checks, red errors with details
- Exit code 0 on success, 1 on validation errors

### 5. Mypy Strict Mode

**Config** (`pyproject.toml`):
- `strict = true` in `[tool.mypy]`
- Tests excluded from strict mode via `[[tool.mypy.overrides]]`

**Fixes applied:**
- `loader.py`: `re.Match` → `re.Match[str]` (generic type parameter)
- `history_sqlite.py`: `list()` conversion for `execute_fetchall()` return type, explicit casts for SQLite row values

### 6. App Wiring — DI via `app.state`

**`src/aegis_qa/api/app.py`** (refactored):
- `create_app()` loads config and creates history backend (SqliteHistory by default, InMemoryHistory fallback)
- Stores on `app.state.config` and `app.state.history`
- Eliminated module-level `_history` singleton from `workflow_list.py`

**All route handlers** now access history via `request.app.state.history`:
- `GET /api/workflows/{name}/history` → `request.app.state.history.get_history(name)`
- `GET /api/history` → `request.app.state.history.get_recent()`
- `POST /api/workflows/{name}/run` → `PipelineRunner(config, history=request.app.state.history)`

**Test wiring**: Tests set `app.state.config` and `app.state.history = InMemoryHistory()` directly.

### Files Changed

| Status | File |
|--------|------|
| NEW | `src/aegis_qa/workflows/history_sqlite.py` |
| NEW | `src/aegis_qa/api/auth.py` |
| NEW | `tests/test_history.py` |
| NEW | `tests/test_auth.py` |
| MOD | `src/aegis_qa/config/models.py` |
| MOD | `src/aegis_qa/workflows/history.py` |
| MOD | `src/aegis_qa/workflows/history_sqlite.py` |
| MOD | `src/aegis_qa/api/app.py` |
| MOD | `src/aegis_qa/api/routes/workflows.py` |
| MOD | `src/aegis_qa/api/routes/workflow_list.py` |
| MOD | `src/aegis_qa/cli.py` |
| MOD | `src/aegis_qa/landing/index.html` |
| MOD | `src/aegis_qa/landing/styles.css` |
| MOD | `src/aegis_qa/landing/app.js` |
| MOD | `pyproject.toml` |
| MOD | `.aegis.yaml.example` |
| MOD | `src/aegis_qa/config/loader.py` |
| MOD | `tests/test_api.py` |
| MOD | `tests/test_cli.py` |
| MOD | `tests/test_integration.py` |
| MOD | `docs/phases/phase4.md` |
| MOD | `docs/roadmap.md` |

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation complete. All success criteria met:
- 154 tests pass (up from 126)
- 93.64% coverage (target was 85%)
- `--cov-fail-under=80` enforced
- SQLite history persists via `aiosqlite` with retention pruning
- `InMemoryHistory` and `SqliteHistory` both pass the same interface tests
- `GET /api/history` returns recent runs (no route conflict)
- API key auth blocks unauthorized POST with 401, disabled when no key configured
- Landing page shows "Recent Runs" with live data
- `aegis config validate` catches missing services, unknown step types, invalid URLs
- `mypy --strict src/` passes clean
- `ruff check .` passes clean
- All existing tests still pass (updated for `app.state` DI pattern)

### Reviewer
**Action:** REQUEST_CHANGES

The implementation is close, but I found two blocking issues against the Phase 4 success criteria.

1. **SQLite retention pruning does not cascade-delete step rows**
   - In `src/aegis_qa/workflows/history_sqlite.py`, `PRAGMA foreign_keys = ON` is only executed inside `_ensure_tables()` while `self._initialized` is false.
   - Because each method call opens a new SQLite connection, later connections skip `_ensure_tables()` and run with `foreign_keys=OFF`.
   - Result: retention deletes old `workflow_runs`, but related `step_runs` rows are left orphaned, so the claimed `ON DELETE CASCADE` cleanup does not actually hold.
   - Repro (verified locally): with `max_records=1`, after recording two runs for one workflow → `workflow_runs=1`, `step_runs=2`.

2. **`aegis config validate` does not gracefully handle malformed YAML**
   - `config_validate()` in `src/aegis_qa/cli.py` catches `FileNotFoundError` and `ValueError`, but malformed YAML raises `yaml.ScannerError` from `load_config()` and bubbles up as a full traceback.
   - This violates the success criterion that config validation should catch YAML parsing issues with clear validation output.
   - Repro (verified locally): `aegis config validate --path bad.yaml` with malformed YAML prints a stack trace instead of a clean red validation message.

Please fix both and add tests that would fail on these regressions:
- a SQLite retention test that asserts step rows are also pruned (or otherwise guaranteed consistent),
- a CLI validation test for malformed YAML that asserts clean error handling (no raw traceback).

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Both issues fixed with regression tests:

1. **SQLite FK cascade fix:** Extracted `_init_connection()` from `_ensure_tables()`. Now `PRAGMA foreign_keys = ON` runs on every connection open, not just the first. Tables still only created once (via `_initialized` flag). Added `test_retention_pruning_cascades_step_rows` that directly queries `step_runs` count after pruning — asserts only the surviving run's steps remain.

2. **Malformed YAML handling:** Added `except yaml.YAMLError` catch before the `ValueError` catch in `config_validate()`. Outputs `"YAML parsing failed: {exc}"` with red styling and exit code 1. Added `test_validate_malformed_yaml` that writes broken YAML to a temp file, invokes `config validate --path`, and asserts clean error output with no traceback.

Verified: 156 tests pass, 93.67% coverage, ruff clean, mypy strict clean.

### Reviewer
**Action:** APPROVE

Implementation approved.

Both Round 1 blockers are resolved:
1. SQLite retention pruning now preserves referential integrity (per-connection foreign key enablement + regression coverage on step-row pruning).
2. `aegis config validate` now handles malformed YAML with clean validation output and exit code 1 (no raw traceback path), with regression coverage.

Verification performed:
- Targeted repros for both prior failures now pass.
- `pytest -q`: 156 passed, 93.67% coverage.
- `ruff check .`: clean.
- `mypy src`: clean.

No further blocking implementation changes required.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
