# Phase 3: Workflow Engine Hardening & Test Coverage

## Status
- [x] Planning
- [x] In Review
- [x] Approved
- [x] Implementation
- [ ] Implementation Review
- [ ] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human

## Summary
**What:** Harden the workflow engine with retry logic, parallel step execution, and execution history. Fill the critical test coverage gap (CLI at 0%, integration tests missing). Add API endpoints the landing page needs to stop using hardcoded data.
**Why:** Aegis positions Jack as a QA engineering leader. A QA leader's own tooling having 0% CLI test coverage and a stubbed-out verification step undermines credibility. Meanwhile, the workflow engine — the core value proposition — lacks retry, parallelism, and execution history that any real orchestration layer needs. Phase 3 closes these gaps: the engine becomes production-worthy and the test suite proves it.
**Depends on:** Phase 2 (complete)

## Scope

### In Scope

#### 1. Workflow Engine Hardening
- **Retry with backoff:** Configurable retry count and backoff strategy per step. Opt-in: 0 retries by default. Step-level override via `WorkflowStepDef` fields (`retries`, `retry_delay`).
- **Parallel step execution:** Steps can declare `parallel: true` in config. Parallel steps run concurrently via `asyncio.gather()`. Sequential remains the default.
- **Step timeout:** Per-step timeout config (default 30s). Raises a clear error on timeout, distinct from connection errors.
- **VerifyStep implementation:** Replace the placeholder stub with a real implementation that re-runs a subset of tests to confirm fixes (calls `POST /api/runs` with a `verify_only` flag on qaagent).
- **Execution history:** In-memory execution log with timestamps, step durations, and results. Exposed via `GET /api/workflows/{name}/history`. Not persisted to disk in this phase — persistence is Phase 4+.
- **Richer condition expressions:** Support `on_success`, `on_failure`, `always` in addition to `has_failures`. Clean up the `_should_skip` logic.

#### 2. Test Coverage Uplift
- **CLI tests:** Unit tests for all 4 CLI commands (`status`, `serve`, `run`, `config show`) using `typer.testing.CliRunner`. Target: CLI module >90% coverage.
- **Integration tests:** End-to-end tests that start the FastAPI app via `TestClient`, hit API endpoints, and verify the full request/response cycle including error paths.
- **Base step tests:** Direct tests for `_get()` and `_post()` in `workflows/steps/base.py` with httpx mocking (not just mocking them away). Target: base module >90%.
- **Coverage threshold:** Add `--cov-fail-under=80` to pytest config. Enforce in CI.
- **Overall target:** 85%+ line coverage (up from 70%).

#### 3. API Completeness
- **`GET /api/workflows`:** List all configured workflows with their step definitions. Replaces hardcoded `STATIC_WORKFLOWS` in the landing page JS.
- **`GET /api/workflows/{name}`:** Get a single workflow definition (steps, conditions, retry config).
- **Landing page update:** Update `app.js` to fetch workflow data from `/api/workflows` when the API is live, falling back to static data when offline.

### Out of Scope
- Persistent execution history (disk/database) — Phase 4+
- Webhook/event triggers for workflows — Phase 4+
- Authentication / API keys on Aegis endpoints — Phase 4+
- Config validation command (`aegis config validate`) — nice-to-have, defer
- Mypy strict mode — Phase 4+
- Multi-Python-version CI matrix — not needed yet

## Technical Approach

### Retry Logic
Add retry fields to `WorkflowStepDef` in `config/models.py`:
```python
class WorkflowStepDef(BaseModel):
    type: str
    service: str
    condition: str | None = None
    parallel: bool = False
    retries: int = 0          # 0 = no retry
    retry_delay: float = 1.0  # seconds, base for exponential backoff
    timeout: float = 30.0     # seconds
```

Implement retry in `PipelineRunner` (runner-level), not in `BaseStep`. `BaseStep.execute()` is abstract and concrete steps catch exceptions broadly, returning failed `StepResult` objects — so retry must check `step_result.success` rather than catching exceptions. The runner wraps each `step.execute()` call: if the result is not successful and retries remain, it sleeps `2 ** attempt * retry_delay` seconds and re-invokes. Timeout uses `asyncio.wait_for()` around the step call, raising `asyncio.TimeoutError` which the runner catches and converts to a failed `StepResult`. All attempt results are captured in `StepResult.attempts` (new field).

### Parallel Execution
In `PipelineRunner.run()`, group consecutive steps that have `parallel: true` into batches. Run each batch with `asyncio.gather()`. Sequential steps flush the current batch and run alone. Context is merged after all parallel steps complete.

### Execution History
New module `workflows/history.py`:
```python
@dataclass
class ExecutionRecord:
    workflow_name: str
    started_at: datetime
    completed_at: datetime | None
    steps: list[StepRecord]
    success: bool

class ExecutionHistory:
    """In-memory execution log. Thread-safe via asyncio lock."""
    _records: dict[str, list[ExecutionRecord]]  # keyed by workflow name
```

`PipelineRunner` writes to `ExecutionHistory` after each run. API endpoint reads from it.

### Condition Expressions
Replace the string-match `if condition == "has_failures"` with a small evaluator:
```python
CONDITIONS = {
    "has_failures": lambda ctx: any(r.has_failures for r in ctx.values() if isinstance(r, StepResult)),
    "on_success": lambda ctx: all(r.success for r in ctx.values() if isinstance(r, StepResult)),
    "on_failure": lambda ctx: any(not r.success for r in ctx.values() if isinstance(r, StepResult)),
    "always": lambda ctx: True,
}
```

### CLI Tests
Use `typer.testing.CliRunner` with mocked config/registry/runner. Test all 4 commands plus error paths (missing config, unknown workflow, service down).

### Integration Tests
New `tests/test_integration.py`. Use `fastapi.testclient.TestClient` against the real `create_app()` with mocked downstream services. Test the full lifecycle: list services → run workflow → check history.

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `src/aegis_qa/workflows/history.py` | In-memory execution history |
| `src/aegis_qa/api/routes/workflow_list.py` | GET /api/workflows, GET /api/workflows/{name}, GET /api/workflows/{name}/history |
| `tests/test_cli.py` | CLI unit tests |
| `tests/test_integration.py` | End-to-end API integration tests |

### Modified Files
| File | Changes |
|------|---------|
| `src/aegis_qa/config/models.py` | Add `parallel`, `retries`, `retry_delay`, `timeout` to `WorkflowStepDef` |
| `src/aegis_qa/workflows/models.py` | Add `attempts` to `StepResult`, `duration_ms` field |
| `src/aegis_qa/workflows/steps/base.py` | No retry changes (stays abstract); only touched if helper improvements needed |
| `src/aegis_qa/workflows/steps/verify.py` | Real implementation (call qaagent verify endpoint) |
| `src/aegis_qa/workflows/pipeline.py` | Retry/timeout logic (runner-level), parallel batch execution, condition evaluator, history recording |
| `src/aegis_qa/api/app.py` | Register new workflow list routes |
| `src/aegis_qa/landing/app.js` | Fetch from `/api/workflows` with static fallback |
| `pyproject.toml` | Add `--cov-fail-under=80` to pytest config |
| `.aegis.yaml.example` | Show retry/parallel config options |
| `tests/test_workflows.py` | Tests for retry, parallel, conditions, history |
| `tests/test_api.py` | Tests for new workflow list/history endpoints |

## Success Criteria
- [ ] Retry logic works: steps retry N times with exponential backoff on failure
- [ ] Parallel steps run concurrently via `asyncio.gather()`
- [ ] Per-step timeout raises a clear timeout error
- [ ] `VerifyStep` makes a real HTTP call (mocked in tests)
- [ ] Condition expressions `has_failures`, `on_success`, `on_failure`, `always` all work
- [ ] `GET /api/workflows` returns configured workflow definitions
- [ ] `GET /api/workflows/{name}` returns a single workflow definition
- [ ] `GET /api/workflows/{name}/history` returns execution records
- [ ] Landing page fetches live workflow data from API when available
- [ ] CLI tests cover all 4 commands with >90% CLI module coverage
- [ ] Integration tests exercise the full API lifecycle
- [ ] `base.py` step helpers tested directly at >90%
- [ ] Overall project coverage ≥85% (up from 70%)
- [ ] `--cov-fail-under=80` enforced in CI
- [ ] All existing tests still pass
- [ ] `ruff check` and `mypy` still pass clean

## Open Questions
None — all decisions are documented above.

## Risks
- **Retry + parallel interaction:** Retries inside parallel steps could cause cascading delays. Mitigation: timeout acts as a hard ceiling per step regardless of retries.
- **Coverage target ambition:** 85% is a 15-point jump. Mitigation: CLI and integration tests alone should account for most of the gap since cli.py (0%) and app.py (0%) are the biggest holes.
- **VerifyStep assumes qaagent API:** The verify endpoint on qaagent may not exist yet. Mitigation: step is fully mocked in tests; implementation just calls POST with a verify flag. Works when qaagent adds the endpoint, gracefully fails until then.
