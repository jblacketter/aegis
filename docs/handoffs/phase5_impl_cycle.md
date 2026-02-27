# Handoff: Phase 5 (Workflow Events & Tool Suite Expansion) — Implementation Review

**Phase:** phase5
**Type:** impl
**Date:** 2026-02-27
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase5.md`
- Plan review: `docs/handoffs/phase5_plan_cycle.md` (approved Round 2)

## Implementation Summary

Phase 5 implements all six deliverables from the approved plan. 189 tests pass, 93.59% coverage, ruff clean, mypy strict clean.

### 1. Workflow Event System

**Event types** (`src/aegis_qa/events/emitter.py` — NEW):
- `WorkflowEvent` dataclass with `event_type`, `timestamp`, `workflow_name`, `data`
- `EventListener` protocol with `on_event()` method
- `EventEmitter` class dispatches events to registered listeners with `try/except` per listener
- `create_cli_emitter(config)` helper returns `EventEmitter | None` for CLI usage

**Event log** (`src/aegis_qa/events/log.py` — NEW):
- `EventLog` implements `EventListener` protocol
- Bounded `deque` with configurable `max_size` (default 100)
- `get_recent(limit, event_type)` with optional type filter, returns most recent first
- Thread-safe via `asyncio.Lock`

**Pipeline integration** (`src/aegis_qa/workflows/pipeline.py` — MODIFIED):
- `PipelineRunner.__init__()` accepts optional `emitter: EventEmitter | None`
- Emits `workflow.started` at pipeline start (with `step_count`)
- Emits `step.completed` after each step (with `step_type`, `service`, `success`, `duration_ms`)
- Emits `failure.detected` on first failure (with `step_type`, `service`, `error`)
- Emits `workflow.completed` at pipeline end (with `success`, `total_duration_ms`, `steps_passed`, `steps_failed`)
- `_emit()` helper is no-op when emitter is None — all existing tests work unchanged

### 2. Webhook Delivery

**Webhook listener** (`src/aegis_qa/events/webhook.py` — NEW):
- `WebhookListener` implements `EventListener` protocol
- **Exact-match only** plus `"*"` wildcard — no glob or prefix patterns
- Fire-and-forget via `asyncio.create_task()` with `name=f"webhook-{wh.url}"`
- `_deliver()` wraps entire body in `try/except Exception` with `logger.exception()` — no unobserved task exceptions
- Task references stored in `self._pending: set[asyncio.Task]` with `add_done_callback(discard)` to prevent GC
- HMAC-SHA256 signature via `X-Aegis-Signature` header when `secret` is configured
- JSON payload includes `event_type`, `timestamp`, `workflow_name`, `data`

**Config** (`src/aegis_qa/config/models.py` — MODIFIED):
- `WebhookConfig(url, events, secret)` Pydantic model
- `AegisConfig.webhooks: list[WebhookConfig]` (default empty)
- `AegisConfig.event_log_size: int = 100`

### 3. Report Step Type

**Report step** (`src/aegis_qa/workflows/steps/report.py` — NEW):
- `ReportStep` extends `BaseStep`, registered as `"report"` in `STEP_REGISTRY`
- Aggregates prior step results: total, passed, failed, skipped, total_duration_ms
- Returns structured report in `StepResult.data` — pure context aggregation, no external calls

### 4. Event API

**Endpoint** (`src/aegis_qa/api/routes/workflow_list.py` — MODIFIED):
- `GET /api/events` with query params `?limit=20&event_type=workflow.completed`
- Returns JSON array of event objects from `app.state.event_log`

**App wiring** (`src/aegis_qa/api/app.py` — MODIFIED):
- `create_app()` creates `EventLog`, `EventEmitter`, optionally `WebhookListener`
- Stores on `app.state.event_log` and `app.state.emitter`
- `POST /api/workflows/{name}/run` passes `emitter` to `PipelineRunner`

### 5. qaagent Decomposition Analysis

**Document** (`docs/decomposition.md` — NEW):
- Analyzes qaagent's four domains (route discovery, risk analysis, test generation, orchestration)
- Proposes extraction order: discovery first (most self-contained), risk analyzer second, test generator third
- API contracts for each proposed standalone service
- Risk assessment and migration path

### 6. Landing Page Updates

**Recent Events section** (`src/aegis_qa/landing/index.html`, `app.js`, `styles.css` — MODIFIED):
- New "Recent Events" section showing last 5 events from `GET /api/events`
- Event type, workflow name, timestamp, and pass/fail icon
- Graceful fallback when API is offline

**Architecture diagram** (`src/aegis_qa/landing/index.html` — MODIFIED):
- Updated SVG to include "External Systems" box (GitHub, Slack, CI/CD) with webhook arrow
- Added "Event Log" box with events arrow
- Expanded viewBox to accommodate new elements

### 7. CLI Integration

**CLI wiring** (`src/aegis_qa/cli.py` — MODIFIED):
- `aegis run` creates emitter via `create_cli_emitter(config)` — webhooks only, no event log
- Works unchanged when no webhooks configured (emitter=None)
- `aegis config validate` now validates webhook URLs and warns on unrecognized event types

### Files Changed

| Status | File |
|--------|------|
| NEW | `src/aegis_qa/events/__init__.py` |
| NEW | `src/aegis_qa/events/emitter.py` |
| NEW | `src/aegis_qa/events/log.py` |
| NEW | `src/aegis_qa/events/webhook.py` |
| NEW | `src/aegis_qa/workflows/steps/report.py` |
| NEW | `tests/test_events.py` |
| NEW | `tests/test_report_step.py` |
| NEW | `docs/decomposition.md` |
| MOD | `src/aegis_qa/config/models.py` |
| MOD | `src/aegis_qa/workflows/pipeline.py` |
| MOD | `src/aegis_qa/workflows/steps/__init__.py` |
| MOD | `src/aegis_qa/api/app.py` |
| MOD | `src/aegis_qa/api/routes/workflow_list.py` |
| MOD | `src/aegis_qa/api/routes/workflows.py` |
| MOD | `src/aegis_qa/cli.py` |
| MOD | `src/aegis_qa/landing/index.html` |
| MOD | `src/aegis_qa/landing/app.js` |
| MOD | `src/aegis_qa/landing/styles.css` |
| MOD | `.aegis.yaml.example` |
| MOD | `tests/test_api.py` |
| MOD | `tests/test_integration.py` |
| MOD | `tests/test_cli.py` |
| MOD | `docs/phases/phase5.md` |
| MOD | `docs/roadmap.md` |

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation complete. All success criteria met:
- 189 tests pass (up from 156)
- 93.59% coverage (target was 85%)
- `PipelineRunner` emits all four event types at pipeline lifecycle points
- `EventLog` stores events in bounded ring buffer with type filter
- `GET /api/events` returns recent events with `?event_type=` filter
- Webhook delivery is exact-match only plus `"*"`, fire-and-forget with full exception handling
- Webhook task references stored in `_pending` set to prevent GC
- HMAC-SHA256 signature sent when secret configured
- `ReportStep` aggregates prior step results into structured summary
- `aegis config validate` checks webhook URLs and warns on unrecognized event types
- CLI `aegis run` sends webhooks when configured, works unchanged otherwise
- Landing page shows "Recent Events" section with live data
- Architecture diagram updated with event flow arrows
- `docs/decomposition.md` documents qaagent extraction strategy
- All existing tests still pass (updated for emitter/event_log in app.state)
- `mypy --strict src/` passes clean
- `ruff check .` passes clean

### Reviewer
**Action:** REQUEST_CHANGES

Implementation is close, but I found one blocking correctness issue:

1. **HMAC signature is computed over different bytes than the actual webhook request body**
   - In `src/aegis_qa/events/webhook.py`, signature generation uses `json.dumps(payload, sort_keys=True)` for HMAC input.
   - The HTTP request is sent with `httpx.post(..., json=payload)`, which serializes JSON differently (different key order and compact separators).
   - Result: `X-Aegis-Signature` does not match the real transmitted body bytes, so standards-based receiver verification over raw request body will fail.

   Repro (verified locally):
   - Signature input string differs from `httpx.Request(..., json=payload).content`.
   - Corresponding SHA256 HMAC hashes differ.

Please fix by signing the exact bytes that are sent on the wire, and add a regression test that validates signature correctness against the transmitted body representation.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

HMAC signature fix applied with regression test:

1. **Fix:** `_deliver()` in `src/aegis_qa/events/webhook.py` now serializes the payload to bytes once via `json.dumps(payload).encode()`, computes HMAC over those exact bytes, then sends them via `content=body_bytes` (not `json=payload`). This guarantees the signature matches the transmitted body byte-for-byte.

2. **Regression test:** Added `test_hmac_signature_matches_transmitted_body` in `tests/test_events.py`. It captures the `content` bytes from the mock `post()` call, recomputes HMAC-SHA256 independently, and asserts the signatures match.

3. **Updated existing test:** `test_exact_match_delivers` now parses the `content` bytes (not `json`) since the API changed from `json=` to `content=`.

Verified: 190 tests pass, 93.59% coverage, ruff clean, mypy strict clean.

### Reviewer
**Action:** APPROVE

Round 2 changes resolve the blocking HMAC issue.

Validation performed:
- Verified `src/aegis_qa/events/webhook.py` signs the exact transmitted bytes (`body_bytes`) and sends those same bytes via `content=`.
- Verified regression coverage in `tests/test_events.py` (`test_hmac_signature_matches_transmitted_body`) checks signature against transmitted body bytes.
- Ran quality gates:
  - `pytest -q` → 190 passed, 93.59% coverage
  - `ruff check .` → clean
  - `mypy src` → clean

No remaining blocking issues found. Approving phase 5 implementation.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
