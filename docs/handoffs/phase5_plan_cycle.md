# Handoff: Phase 5 (Workflow Events & Tool Suite Expansion) — Plan Review

**Phase:** phase5
**Type:** plan
**Date:** 2026-02-27
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase5.md`

## Plan Summary

Phase 5 adds a workflow event system with external webhook delivery, expanding Aegis from an internal orchestrator to a CI/CD-integrated platform. Six deliverables:

1. **Workflow Event System** — `EventEmitter` class emits typed events (`workflow.started`, `step.completed`, `workflow.completed`, `failure.detected`) at pipeline lifecycle points. `EventListener` protocol for extensible consumption.

2. **Webhook Delivery** — Configurable webhook URLs in `.aegis.yaml`. Fire-and-forget async POST with optional HMAC-SHA256 signing. Non-blocking — failures logged, not raised.

3. **Report Step Type** — New `ReportStep` that aggregates prior step results into summary stats. Pure context aggregation, no external calls. Final step in a pipeline.

4. **Event API** — `GET /api/events` returns recent events from an in-memory ring buffer. Optional `?event_type=` filter.

5. **qaagent Decomposition Analysis** — Documentation analyzing qaagent's modular structure and proposing extraction order (route discovery first, then risk analyzer, then test generator). No code changes to qaagent.

6. **Landing Page Updates** — "Recent Events" section showing live event feed. Updated architecture diagram with event flow arrows.

### Key Design Decisions

- **Fire-and-forget webhooks:** Delivery failures don't block pipelines. This is the right tradeoff for v1 — guaranteed delivery adds complexity for limited portfolio benefit.
- **In-memory event log:** Bounded `deque` (default 100 events). No persistence needed — events are ephemeral observability, not durable history (that's what SQLite history is for).
- **Emitter is optional:** `PipelineRunner` accepts `emitter=None` by default. Existing tests and CLI usage work unchanged.
- **Report step is service-agnostic:** It reads from context, not external APIs. Any service entry works.

### Files: 8 new, 16 modified

See `docs/phases/phase5.md` for the full file list and technical approach.

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 5 plan submitted. This phase pivots Aegis from an internal orchestrator to a CI/CD-integrated platform:
- **External integration** — webhook delivery to GitHub, Slack, monitoring
- **Observability** — event log + API + landing page feed
- **Extensibility** — new step type pattern (ReportStep) + listener protocol
- **Architecture story** — decomposition analysis tells the microservices narrative

All design decisions documented. No new dependencies needed (httpx already available for webhook delivery).

### Reviewer
**Action:** REQUEST_CHANGES

The direction is strong, but I see three blocking planning gaps that should be resolved before implementation:

1. **Webhook event matching semantics are ambiguous**
   - The plan says `webhooks.events` is a list of "event type patterns".
   - The technical snippet currently matches only exact event names plus `"*"`.
   - Please choose one explicit matching model (exact-only, wildcard/glob, or prefix) and define it in Scope + Technical Approach + tests.

2. **Fire-and-forget failure handling is underspecified**
   - Success criteria says webhook failures are logged and not raised.
   - Current design uses `asyncio.create_task()` from listener callbacks; without an explicit exception-handling strategy inside spawned tasks, this can produce unobserved task exceptions rather than structured logging.
   - Please specify the exact failure-handling approach for background delivery tasks (where exceptions are caught/logged and how task lifecycle is managed).

3. **CLI event/webhook behavior is not defined**
   - `create_app()` wiring gives API-triggered runs an emitter, but `aegis run` uses `PipelineRunner(config)` directly today.
   - Please decide and document whether CLI-triggered workflow runs should emit events and send webhooks, and if yes, the wiring approach. If no, call it out as explicit scope behavior to avoid confusion.

Once these are clarified, this should be close to approval.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

All three blocking gaps resolved in `docs/phases/phase5.md`:

1. **Webhook event matching: exact-match only + `"*"`**
   - Removed "patterns" language from Scope. The `events` list contains literal event type strings (e.g., `["workflow.completed", "failure.detected"]`) or `["*"]` for all events.
   - No glob, prefix, or regex — simplest model, no ambiguity.
   - `aegis config validate` will warn on unrecognized event type strings.
   - Added success criterion: "test confirms non-matching events are not delivered."

2. **Fire-and-forget failure handling: fully specified**
   - `_deliver()` wraps its entire body in `try/except Exception` with `logger.exception()`. No unobserved task exceptions.
   - Tasks created with descriptive `name=f"webhook-{wh.url}"` for debuggability.
   - Task references stored in `self._pending: set[asyncio.Task]` with `add_done_callback(self._pending.discard)` to prevent GC of running tasks.
   - Updated Technical Approach code snippet to show the complete pattern.

3. **CLI event/webhook behavior: defined**
   - `aegis run` creates its own `EventEmitter` with `WebhookListener` when webhooks are configured. No `EventLog` — the ring buffer is only useful for the API.
   - Helper function `create_cli_emitter(config) -> EventEmitter | None` in `emitter.py` keeps CLI wiring simple.
   - Added CLI wiring diagram to Technical Approach.
   - Added `src/aegis_qa/cli.py` to Modified Files list.
   - Added two CLI-specific success criteria.

### Reviewer
**Action:** APPROVE

Plan approved.

All Round 1 blocking gaps are resolved:
1. Webhook matching semantics are now explicit and testable (exact-match only plus `"*"`).
2. Fire-and-forget failure handling is concretely specified (exceptions caught/logged inside `_deliver()`, task references retained in `_pending`).
3. CLI behavior is explicitly defined (`aegis run` uses `create_cli_emitter()` for webhook delivery, with no CLI event log).

No further blocking planning changes required.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
