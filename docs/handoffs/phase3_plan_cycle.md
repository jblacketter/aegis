# Handoff: Phase 3 (Workflow Engine Hardening & Test Coverage) — Plan Review

**Phase:** phase3
**Type:** plan
**Date:** 2026-02-25
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase3.md`

## Plan Summary

Phase 3 hardens the Aegis workflow engine and fills the test coverage gap. Three pillars:

1. **Workflow Engine Hardening** — Retry with exponential backoff, parallel step execution via `asyncio.gather()`, per-step timeout, richer condition expressions (`on_success`, `on_failure`, `always`), VerifyStep real implementation, and in-memory execution history.

2. **Test Coverage Uplift** — CLI tests (0% → >90%), integration tests (new), base step helper tests (49% → >90%), coverage threshold enforcement (`--cov-fail-under=80`). Overall target: 85%+ (up from 70%).

3. **API Completeness** — `GET /api/workflows` and `GET /api/workflows/{name}` endpoints so the landing page can fetch live workflow data instead of using hardcoded JS. `GET /api/workflows/{name}/history` for execution records.

### Key Design Decisions

- **Retry config on `WorkflowStepDef`:** `retries`, `retry_delay`, `timeout` fields. Exponential backoff: `2^attempt * retry_delay`. Retry is opt-in (default 0 retries).
- **Parallel batching:** Consecutive `parallel: true` steps are grouped and run via `asyncio.gather()`. Non-parallel steps flush the batch. Context is merged after batch completion.
- **Condition evaluator:** Dict of lambda functions replaces the if/elif chain. Extensible for future conditions.
- **Execution history is in-memory only:** No database or file persistence in Phase 3. Keeps scope tight. Persistence is Phase 4+.
- **VerifyStep calls qaagent:** POST to qaagent's runs endpoint with a `verify_only` flag. Gracefully fails if qaagent doesn't support it yet.

### Files: 4 new, 11 modified

See `docs/phases/phase3.md` for the full file list and technical approach.

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 3 plan submitted for review. The plan balances three goals:
- **Technical depth** — retry, parallelism, and history make the workflow engine production-worthy
- **QA credibility** — a QA engineer's portfolio with 0% CLI test coverage is a bad look; this fixes it
- **Portfolio value** — live workflow data on the landing page makes the demo more dynamic

All design decisions are documented. No open questions.

### Reviewer
**Action:** REQUEST_CHANGES

Strong phase direction overall, but I see three blocking planning gaps that should be resolved before implementation:

1. **Retry default is internally inconsistent**
   - `docs/phases/phase3.md` currently says both:
     - In Scope: "Default: 3 retries, exponential backoff"
     - Technical Approach / model snippet: `retries: int = 0` (opt-in retry)
   - The cycle summary also describes retry as opt-in default 0.
   - Please pick one default behavior and align Scope, Technical Approach, and Success Criteria.

2. **Retry/timeout placement conflicts with the current step architecture**
   - The plan says "Implement retry in `BaseStep.execute()`", but `BaseStep.execute()` is abstract in current code.
   - Current concrete steps catch `Exception` and return failed `StepResult` objects, which means exception-based retry logic will not trigger unless execution flow is redesigned.
   - Please choose and document one concrete mechanism (for example: runner-level retry/timeout around step execution with explicit retriable classification, or step-level refactor that removes broad catches where retry should apply).

3. **Roadmap mismatch on Phase 3 deliverables**
   - `docs/roadmap.md` Phase 3 still lists "workflow execution history and persistence" and "webhook triggers".
   - This plan explicitly defers persistence and webhooks to Phase 4+.
   - Please reconcile the roadmap and phase plan so scope is unambiguous.

Once these are resolved, this is likely ready for approval quickly.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

All three issues addressed:

1. **Retry default aligned:** Fixed the Scope section — now says "Opt-in: 0 retries by default" matching the Technical Approach model (`retries: int = 0`). No ambiguity.

2. **Retry/timeout moved to runner-level:** The plan now clearly states retry and timeout are implemented in `PipelineRunner`, not `BaseStep`. Since `BaseStep.execute()` is abstract and concrete steps return failed `StepResult` objects (rather than raising exceptions), the runner checks `step_result.success` to decide retry. Timeout uses `asyncio.wait_for()` around the step call. The Files table updated accordingly — `base.py` no longer listed for retry changes; `pipeline.py` now explicitly owns retry/timeout.

3. **Roadmap reconciled:** `docs/roadmap.md` Phase 3 updated to match the actual plan (in-memory history only, no persistence, no webhooks). Deferred items explicitly moved to Phase 4 deliverables.

### Reviewer
**Action:** APPROVE

Plan approved.

All Round 1 blocking items are resolved:
1. Retry default is now internally consistent (opt-in, `retries=0` by default).
2. Retry/timeout ownership is now explicit and architecture-aligned (runner-level in `PipelineRunner`, with `asyncio.wait_for()` and retry decisions based on `StepResult.success`).
3. Roadmap and phase scope are reconciled (persistence and webhook triggers deferred to Phase 4).

No further blocking planning changes required.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
