# Alteryx Canvas Diff (ACD)

## What This Is

A CLI tool that compares two Alteryx workflow files (`.yxmd`) and generates a self-contained HTML diff report — showing exactly what changed at the tool, configuration, and connection level, with an embedded interactive workflow graph. Built for analytics developers and governance teams who need to understand what changed between workflow versions without reading XML.

Shipped v1.1 as a Windows desktop companion app — non-technical Alteryx analysts can save versions, browse history, push to GitHub/GitLab, and manage experiment branches without touching the command line.

## Core Value

Accurate detection of functional changes — zero false positives from layout noise, zero missed configuration changes.

## Current State — v1.1 Shipped (2026-04-02)

**App:** Windows `.exe` desktop companion (PyInstaller + FastAPI + React). ~6,869 LOC app code. ~6,992 LOC test code. 252 tests (243 pass + 1 xfail). 31/31 v1.1 requirements satisfied.

**What's running:**
- Local web server (FastAPI) on port 7433 + auto-browser launch
- System tray icon + auto-start on Windows boot
- File watcher (native + polling for SMB/UNC drives)
- Save Version / History timeline / ACD diff viewer inline / Undo / Discard
- Multi-project folder management
- GitHub OAuth + GitLab PAT remote auth + single-button push (auto-creates remote repo)
- Experiment branches (create / switch / push / PR/MR creation from app)
- CI templates: GitHub comment dedup + inline graph PNG, GitLab MR comment dedup, setup README
- Redesigned HTML diff report: dark-first CSS variable theming, stat cards, polished diff panels

**Known open items (not blocking):**
- 24 human-verification items (Windows-only or live browser required)
- `GUID_VALUE_KEYS` frozenset still empty — needs validation against real `.yxmd` files
- `JSONRenderer` not wired to CLI `--json` — two incompatible schemas (tech debt from v1.0)

## Requirements

### Validated (v1.0)

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

### Validated (v1.1)

- ✓ Windows .exe desktop companion app — no Python install required (APP-01)
- ✓ Auto-start on Windows boot, silent background mode (APP-02)
- ✓ Port 7433 with fallback 7434–7443 (APP-03)
- ✓ Browser auto-launch on exe start (APP-04a) + system tray click-to-open (APP-04b)
- ✓ System tray icon shows app status (APP-05)
- ✓ First-run welcome screen (ONBOARD-01)
- ✓ Add project folder with auto git init (ONBOARD-02)
- ✓ Git identity prompt on first use (ONBOARD-03)
- ✓ Multi-project folder management (ONBOARD-04)
- ✓ File change badge for .yxmd/.yxwz (WATCH-01)
- ✓ Polling fallback for SMB/UNC paths (WATCH-02)
- ✓ First-save N-workflow warning (WATCH-03)
- ✓ Save Version with selective commit (SAVE-01) + Undo (SAVE-02) + Discard to .acd-backup (SAVE-03)
- ✓ History timeline (HIST-01) + inline ACD diff viewer (HIST-02)
- ✓ GitHub OAuth (REMOTE-01) + GitLab PAT (REMOTE-02) + OS keyring (REMOTE-03)
- ✓ Single-button push (REMOTE-04) + auto-create remote repo (REMOTE-05) + ahead/behind indicator (REMOTE-06)
- ✓ Experiment branches create/switch/label (BRANCH-01/02/03)
- ✓ GitHub comment dedup (CI-01) + inline PNG (CI-02) + GitLab cleanup (CI-03) + setup README (CI-04)

### Active (v1.2)

*TBD — run `/gsd:new-milestone` to define requirements.*

### Out of Scope

- Real-time overlay inside Alteryx Designer — requires Designer plugin API
- Macro recursion parsing — deferred
- CI/CD automation platform — deferred
- Enterprise security framework (SSO, RBAC) — deferred
- REST API service layer — architecture supports it via `pipeline.run()` facade when needed
- Three-way merge — requires semantic understanding of Alteryx config; 10x scope
- AI natural language change summary — hallucination risk unacceptable for governed workflows

## Context

**Tech stack:** Python 3.13 (≥3.11), uv, FastAPI, React + Vite + shadcn/ui + Zustand, lxml 6.0.2, scipy 1.17.1 (Hungarian matcher), deepdiff 8.x, networkx 3.6.1, Jinja2, Typer, pystray, keyring, PyInstaller, vis-network 9.1.4 (vendored).

**User context:** Internal analytics team. Manual side-by-side comparison before workflow promotions is recurring pain. Pilot running on Windows. If successful, evolve toward API service for Alteryx Server promotion events.

**SaaS path:** Same `pipeline.run(DiffRequest)` facade is the only entry point. REST API = thin wrapper. No rearchitecting needed.

## Constraints

- **Tech Stack:** Python 3.11+, lxml, scipy, deepdiff, networkx, Jinja2, Typer, vis-network 9.1.4 (vendored UMD)
- **Performance:** Report generation under 5 seconds for workflows up to 500 tools
- **Deployment:** Windows .exe; no server infrastructure required for v1.x
- **Output:** Single self-contained HTML file + optional JSON; viewable in standard browser offline
- **Compatibility:** Handles ToolID regeneration via two-pass matcher (exact + Hungarian fallback)

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Ignore position changes by default | Position drift is the #1 source of false positives; functional diff is the core value | ✓ Good — `--include-positions` flag works; positions stored separately in NormalizedNode |
| API-first architecture target | Alteryx Server + Git hook both become thin wrappers over parse→diff→render pipeline | ✓ Good — confirmed by Phase 9: CLI is 15-line adapter over `pipeline.run()` |
| vis-network 9.1.4 vendored (no CDN) | Air-gap compliance — HTML report must work offline | ✓ Good — 702KB UMD bundle embedded; zero CDN references |
| PyInstaller .exe (not installer) | Simplest distribution — no admin rights needed, xcopy deploy | ✓ Good — GitHub Actions release CI builds on windows-latest |
| OS keyring for credentials | Windows Credential Manager / macOS Keychain — never plaintext | ✓ Good — keyring lib + hiddenimports in PyInstaller spec |
| GIT_ASKPASS pattern for push | Token never in URL or subprocess args; temp script approach | ✓ Good — cross-platform; used for both push and fetch |
| SSE for file watcher events | Long-poll alternative harder to clean up on disconnect | ✓ Good — asyncio.wait_for + is_disconnected() for clean teardown |
| Polling fallback for SMB/UNC | watchdog has known issues with network drives | ✓ Good — is_network_path() auto-detects; no manual config needed |
| JSONRenderer schema separate from CLI --json | Preserves JSONRenderer contract tests | ⚠️ Open — two incompatible JSON schemas; wire in v1.2 if needed |
| GUID_VALUE_KEYS starts empty | Populate only from confirmed real .yxmd files | ⚠️ Open — still empty; needs real-file validation |

---
*Last updated: 2026-04-02 — v1.1 shipped: Windows desktop companion app, 31/31 requirements, 252 tests*
