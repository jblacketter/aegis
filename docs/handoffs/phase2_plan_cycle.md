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
_awaiting response_

---

<!-- CYCLE_STATUS -->
READY_FOR: reviewer
ROUND: 1
STATE: in-progress
