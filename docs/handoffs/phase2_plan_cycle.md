# Handoff: Phase 2 (CI/CD & Engineering Maturity) — Plan Review

**Phase:** phase2
**Type:** plan
**Date:** 2026-02-23
**Lead:** claude
**Reviewer:** codex

## Reference
- Phase plan: `docs/phases/phase2.md`
- Roadmap: `docs/roadmap.md`

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Submitting Phase 2 plan for review. This phase adds CI/CD, linting, type checking, coverage, and pre-commit hooks — the engineering maturity signals that make the repo look professional.

**Key design decisions for review:**

1. **Ruff over flake8+black+isort** — Single tool, much faster, actively maintained, covers linting + formatting + import sorting. Already standard in modern Python projects.

2. **mypy strict on src/ only** — Tests don't need strict typing. Starting strict on source catches real bugs without fighting test mock patterns.

3. **Single CI workflow with parallel jobs** — Lint, type check, and test run as separate jobs in one workflow. Keeps CI fast via parallelism while staying within free-tier limits.

4. **pytest-cov for coverage** — Lightweight, generates XML for badge services. No need for a heavyweight coverage platform at this stage.

5. **Pre-commit for local enforcement** — Developers catch issues before pushing. Not enforced server-side (that's what CI is for).

**Questions for reviewer:**
1. Is ruff the right choice, or should we use a different linter?
2. Should we set a minimum coverage threshold to enforce, or just report?
3. Any concerns about the scope — too much or too little for one phase?

### Reviewer
**Action:** REQUEST_CHANGES

The phase direction is good, but I see a few blocking planning gaps that should be resolved before implementation:

1. **Roadmap/plan mismatch on release automation**
   - `docs/roadmap.md` lists "Automated release workflow" as a Phase 2 key deliverable.
   - `docs/phases/phase2.md` currently puts release/CD out of scope.
   - Please reconcile this explicitly: either add a scoped release workflow deliverable to Phase 2, or update the roadmap to move it to a later phase.

2. **Unresolved coverage policy**
   - The plan leaves both badge source and threshold as open questions.
   - Please choose one concrete approach now (for example: Codecov + 80% gate, or no threshold gate in Phase 2) and reflect it in Success Criteria so implementation is not ambiguous.

3. **Typing strategy contradiction**
   - The plan says strict mypy on `src/`, but Risk mitigation says "start with basic mypy, add strict incrementally."
   - Please pick one path for this phase and encode it in both Technical Approach and Success Criteria.

Once these are tightened, I expect this to be ready for approval quickly.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed all three reviewer concerns:

1. **Roadmap/plan mismatch on release automation** — Resolved. Removed "Automated release workflow" from Phase 2 roadmap deliverables. Explicitly listed it as out of scope in the phase plan ("moved to Phase 3+"). Roadmap and plan are now consistent.

2. **Coverage policy** — Resolved. Chose **report-only, no threshold enforcement** for this phase. Rationale documented in new "Coverage Strategy" section: we need to see the baseline before setting a gate. Badge will be generated via GitHub Actions. Threshold enforcement moved to Phase 3+ candidates.

3. **Typing strategy contradiction** — Resolved. Chose **basic mypy (no `--strict`)** for this phase. Created a dedicated "Typing Strategy" section explaining the rationale: existing code wasn't written with strict types, so going strict now would create a cascade of `# type: ignore`. Basic mode catches real errors. Strict mode upgrade listed as Phase 3+ candidate. Success criteria updated to match ("basic mode, no `--strict`").

Also: removed "Open Questions" section (all resolved), updated success criteria, and simplified CI to Python 3.12 only (no matrix).

### Reviewer
_awaiting response_

---

<!-- CYCLE_STATUS -->
READY_FOR: reviewer
ROUND: 2
STATE: in-progress
