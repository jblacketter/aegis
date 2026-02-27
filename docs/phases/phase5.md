# Phase 5: Workflow Events & Tool Suite Expansion

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
**What:** Add a workflow event system with webhook delivery for CI/CD integration, a new `report` step type, and a qaagent decomposition analysis. Update the landing page with event activity.
**Why:** A production orchestration platform needs to communicate with external systems. Webhook triggers enable CI/CD integration (GitHub Actions, Slack, monitoring). The event system also powers the landing page event feed, making the portfolio demo tangible. The report step demonstrates how new tool capabilities extend the pipeline. The decomposition analysis documents the path from monolith to microservices — the kind of architectural thinking a QA lead brings to a team.
**Depends on:** Phase 4 (complete)

## Scope

### In Scope

#### 1. Workflow Event System
- **Event emitter:** New `EventEmitter` class in `src/aegis_qa/events/emitter.py`. Collects events during pipeline execution and dispatches them to registered listeners.
- **Event types:** `workflow.started`, `step.completed`, `workflow.completed`, `failure.detected`. Each event is a typed dataclass with timestamp, workflow name, and relevant payload.
- **Event log:** In-memory ring buffer (`EventLog`) stores the last N events (configurable via `event_log_size: int = 100` in config). Accessible via API.
- **Pipeline integration:** `PipelineRunner` accepts an optional `EventEmitter`. Emits events at: workflow start, after each step completes, workflow end, and on first failure detection.
- **CLI integration:** `aegis run` creates its own `EventEmitter` with a `WebhookListener` (from config webhooks) when webhooks are configured. No `EventLog` for CLI — the ring buffer is only useful for the API/landing page. This means CLI-triggered runs send webhooks but don't populate the in-memory event log. The wiring is a simple helper function `create_cli_emitter(config) -> EventEmitter | None` in `src/aegis_qa/events/emitter.py`.

#### 2. Webhook Delivery
- **Config:** New `webhooks` list in `AegisConfig`. Each entry: `url`, `events` (list of exact event type strings), `secret` (optional HMAC signing key, supports `${ENV_VAR}`).
- **Event matching:** **Exact-match only** plus the special value `"*"` (matches all events). No glob, prefix, or regex patterns. The `events` list contains literal event type strings (e.g., `["workflow.completed", "failure.detected"]`) or `["*"]` for all. This is the simplest model and avoids ambiguity. `aegis config validate` will warn on unrecognized event type strings.
- **Delivery:** Fire-and-forget async HTTP POST to webhook URLs. Non-blocking — delivery failures are logged but don't affect pipeline execution.
- **Failure handling:** Each `_deliver()` call wraps its entire body in `try/except Exception` with `logger.exception()`. Tasks are created with a descriptive name (`f"webhook-{wh.url}"`) for debuggability. No unobserved task exceptions — all errors are caught and logged inside the task. Task references are stored in a `set[asyncio.Task]` with a discard callback to prevent GC of running tasks.
- **Payload:** JSON body with `event_type`, `timestamp`, `data` (event-specific payload). Optional `X-Aegis-Signature` header when secret is configured (HMAC-SHA256 of body).
- **Listener:** `WebhookListener` class implements the event listener protocol. Registered in `create_app()` from config and in CLI `run` command.

#### 3. Report Step Type
- **New step:** `ReportStep` in `src/aegis_qa/workflows/steps/report.py`. Generates a structured JSON execution report from the current workflow context.
- **Output:** Collects all prior step results, computes summary stats (total/passed/failed/skipped, duration), and returns a report dict. Does not call external services — pure context aggregation.
- **Use case:** Final step in a pipeline. The report data can be consumed by webhook listeners, stored in history, or returned via API.
- **Registration:** Added to `STEP_REGISTRY` as `"report"`.

#### 4. Event API
- **`GET /api/events`** — Returns the most recent events from the in-memory log. Query params: `?limit=20&event_type=workflow.completed`.
- **Wiring:** `EventLog` stored on `app.state.event_log`. Routes access via `request.app.state.event_log`.

#### 5. qaagent Decomposition Analysis
- **Document:** `docs/decomposition.md` — Analyzes qaagent's modular structure and identifies extraction candidates (route discovery, risk analyzer, test generator).
- **Content:** Current architecture, proposed extraction order, API contracts for each standalone service, migration path, risk assessment.
- **Not code:** This deliverable is documentation only. Actual extraction happens in future phases.

#### 6. Landing Page Updates
- **Event activity section:** New "Recent Events" section showing the last 5 events from `GET /api/events`. Shows event type icon, workflow name, timestamp, and outcome.
- **Architecture diagram update:** Add event flow arrows showing webhook delivery path from Aegis to external systems.

### Out of Scope
- WebSocket real-time event streaming — future enhancement
- Actual qaagent decomposition / standalone service extraction — documented but deferred
- Event replay / guaranteed delivery — fire-and-forget is sufficient for v1
- Event filtering by workflow name in API — add if needed later
- External event ingestion (receiving webhooks) — Phase 6+

## Technical Approach

### Event System

**Event types:**
```python
@dataclass
class WorkflowEvent:
    event_type: str  # "workflow.started", "step.completed", etc.
    timestamp: datetime
    workflow_name: str
    data: dict[str, Any]

# Concrete event payloads:
# workflow.started: {"step_count": N}
# step.completed: {"step_type": str, "service": str, "success": bool, "duration_ms": float}
# workflow.completed: {"success": bool, "total_duration_ms": float, "steps_passed": N, "steps_failed": N}
# failure.detected: {"step_type": str, "service": str, "error": str}
```

**Event emitter:**
```python
class EventListener(Protocol):
    async def on_event(self, event: WorkflowEvent) -> None: ...

class EventEmitter:
    def __init__(self) -> None:
        self._listeners: list[EventListener] = []

    def add_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    async def emit(self, event: WorkflowEvent) -> None:
        for listener in self._listeners:
            try:
                await listener.on_event(event)
            except Exception:
                logger.exception("Event listener error")
```

**Event log (in-memory ring buffer):**
```python
class EventLog:
    def __init__(self, max_size: int = 100) -> None:
        self._events: deque[WorkflowEvent] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()

    async def on_event(self, event: WorkflowEvent) -> None:
        async with self._lock:
            self._events.append(event)

    async def get_recent(self, limit: int = 20, event_type: str | None = None) -> list[WorkflowEvent]: ...
```

**Pipeline integration (in `PipelineRunner.run()`):**
```python
# At start:
await self._emitter.emit(WorkflowEvent("workflow.started", ...))

# After each step:
await self._emitter.emit(WorkflowEvent("step.completed", ...))
if not step_result.success:
    await self._emitter.emit(WorkflowEvent("failure.detected", ...))

# At end:
await self._emitter.emit(WorkflowEvent("workflow.completed", ...))
```

### Webhook Delivery

**Config:**
```python
class WebhookConfig(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["workflow.completed"])
    secret: str = ""  # HMAC signing key, supports ${ENV_VAR}

class AegisConfig(BaseModel):
    # ... existing fields ...
    webhooks: list[WebhookConfig] = Field(default_factory=list)
    event_log_size: int = 100
```

**Webhook listener:**
```python
class WebhookListener:
    def __init__(self, webhooks: list[WebhookConfig]) -> None:
        self._webhooks = webhooks
        self._pending: set[asyncio.Task[None]] = set()  # prevent GC of running tasks

    async def on_event(self, event: WorkflowEvent) -> None:
        for wh in self._webhooks:
            if event.event_type in wh.events or "*" in wh.events:
                task = asyncio.create_task(
                    self._deliver(wh, event),
                    name=f"webhook-{wh.url}",
                )
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)

    async def _deliver(self, wh: WebhookConfig, event: WorkflowEvent) -> None:
        """Fire-and-forget delivery. All exceptions caught and logged — never unobserved."""
        try:
            payload = {"event_type": event.event_type, "timestamp": event.timestamp.isoformat(), "data": event.data}
            headers = {"Content-Type": "application/json"}
            if wh.secret:
                sig = hmac.new(wh.secret.encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
                headers["X-Aegis-Signature"] = sig
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(wh.url, json=payload, headers=headers)
        except Exception:
            logger.exception("Webhook delivery failed for %s (event: %s)", wh.url, event.event_type)
```

### Report Step

```python
class ReportStep(BaseStep):
    step_type = "report"

    async def execute(self, context: dict[str, Any]) -> StepResult:
        step_results = context.get("step_results", [])
        total = len(step_results)
        passed = sum(1 for r in step_results if r.success)
        failed = sum(1 for r in step_results if not r.success and not r.skipped)
        skipped = sum(1 for r in step_results if r.skipped)
        total_duration = sum(r.duration_ms or 0 for r in step_results)

        report = {
            "summary": {"total": total, "passed": passed, "failed": failed, "skipped": skipped},
            "total_duration_ms": total_duration,
            "steps": [{"step_type": r.step_type, "service": r.service, "success": r.success, ...} for r in step_results],
        }
        return StepResult(step_type="report", service=self.service_entry.name, success=True, data=report)
```

### App Wiring (API)

```
create_app()
  ├─ config = load_config()
  ├─ history = SqliteHistory(...)
  ├─ event_log = EventLog(config.event_log_size)
  ├─ emitter = EventEmitter()
  ├─ emitter.add_listener(event_log)          ← logs events
  ├─ emitter.add_listener(WebhookListener(config.webhooks))  ← delivers webhooks
  ├─ app.state.history = history
  ├─ app.state.event_log = event_log
  ├─ app.state.emitter = emitter
  │
  ├─ POST /api/workflows/{name}/run
  │   └─ PipelineRunner(config, history=..., emitter=...)
  │
  └─ GET /api/events
      └─ request.app.state.event_log.get_recent()
```

### CLI Wiring (`aegis run`)

```
aegis run <workflow>
  ├─ config = load_config()
  ├─ emitter = create_cli_emitter(config)  ← returns None if no webhooks configured
  │   └─ if config.webhooks:
  │       ├─ emitter = EventEmitter()
  │       └─ emitter.add_listener(WebhookListener(config.webhooks))
  │
  └─ PipelineRunner(config, emitter=emitter)
```

**Key difference:** CLI runs get webhook delivery but no `EventLog` (the ring buffer is only useful for the API's `GET /api/events` endpoint). This keeps CLI usage lightweight while still enabling CI/CD integration via webhooks.

**Helper function:**
```python
def create_cli_emitter(config: AegisConfig) -> EventEmitter | None:
    """Create an emitter for CLI usage — webhooks only, no event log."""
    if not config.webhooks:
        return None
    emitter = EventEmitter()
    emitter.add_listener(WebhookListener(config.webhooks))
    return emitter
```

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `src/aegis_qa/events/__init__.py` | Events package init |
| `src/aegis_qa/events/emitter.py` | EventEmitter, WorkflowEvent, EventListener protocol |
| `src/aegis_qa/events/log.py` | EventLog (in-memory ring buffer) |
| `src/aegis_qa/events/webhook.py` | WebhookListener (fire-and-forget HTTP delivery) |
| `src/aegis_qa/workflows/steps/report.py` | ReportStep implementation |
| `tests/test_events.py` | Tests for event system, log, and webhook delivery |
| `tests/test_report_step.py` | Tests for ReportStep |
| `docs/decomposition.md` | qaagent decomposition analysis |

### Modified Files
| File | Changes |
|------|---------|
| `src/aegis_qa/config/models.py` | Add `WebhookConfig`, `webhooks`, `event_log_size` to `AegisConfig` |
| `src/aegis_qa/workflows/pipeline.py` | Accept `EventEmitter`, emit events at lifecycle points |
| `src/aegis_qa/workflows/steps/__init__.py` | Add `"report": ReportStep` to `STEP_REGISTRY` |
| `src/aegis_qa/api/app.py` | Create `EventLog`, `EventEmitter`, `WebhookListener` in `create_app()`, store on `app.state` |
| `src/aegis_qa/api/routes/workflow_list.py` | Add `GET /api/events` endpoint |
| `src/aegis_qa/api/routes/workflows.py` | Pass `emitter` to `PipelineRunner` |
| `src/aegis_qa/landing/index.html` | Add "Recent Events" section |
| `src/aegis_qa/landing/app.js` | Fetch and render events |
| `src/aegis_qa/landing/styles.css` | Styles for event section |
| `.aegis.yaml.example` | Add `webhooks` and `event_log_size` config |
| `pyproject.toml` | No new dependencies (httpx already available) |
| `src/aegis_qa/cli.py` | Wire `create_cli_emitter()` into `aegis run`, validate webhook event types |
| `tests/test_workflows.py` | Update for emitter parameter |
| `tests/test_api.py` | Add event endpoint tests |
| `tests/test_integration.py` | Integration test: run workflow → check events |
| `docs/roadmap.md` | Phase 5 status updates |
| `docs/phases/phase5.md` | Status checkboxes |

## Success Criteria
- [ ] `PipelineRunner` emits `workflow.started`, `step.completed`, `workflow.completed`, `failure.detected` events
- [ ] `EventLog` stores events in a bounded ring buffer, accessible via `get_recent()`
- [ ] `GET /api/events` returns recent events with optional `?event_type=` filter
- [ ] Webhook config in `.aegis.yaml` delivers fire-and-forget POST to registered URLs
- [ ] Webhook event matching is exact-match only (plus `"*"` for all); test confirms non-matching events are not delivered
- [ ] Webhook delivery does not block pipeline execution (failures caught inside `_deliver()`, logged, never unobserved)
- [ ] Webhook task references stored in `_pending` set to prevent GC
- [ ] HMAC-SHA256 signature sent when webhook `secret` is configured
- [ ] `ReportStep` aggregates prior step results into summary stats
- [ ] `aegis config validate` checks webhook URLs are valid and warns on unrecognized event type strings
- [ ] CLI `aegis run` sends webhooks when configured (via `create_cli_emitter()`)
- [ ] CLI `aegis run` works unchanged when no webhooks configured (emitter=None)
- [ ] Landing page shows "Recent Events" section with live data
- [ ] `docs/decomposition.md` documents qaagent extraction strategy
- [ ] All existing tests still pass (updated for emitter parameter)
- [ ] `mypy --strict src/` passes clean
- [ ] `ruff check` passes clean
- [ ] Overall coverage ≥85%

## Open Questions
None — all decisions documented above. Round 1 reviewer feedback resolved:
1. Event matching: exact-match only + `"*"` (no glob/prefix)
2. Failure handling: `try/except` inside `_deliver()`, task reference set prevents GC
3. CLI behavior: `aegis run` creates emitter with `WebhookListener` when webhooks configured

## Risks
- **Webhook delivery latency:** Mitigation: fire-and-forget with `asyncio.create_task()`. 10s timeout. Failures logged but don't block.
- **Event log memory:** Mitigation: bounded `deque` with configurable `max_size`. Default 100 events.
- **Pipeline test updates:** Mitigation: `emitter` parameter is optional (defaults to None). Existing tests work unchanged.
