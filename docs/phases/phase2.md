# Phase 2: CI/CD & Engineering Maturity

## Status
- [x] Planning
- [ ] In Review
- [ ] Approved
- [ ] Implementation
- [ ] Implementation Review
- [ ] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human

## Summary
**What:** Add a GitHub Actions CI pipeline, linting, type checking, test coverage reporting, pre-commit hooks, and status badges to the README. Signals engineering discipline and production-readiness.
**Why:** A polished landing page (Phase 1) draws people in — but the repo itself needs to look professional. CI badges, clean linting, and coverage reports tell employers "this person runs a real engineering process." It also catches regressions as we build Phases 3+.
**Depends on:** Phase 1 (complete)

## Scope

### In Scope
- GitHub Actions CI workflow (`ci.yml`): lint, type check, test, coverage on push/PR
- **Ruff** for linting and formatting (fast, modern, replaces flake8+black+isort)
- **mypy** for type checking (basic mode on `src/`, see Typing Strategy below)
- **pytest-cov** for coverage reporting
- **Pre-commit** config with ruff + mypy hooks
- Coverage badge on README via GitHub Actions badge generation (no external service)
- `pyproject.toml` updates for ruff, mypy, and coverage configuration
- Dev dependency updates in `[project.optional-dependencies]`
- Fix any lint/type errors surfaced in existing code

### Out of Scope
- Automated PyPI publishing / release workflow (moved to Phase 3+, see roadmap)
- Docker containerization
- CD/deployment pipeline
- Branch protection rules (manual GitHub setup)
- Coverage threshold enforcement (report only in this phase)

## Technical Approach

### CI Pipeline (`ci.yml`)
Single workflow triggered on push to `main` and on pull requests:
1. **Lint** job: `ruff check src/ tests/` and `ruff format --check src/ tests/`
2. **Type check** job: `mypy src/`
3. **Test** job: `pytest --cov=aegis_qa --cov-report=xml tests/`
4. **Badge** step: Generate coverage badge after test job
5. Python 3.12 only (single version, no matrix — keeps CI fast and simple)

### Ruff Configuration
Add `[tool.ruff]` section to `pyproject.toml`:
- Target Python 3.11+
- Select standard rule sets (E, F, W, I for isort, UP for pyupgrade)
- Line length 120 (matches existing code style)
- Exclude common dirs

### Typing Strategy
**Basic mypy in this phase, strict in a future phase.** Rationale: the existing codebase was written without type annotations in mind. Going strict immediately risks a cascade of `# type: ignore` comments that hurt readability. Instead:
- `mypy src/` with default settings + `ignore_missing_imports = true`
- No `--strict` flag
- Fix any real type errors surfaced
- Add type annotations to new code going forward
- Strict mode upgrade is a candidate for Phase 3+

### Pre-commit
Create `.pre-commit-config.yaml`:
- ruff (lint + format)
- mypy (basic mode)
- Trailing whitespace, end-of-file fixer

### Coverage Strategy
**Report-only, no threshold enforcement in this phase.** Rationale: setting an arbitrary gate before understanding baseline coverage creates noise. Instead:
- Use `pytest-cov` to generate XML and terminal reports
- Generate a coverage badge via `gist-based` badge or `dynamic-badges-action` in CI
- Display badge on README so coverage is visible
- Threshold enforcement is a candidate for Phase 3+ once we know the baseline

## Files to Create/Modify
- `.github/workflows/ci.yml` — CI pipeline
- `.pre-commit-config.yaml` — Pre-commit hook config
- `pyproject.toml` — Add ruff, mypy, coverage config; update dev deps
- `README.md` — Add CI and coverage badges
- `src/aegis_qa/**/*.py` — Fix any lint/type errors surfaced
- `tests/**/*.py` — Fix any lint errors surfaced

## Success Criteria
- [ ] GitHub Actions CI runs on push to main and on PRs
- [ ] `ruff check` and `ruff format --check` pass with zero errors
- [ ] `mypy src/` passes in basic mode (no `--strict`)
- [ ] `pytest --cov` reports coverage percentage
- [ ] Coverage badge visible on README
- [ ] CI status badge visible on README
- [ ] Pre-commit config exists and hooks run locally
- [ ] All existing 69+ tests still pass
- [ ] Dev dependencies updated in pyproject.toml

## Open Questions
None — all resolved.

## Risks
- **Lint fixes cascade:** Ruff may flag many issues in existing code. Mitigation — auto-fix with `ruff check --fix` and `ruff format` before committing.
- **CI minutes:** Free tier GitHub Actions has limits. Mitigation — single workflow, single Python version, fast tools (ruff is very fast).
