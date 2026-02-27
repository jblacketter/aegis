# Handoff: Phase 3 (Workflow Engine Hardening & Test Coverage) — Implementation Review

**Phase:** phase3
**Type:** impl
**Date:** 2026-02-27
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase3.md`
- Plan review: `docs/handoffs/phase3_plan_cycle.md` (approved Round 2)

## Implementation Summary

Phase 3 implements all three pillars from the approved plan. 125 tests pass, 94% coverage, ruff and mypy clean.

### 1. Workflow Engine Hardening

**Config model** (`src/aegis_qa/config/models.py`):
- Added `parallel`, `retries`, `retry_delay`, `timeout` fields to `WorkflowStepDef`

**Workflow models** (`src/aegis_qa/workflows/models.py`):
- Added `duration_ms` and `attempts` fields to `StepResult`
- Updated `to_dict()` to include new fields

**Execution history** (`src/aegis_qa/workflows/history.py` — NEW):
- `StepRecord`, `ExecutionRecord`, `ExecutionHistory` dataclasses
- In-memory storage with asyncio lock for thread safety
- `record()`, `get_history()`, `get_all()` methods

**Pipeline runner** (`src/aegis_qa/workflows/pipeline.py` — major rewrite):
- **Runner-level retry**: Wraps `step.execute()` with retry logic checking `step_result.success`, exponential backoff (`2^attempt * retry_delay`)
- **Runner-level timeout**: `asyncio.wait_for()` around step execution, converts `TimeoutError` to failed `StepResult`
- **Parallel batching**: Consecutive `parallel: true` steps grouped and run via `asyncio.gather()`. Sequential steps flush the batch.
- **Condition evaluator**: Dict-based `CONDITIONS` map replaces the string-match if/elif chain. Supports `has_failures`, `on_success`, `on_failure`, `always`.
- **History recording**: Writes `ExecutionRecord` to injected `ExecutionHistory` after each run

**VerifyStep** (`src/aegis_qa/workflows/steps/verify.py`):
- Replaced placeholder stub with real implementation: POST to `/api/runs` with `verify_only: true`

### 2. Test Coverage Uplift

**CLI tests** (`tests/test_cli.py` — NEW, 14 tests):
- All 4 commands tested: `status`, `serve`, `run`, `config show`
- Error paths: missing config, unknown workflow, invalid config, skipped steps, error steps

**Integration tests** (`tests/test_integration.py` — NEW, 8 tests):
- Full API lifecycle: health check → list services → list workflows → run workflow → check portfolio
- Error paths: unknown service health, unknown workflow, unknown workflow history

**Base step tests** (`tests/test_base_step.py` — NEW, 12 tests):
- Direct tests for `_get()` and `_post()` with httpx mocking (MagicMock for sync response methods)
- Tests for `__init__`, `_headers()`, API key from env, HTTP errors

**Workflow tests** (`tests/test_workflows.py` — updated, 31 tests):
- New: retry (3 tests), timeout (1 test), parallel (2 tests), execution history (3 tests)
- New: condition evaluator tests for `on_success`, `on_failure`, `always`
- Updated VerifyStep tests for real implementation

**API tests** (`tests/test_api.py` — updated, 13 tests):
- New: workflow list, workflow detail, workflow history, workflow not found

**Coverage**: 94.01% overall (target was 85%), `--cov-fail-under=80` enforced

### 3. API Completeness

**Workflow list routes** (`src/aegis_qa/api/routes/workflow_list.py` — NEW):
- `GET /api/workflows` — list all configured workflows with step definitions
- `GET /api/workflows/{name}` — get a single workflow with full retry/parallel config
- `GET /api/workflows/{name}/history` — get execution records

**App factory** (`src/aegis_qa/api/app.py`):
- Registered `workflow_list.router` before `workflows.router` (GET before POST)

**Landing page** (`src/aegis_qa/landing/app.js`):
- `init()` now fetches `/api/workflows` alongside portfolio and services
- `buildWorkflowMap()` converts API response to keyed map for rendering
- Falls back to `STATIC_WORKFLOWS` when API unavailable

### Config & Build

- `.aegis.yaml.example`: Added retry/parallel/timeout fields with comments
- `pyproject.toml`: Added `--cov=aegis_qa --cov-fail-under=80` to pytest addopts
- `docs/roadmap.md`: Phase 3 aligned, deferred items moved to Phase 4

### Files Changed

| Status | File |
|--------|------|
| NEW | `src/aegis_qa/workflows/history.py` |
| NEW | `src/aegis_qa/api/routes/workflow_list.py` |
| NEW | `tests/test_cli.py` |
| NEW | `tests/test_integration.py` |
| NEW | `tests/test_base_step.py` |
| MOD | `src/aegis_qa/config/models.py` |
| MOD | `src/aegis_qa/workflows/models.py` |
| MOD | `src/aegis_qa/workflows/pipeline.py` |
| MOD | `src/aegis_qa/workflows/steps/verify.py` |
| MOD | `src/aegis_qa/api/app.py` |
| MOD | `src/aegis_qa/landing/app.js` |
| MOD | `pyproject.toml` |
| MOD | `.aegis.yaml.example` |
| MOD | `tests/test_workflows.py` |
| MOD | `tests/test_api.py` |
| MOD | `docs/phases/phase3.md` |
| MOD | `docs/roadmap.md` |

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation complete. All success criteria met:
- 125 tests pass (up from 68)
- 94% coverage (up from 70%, target was 85%)
- `--cov-fail-under=80` enforced
- Retry, parallel, timeout, conditions, history all working
- VerifyStep makes real HTTP calls
- 3 new API endpoints functional
- Landing page fetches live workflow data
- `ruff check` and `mypy` pass clean

### Reviewer
**Action:** REQUEST_CHANGES

Implementation is close, but there is one blocking behavior regression against the phase success criteria:

1. **Workflow history endpoint is effectively disconnected from workflow runs**
   - `src/aegis_qa/api/routes/workflow_list.py` defines a module-level `ExecutionHistory` singleton (`_history`).
   - `GET /api/workflows/{name}/history` reads from that singleton.
   - `POST /api/workflows/{name}/run` in `src/aegis_qa/api/routes/workflows.py` constructs `PipelineRunner(config)` **without** passing that shared history instance.
   - Result: successful runs are not recorded into the API-exposed history, so history stays empty even after runs.

   Repro (verified locally):
   - `POST /api/workflows/full_pipeline/run` → `200`, success `true`
   - `GET /api/workflows/full_pipeline/history` immediately after → `200`, `[]`

Please wire the run path to the same shared history instance used by `workflow_list.py`, and add an API/integration test that asserts history is non-empty after a successful run.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Fixed the history wiring issue:

1. **`src/aegis_qa/api/routes/workflows.py`** — `run_workflow()` now imports `get_history()` from `workflow_list` and passes it to `PipelineRunner(config, history=get_history())`. Runs are recorded to the shared singleton.

2. **`tests/test_integration.py`** — Added `test_run_then_history_non_empty` that:
   - Clears history
   - POSTs a workflow run
   - GETs `/api/workflows/full_pipeline/history`
   - Asserts exactly 1 record with the correct workflow name and success status

Verified: 126 tests pass, 94.17% coverage, ruff and mypy clean.

### Reviewer
**Action:** APPROVE

Implementation approved.

Round 1 blocking issue is resolved:
1. `POST /api/workflows/{name}/run` now passes the shared history instance (`get_history()`) into `PipelineRunner`, so runs are recorded to the same store used by `GET /api/workflows/{name}/history`.
2. Integration coverage now includes a regression test that runs a workflow and asserts non-empty history.

Verification performed:
- Direct API repro now returns a history record after a successful run.
- `pytest -q`: 126 passed, 94.17% coverage.
- `ruff check .`: clean.
- `mypy src`: clean.

No further blocking implementation changes required.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
