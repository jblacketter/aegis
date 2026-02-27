# Handoff: Phase 4 (Production Readiness — Persistence, Auth & Dashboard) — Plan Review

**Phase:** phase4
**Type:** plan
**Date:** 2026-02-27
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase4.md`

## Plan Summary

Phase 4 makes Aegis production-worthy. Five pillars:

1. **Persistent Execution History** — SQLite via `aiosqlite`. Normalized schema (`workflow_runs` + `step_runs` tables). Abstract `ExecutionHistoryBackend` protocol with `InMemoryHistory` (existing) and `SqliteHistory` (new) implementations. Auto-creates tables on first use.

2. **API Key Authentication** — Optional `auth.api_key` config field. FastAPI dependency checks `X-API-Key` header on write endpoints. Disabled when no key configured (backwards compatible). Supports env var interpolation.

3. **Execution History Dashboard** — New "Recent Runs" section on landing page. New `GET /api/workflows/history` endpoint. Shows last 10 runs with status badges, timestamps, duration.

4. **Config Validation CLI** — `aegis config validate` command. Checks YAML parsing, Pydantic validation, service references, step type existence, URL validity. Green/red output, exit code 0/1.

5. **Mypy Strict Mode** — Enable `strict = true` for `src/`. Fix all resulting type errors.

### Key Design Decisions

- **Protocol-based history:** Both backends implement the same protocol, making them interchangeable. Tests use in-memory, production uses SQLite.
- **SQLite without migration framework:** Auto-create tables on first use. No Alembic for v1 — the schema is simple and stable.
- **Auth on write endpoints only:** Read endpoints stay public. This keeps the portfolio landing page accessible while protecting the API.
- **No webhooks this phase:** Deferred to Phase 5 to keep scope tight. Focus on what makes Aegis itself production-ready.

### Files: 4 new, 14 modified

See `docs/phases/phase4.md` for the full file list and technical approach.

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 4 plan submitted for review. The plan crosses Aegis from "demo" to "production-ready":
- **Data durability** — execution history survives restarts
- **Security** — API key auth on write endpoints
- **Observability** — dashboard shows real execution data
- **DX** — config validation catches mistakes before runtime
- **Type safety** — mypy strict proves code quality

All design decisions are documented. Roadmap updated to reflect Phase 4 re-scope (qaagent decomposition → Phase 5).

### Reviewer
**Action:** REQUEST_CHANGES

Strong direction overall, but I see three blocking planning gaps that should be tightened before implementation:

1. **Route conflict risk for `GET /api/workflows/history`**
   - The plan adds `GET /api/workflows/history` while this codebase already has `GET /api/workflows/{name}` in the same route namespace.
   - Without an explicit ordering/path strategy, `"history"` can be captured as `{name}`.
   - Please specify one concrete solution in the plan: route declaration order guarantees, or a non-conflicting path shape.

2. **History backend wiring/lifecycle is underspecified**
   - The plan says `create_app()` wires `SqliteHistory` by default, but current routing uses module-level state (`workflow_list` singleton) and `workflows` imports from that module.
   - Please document the exact dependency injection path so **run** and **history** endpoints are guaranteed to use the same backend instance/path, including how tests override it.
   - This should explicitly prevent a repeat of the Phase 3 bug where run and history were disconnected.

3. **Retention is in scope but has no concrete config/behavior**
   - Scope includes optional max-records-per-workflow retention, but Technical Approach/config snippets do not define the field or pruning behavior.
   - Please add explicit config shape and enforcement strategy (when pruning occurs and how old records are selected/deleted).

Once these are resolved, this looks close to approval.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

All three issues addressed:

1. **Route conflict resolved:** Changed endpoint from `GET /api/workflows/history` to `GET /api/history`. Top-level path avoids the `{name}` capture entirely. No ordering tricks needed.

2. **History wiring fully specified:** Replaced module-level singleton pattern with `app.state.history`. `create_app()` creates the backend and stores it once. All routes access via `request.app.state.history`. Tests set `app.state.history = InMemoryHistory()`. Added a full ASCII dependency injection diagram to the Technical Approach showing the exact flow. This structurally prevents the Phase 3 disconnection bug.

3. **Retention concretely specified:** Added `history_max_records: int = 0` to config (0 = unlimited). Pruning happens in `SqliteHistory.record()` after insertion — counts records per workflow, deletes oldest excess via SQL. `step_runs` FK uses `ON DELETE CASCADE` to auto-clean step data. Added code snippet to Technical Approach and success criterion.

### Reviewer
**Action:** APPROVE

All three blocking gaps from Round 1 are resolved:

1. **Route conflict** — `GET /api/history` as a top-level path cleanly avoids the `{name}` capture. No ordering tricks needed.
2. **History wiring** — `app.state.history` DI pattern with the ASCII dependency diagram makes the injection path explicit. Tests override via `app.state.history = InMemoryHistory()`. Structurally prevents the Phase 3 disconnection class.
3. **Retention** — `history_max_records: int = 0` with post-insertion pruning and `ON DELETE CASCADE` is concrete and correct.

Plan approved for implementation.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 2
STATE: approved
