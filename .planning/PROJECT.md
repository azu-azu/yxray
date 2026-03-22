# Alteryx Canvas Diff (ACD)

## What This Is

A CLI tool that compares two Alteryx workflow files (`.yxmd`) and generates a self-contained HTML diff report — showing exactly what changed at the tool, configuration, and connection level, with an embedded interactive workflow graph. Built for analytics developers and governance teams who need to understand what changed between workflow versions without reading XML.

Shipped v1.0 as a developer CLI tool for an internal analytics team. Architecture is API-first: the same `pipeline.run()` facade can be wrapped by a REST API, Alteryx Server webhook, or Git hook without rearchitecting the engine.

## Core Value

Accurate detection of functional changes — zero false positives from layout noise, zero missed configuration changes.

## Requirements

### Validated

- ✓ Accept two .yxmd files as CLI input and validate XML structure — v1.0
- ✓ Parse workflow into internal object model (ToolID, type, position, config, connections) — v1.0
- ✓ Normalize XML to eliminate false positives (whitespace, attribute ordering, non-functional metadata, GUIDs/timestamps) — v1.0
- ✓ Ignore position-only changes by default; expose `--include-positions` flag for opt-in — v1.0
- ✓ Detect tool additions, removals, and modifications — v1.0
- ✓ Detect configuration-level changes (expressions, filters, field selections, parameter values) — v1.0
- ✓ Detect connection additions, removals, and rewirings — v1.0
- ✓ Generate HTML report with color-coded summary and expandable per-tool detail sections — v1.0
- ✓ Embed interactive visual graph (canvas-style nodes + directed edges) in HTML report — v1.0
- ✓ Color-code graph: green=added, red=removed, yellow=modified, blue=connection changes — v1.0
- ✓ Graph uses hierarchical auto-layout by default; `--canvas-layout` flag for Alteryx X/Y coordinate positioning — v1.0
- ✓ Support hover/click on graph nodes to display configuration diff inline — v1.0
- ✓ Handle malformed or corrupted XML gracefully with descriptive error messages — v1.0
- ✓ Perform under 5 seconds for workflows up to 500 tools — v1.0
- ✓ Exit codes: 0 = no diff, 1 = diff detected, 2 = error — v1.0
- ✓ JSON output via `--json` flag for CI/CD integration — v1.0
- ✓ ALCOA+ governance metadata footer (file paths, SHA-256 hashes, timestamp) — v1.0

### Active

<!-- Current scope for v1.1 Alteryx Git Companion -->

- [ ] Windows .exe desktop companion app (PyInstaller + FastAPI + React, no Python install required)
- [ ] Auto-start on Windows login with system tray icon showing change badge
- [ ] File watcher with automatic polling fallback for network/SMB drives
- [ ] Save Version flow (commit), history timeline, embedded ACD diff viewer, undo last save
- [ ] Multi-project folder management
- [ ] GitHub OAuth + GitLab PAT remote auth and push (OS credential store)
- [ ] Basic branch management (experiment copies, no DAG visualization)
- [ ] CI polish: GitHub comment deduplication + inline PNG graph, GitLab cleanup, setup README

### Out of Scope

- Real-time overlay inside Alteryx Designer — requires Designer plugin API; Phase 2+
- Macro recursion parsing — Phase 2
- CI/CD automation platform — Phase 3
- Enterprise security framework (SSO, RBAC) — not needed for CLI; Phase 3 with API
- REST API service layer — Phase 3 (architecture supports it via pipeline.run() facade)
- Web upload UI — requires server infrastructure; Phase 3
- `.yxmc` / `.yxapp` / `.yxzp` format support — defer until core parser is stable
- Three-way merge — requires semantic understanding of Alteryx config; 10x v1 scope
- AI natural language change summary — hallucination risk unacceptable for governed workflows

## Context

**Current state (v1.0):** Shipped. ~5,844 LOC Python (src/ + tests/). 105 tests passing. 24/24 v1 requirements satisfied.

**Tech stack:** Python 3.13 (≥3.11), uv, lxml 6.0.2, scipy 1.17.1 (Hungarian matcher), deepdiff 8.x, networkx 3.6.1, Jinja2, Typer, vis-network 9.1.4 (vendored).

**Known tech debt from v1.0:**
- `GUID_VALUE_KEYS` frozenset in `normalizer/patterns.py` is empty — GUID field names in real `.yxmd` files not yet confirmed. Mechanism in place; needs real-file validation.
- `JSONRenderer` (Phase 6) schema diverges from CLI `--json` output (`_cli_json_output()`). JSONRenderer exercised only by unit tests, not wired to CLI.
- Browser-interactive graph behaviors (click-to-diff panel, show-only-changes toggle) require manual browser test to confirm.

**User context:** Internal analytics team. Manual side-by-side comparison before workflow promotions is recurring pain. If pilot succeeds, evolve into API service for Alteryx Server promotion events.

**SaaS path:** Same `pipeline.run(DiffRequest)` facade is the only entry point. REST API = thin wrapper. Git hook = thin wrapper. No rearchitecting needed.

## Constraints

- **Tech Stack:** Python 3.11+, lxml, scipy, deepdiff, networkx, Jinja2, Typer, vis-network 9.1.4 (vendored UMD)
- **Performance:** Report generation under 5 seconds for workflows up to 500 tools
- **Deployment:** CLI-first; no server infrastructure required for v1
- **Output:** Single self-contained HTML file + optional JSON; viewable in standard browser offline
- **Compatibility:** Handles ToolID regeneration via two-pass matcher (exact + Hungarian fallback)

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Ignore position changes by default | Position drift is the #1 source of false positives; functional diff is the core value | ✓ Good — `--include-positions` flag works; positions stored separately in NormalizedNode |
| X/Y used for graph layout, not diffing | Positions serve layout rendering but not change detection — dual-role clarified explicitly | ✓ Good — two distinct flags: `--include-positions` (diff detection) vs `--canvas-layout` (graph rendering) |
| API-first architecture target | Alteryx Server + Git hook both become thin wrappers over parse→diff→render pipeline | ✓ Good — confirmed by Phase 9: CLI is 15-line adapter over `pipeline.run()` |
| CLI prototype first | Validates the diff engine and report quality before investing in API infrastructure | ✓ Good — v1.0 complete; core value proven |
| Secondary matching (type + position + hash similarity) | ToolIDs can regenerate on Alteryx save; pure ID matching causes false add/remove pairs | ✓ Good — Hungarian algorithm with 0.8 cost threshold; 9 contract tests passing |
| slots=True removed from DiffResult only | Python 3.11 slots=True dataclasses are incompatible with @property descriptors | ✓ Good — minimal exception to frozen pattern; documented |
| vis-network 9.1.4 vendored (no CDN) | Air-gap compliance — HTML report must work offline | ✓ Good — 702KB UMD bundle embedded; zero CDN references |
| JSONRenderer schema separate from CLI --json | Preserves JSONRenderer contract tests; CLI --json uses _cli_json_output() with different schema | ⚠️ Revisit — creates two incompatible JSON schemas; wire JSONRenderer to CLI in v1.1 |
| GUID_VALUE_KEYS starts empty | Populate only from confirmed real .yxmd files, not speculation | ⚠️ Revisit — still empty at v1.0 ship; needs real-file validation |

## Current Milestone: v1.1 Alteryx Git Companion

**Goal:** Make Git-based version control accessible to non-technical Alteryx analysts via a desktop companion app and polished CI integration.

**Target features:**
- Desktop companion app (local web server, system tray, auto-start on boot)
- File watcher with network/SMB drive support via polling fallback
- Save Version / History / Diff / Undo — the core version control loop
- GitHub OAuth + GitLab PAT remote backup
- Basic experiment copy (branch) management
- CI polish: GitHub inline graph PNG, comment deduplication, GitLab cleanup, setup README

---
*Last updated: 2026-03-13 after v1.1 milestone start*
