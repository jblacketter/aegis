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
- **mypy** for type checking with strict mode on `src/`
- **pytest-cov** for coverage reporting
- **Pre-commit** config with ruff + mypy hooks
- Coverage badge on README (via GitHub Actions or coverage service)
- `pyproject.toml` updates for ruff, mypy, and coverage configuration
- Dev dependency updates in `[project.optional-dependencies]`
- Fix any lint/type errors surfaced in existing code

### Out of Scope
- Automated PyPI publishing (future consideration)
- Docker containerization
- CD/deployment pipeline
- Branch protection rules (manual GitHub setup)

## Technical Approach

### CI Pipeline (`ci.yml`)
Single workflow triggered on push to `main` and on pull requests:
1. **Lint** job: `ruff check src/ tests/` and `ruff format --check src/ tests/`
2. **Type check** job: `mypy src/`
3. **Test** job: `pytest --cov=aegis_qa --cov-report=xml tests/`
4. Matrix: Python 3.12 (primary), optionally 3.11 for compatibility

### Ruff Configuration
Add `[tool.ruff]` section to `pyproject.toml`:
- Target Python 3.11+
- Select standard rule sets (E, F, W, I for isort, UP for pyupgrade)
- Line length 120 (matches existing code style)
- Exclude common dirs

### mypy Configuration
Add `[tool.mypy]` section to `pyproject.toml`:
- Strict mode on `src/aegis_qa/`
- Ignore missing imports for third-party libs initially
- Incremental checking enabled

### Pre-commit
Create `.pre-commit-config.yaml`:
- ruff (lint + format)
- mypy
- Trailing whitespace, end-of-file fixer

### Coverage
- Use `pytest-cov` to generate reports
- Upload to Codecov or use a badge generation action
- Add badge to README alongside any existing badges

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
- [ ] `mypy src/` passes (strict mode, allowing `# type: ignore` for known edge cases)
- [ ] `pytest --cov` reports coverage percentage
- [ ] Coverage badge visible on README
- [ ] CI status badge visible on README
- [ ] Pre-commit config exists and hooks run locally
- [ ] All existing 69 tests still pass
- [ ] Dev dependencies updated in pyproject.toml

## Open Questions
- Codecov vs. a simpler badge-generation approach for coverage?
- Should we enforce a minimum coverage threshold (e.g., 80%)?

## Risks
- **Lint/type fixes cascade:** Existing code may have many type errors in strict mode. Mitigation — start with basic mypy, add strict incrementally. Use `# type: ignore` sparingly for truly tricky spots.
- **CI minutes:** Free tier GitHub Actions has limits. Mitigation — single workflow, minimal matrix, fast tools (ruff is very fast).
