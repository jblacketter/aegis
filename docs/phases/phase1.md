# Phase 1: Landing Page & Portfolio Polish

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
**What:** Transform the Aegis landing page from a functional scaffold into a polished portfolio piece that showcases the AI QA tool suite professionally.
**Why:** The landing page is the public face of Jack's tool suite — it needs to demonstrate platform-level thinking and engineering quality to potential employers and collaborators. The current page is structurally sound but visually basic.
**Depends on:** None (foundation complete in Phase 26c)

## Scope

### In Scope
- Redesigned hero section with professional branding and clear value proposition
- Tool cards with GitHub repo links, live health status badges, and meaningful feature tags
- Graceful offline/static mode — page works as a standalone portfolio even when services aren't running
- Interactive or enhanced architecture diagram showing the full ecosystem
- Responsive design (mobile-friendly)
- Footer with links to GitHub profile, LinkedIn, portfolio site
- Static fallback data so the page renders without a running API (critical for portfolio use)
- Updated `/api/portfolio` endpoint to serve richer metadata (repo URLs, status, descriptions)

### Out of Scope
- CI/CD pipeline (Phase 2)
- Workflow execution from the UI
- User authentication or admin features
- Hosting/deployment of the landing page as a separate static site (future consideration)
- Complete redesign of jblacketter.github.io (separate project)

## Technical Approach

### Landing Page Architecture
The landing page currently requires a running Aegis API to populate tool cards. For portfolio use, it must work standalone with static fallback data baked into the HTML/JS.

**Approach:**
1. Embed tool metadata as a JS constant fallback in `app.js`
2. Try fetching live data from the API; if unavailable, render from static data
3. When live, show real health status badges; when static, show "offline" or hide status

### Visual Design
- Keep the dark theme (already professional) but refine typography and spacing
- Add subtle animations (fade-in on scroll, hover effects on cards)
- Improve the SVG architecture diagram with better labels and optional interactivity
- Add a "About" or context blurb that frames the suite as a QA engineering toolkit

### Data Model Changes
- Extend `ServiceEntry` or portfolio endpoint to include `repo_url` and `docs_url` fields
- Add tool-level metadata: icon/color, category, maturity status

### Files to Create/Modify
- `src/aegis_qa/landing/index.html` — redesigned layout, new sections
- `src/aegis_qa/landing/styles.css` — refined styles, responsive breakpoints, animations
- `src/aegis_qa/landing/app.js` — static fallback data, enhanced rendering, health polling
- `src/aegis_qa/api/routes/portfolio.py` — richer metadata response
- `src/aegis_qa/config/models.py` — optional `repo_url`/`docs_url` fields on ServiceEntry
- `tests/test_api.py` — updated portfolio endpoint tests

## Success Criteria
- [ ] Landing page renders fully with no running API (static fallback mode)
- [ ] Tool cards show name, description, features, GitHub link, and health status (when live)
- [ ] Architecture diagram is clear and visually polished
- [ ] Page is responsive down to 375px width (mobile)
- [ ] Hero section clearly communicates "AI QA Tool Suite by Jack Blacketter"
- [ ] Footer links to GitHub profile, LinkedIn, portfolio site
- [ ] All existing tests pass; new tests cover portfolio endpoint changes
- [ ] Page loads in under 2 seconds with no external CDN dependencies

## Open Questions
- Should we add a "Demo" or "Getting Started" section to the landing page?
- Should tool cards link to individual tool documentation pages, or just to GitHub repos?
- Any specific color/brand preferences beyond the current dark theme?

## Risks
- **Scope creep into full portfolio site:** Mitigation — keep this focused on the Aegis landing page only, not a replacement for jblacketter.github.io
- **Over-engineering the static fallback:** Mitigation — keep it simple: a JS object with the same shape as the API response
