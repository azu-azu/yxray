# Milestones

## v1.0 MVP (Shipped: 2026-03-07)

**Phases completed:** 9 phases, 27 plans
**Timeline:** 2026-02-28 → 2026-03-07 (7 days)
**Lines of code:** ~5,844 LOC Python (src/ + tests/)
**Tests:** 105 passing, 1 xfailed (intentional GUID stub)
**Git commits:** 114

**Delivered:** A CLI tool (`acd diff`) that compares two Alteryx `.yxmd` files and produces a self-contained HTML report with color-coded diff summary, expandable per-tool configuration changes, and an embedded interactive workflow graph — with zero false positives from canvas layout noise.

**Key accomplishments:**
1. Immutable 4-stage pipeline (Parser → Normalizer → Matcher → Differ) with typed frozen dataclasses across all stages
2. lxml-based parser with typed `ParseError` exception hierarchy that rejects malformed `.yxmd` files before any processing
3. C14N canonicalization + GUID/timestamp stripping eliminates all Alteryx XML noise false positives (whitespace, attribute ordering, auto-generated metadata)
4. Two-pass node matcher (ToolID exact lookup + Hungarian algorithm fallback with 0.8 cost threshold) prevents phantom add/remove pairs on ToolID regeneration
5. Field-level diff engine using DeepDiff with full before/after values; connection diffs via frozenset symmetric difference on 4-tuple anchors
6. Self-contained HTML report (Jinja2, inline CSS/JS, ALCOA+ governance footer) with embedded vis-network 9.1.4 interactive graph — no CDN, air-gap capable
7. `acd diff` Typer CLI with predictable exit codes (0/1/2), `--json`, `--include-positions`, `--canvas-layout` flags

**Requirements:** 24/24 v1 requirements satisfied
**Audit:** tech_debt — no critical blockers; 6 deferred browser-UX and GUID verification items

**Archive:**
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

---

## v1.1 Alteryx Git Companion (Shipped: 2026-04-02)

**Phases completed:** 15 phases (10–22 incl. 16.1, 18.1), 55 plans
**Timeline:** 2026-03-09 → 2026-04-01 (24 days)
**Lines of code:** ~6,869 LOC app (Python + TSX/TS) + ~6,992 LOC tests
**Tests:** 252 collected (243 passing, 1 xfailed)
**Git commits:** 325

**Delivered:** A Windows desktop companion app (PyInstaller `.exe`) that makes Git-based version control accessible to non-technical Alteryx analysts — file watcher, save/undo/discard, history timeline with embedded ACD diff viewer, GitHub OAuth + GitLab PAT remote backup, experiment branch management, in-app PR/MR creation, and polished CI templates.

**Key accomplishments:**
1. Windows `.exe` via PyInstaller — bundles FastAPI + React + acd CLI; zero Python install; auto-launches browser on start; auto-starts on Windows boot via system tray
2. File watcher with automatic polling fallback (5s) for SMB/UNC network drives — no manual configuration
3. Core version control loop: selective commit (Save Version), flat history timeline, ACD HTML diff embedded in iframe, Undo last save, Discard to `.acd-backup`
4. Remote backup: GitHub OAuth device flow + GitLab PAT; credentials in OS keyring; single-button push with auto-create remote repo; ahead/behind indicator
5. Experiment branch management with git graph view, push status cloud icons, and in-app PR/MR creation for both GitHub and GitLab
6. CI templates: GitHub comment deduplication (find-or-update), inline PNG graph, GitLab MR marker-based dedup, `ci-templates/` distributable with setup README
7. HTML report visual redesign: dark-first CSS variable theming, stat cards with accent colors, animated chevron tool rows, Before/After diff panels, `localStorage` theme persistence — all self-contained, zero CDN

**Requirements:** 31/31 v1.1 requirements satisfied
**Audit:** tech_debt — no critical blockers; 24 deferred human-verification items (Windows-only or live browser)

**Archive:**
- `.planning/milestones/v1.1-ROADMAP.md`
- `.planning/milestones/v1.1-REQUIREMENTS.md`
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

---
