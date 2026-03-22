---
phase: 15-system-tray-and-auto-start
plan: 03
subsystem: api
tags: [pystray, PIL, pillow, system-tray, fastapi, settings, autostart, tray-icon]

# Dependency graph
requires:
  - phase: 15-system-tray-and-auto-start
    plan: 01
    provides: RED test stubs for _compute_state, settings router, tray module
  - phase: 15-system-tray-and-auto-start
    plan: 02
    provides: app/services/autostart.py (register/unregister/is_enabled)
provides:
  - "app/tray.py: _compute_state() pure function + TrayIcon class + start_tray() entry point"
  - "app/routers/settings.py: GET/POST /api/settings backed by autostart service"
  - "app/server.py: settings router registered"
  - "assets/icon-watching.ico and assets/icon-changes.ico: programmatically generated placeholder icons"
affects: [15-04, app.spec PyInstaller bundle, main.py tray thread]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pystray import guarded by try/except ImportError for macOS/CI compatibility"
    - "_compute_state() pure function (dict -> tuple) keeps tray state testable without OS deps"
    - "PIL programmatic icon fallback: generate 64x64 RGBA squares with letter overlay"
    - "_get_asset_path() uses sys._MEIPASS pattern for PyInstaller bundle compatibility"
    - "Module-level autostart import in settings router enables unittest.mock.patch targeting"

key-files:
  created:
    - app/tray.py
    - app/routers/settings.py
    - assets/icon-watching.ico
    - assets/icon-changes.ico
  modified:
    - app/server.py

key-decisions:
  - "pystray import guarded by try/except at module level -- PYSTRAY_AVAILABLE flag controls run() path; CI/macOS tests never need pystray installed"
  - "_compute_state() uses em-dash (U+2014) in tooltips: 'Alteryx Git Companion — watching'; pure function needs no mocking"
  - "Placeholder icons generated using PIL during plan execution (not at runtime) so assets exist for PyInstaller bundling"
  - "settings.router registered in server.py after history.router -- consistent with prior router registration order"

patterns-established:
  - "Tray state computation: pure dict -> (state_str, tooltip_str) function for zero-dependency testability"
  - "Asset path resolution: _get_asset_path() centralizes sys._MEIPASS / dev path logic"

requirements-completed: [APP-05]

# Metrics
duration: 6min
completed: 2026-03-15
---

# Phase 15 Plan 03: System Tray Icon + Settings Router Summary

**pystray-guarded TrayIcon with PIL icon loading, _compute_state() pure function, and GET/POST /api/settings router backed by autostart service -- all 9 tray+settings tests GREEN**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-15T02:00:00Z
- **Completed:** 2026-03-15T02:06:44Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `_compute_state()` pure function: idle/watching/changes states with singular/plural handling, aggregates multiple projects
- `TrayIcon` class: pystray-guarded, PIL image loading with programmatic fallback, polling loop, menu with Open/Quit
- `start_tray()` entry point for daemon thread invocation from main()
- `app/routers/settings.py` GET/POST /api/settings with module-level autostart import for mock.patch
- Settings router registered in server.py; `/api/settings` confirmed accessible in FastAPI route table
- Generated assets/icon-watching.ico (green) and assets/icon-changes.ico (amber) via PIL

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/tray.py with _compute_state + TrayIcon + generate placeholder icons** - `edb2b30` (feat)
2. **Task 2: Create app/routers/settings.py and register in server.py** - `a9bc466` (feat)

## Files Created/Modified

- `app/tray.py` - _compute_state() pure function + TrayIcon class + start_tray() entry point; pystray import guarded
- `app/routers/settings.py` - GET/POST /api/settings backed by autostart service; module-level import for mock.patch
- `app/server.py` - Added settings to router import and include_router call after history.router
- `assets/icon-watching.ico` - Green (34, 197, 94) 64x64 placeholder icon with 'W' letter
- `assets/icon-changes.ico` - Amber (245, 158, 11) 64x64 placeholder icon with '!' letter

## Decisions Made

- pystray import guarded by try/except at module level; PYSTRAY_AVAILABLE flag so run() exits cleanly on macOS/CI
- _compute_state() uses em-dash (U+2014) in tooltips matching the plan spec; pure function needs zero mocking in tests
- Placeholder icons generated during plan execution via python -c inline script; assets exist before PyInstaller bundling
- settings.router registered after history.router to maintain consistent API ordering in server.py

## Deviations from Plan

None - plan executed exactly as written. Ruff auto-reformatted the server.py import from single-line to multi-line style (pre-commit hook) -- re-staged and committed cleanly.

## Issues Encountered

- Ruff reformatted `from app.routers import ... settings ...` to multi-line import block on first commit attempt. Pre-commit hook fixed and re-staged automatically.
- Pre-existing test_port_probe.py failures (port 7433 in use in this environment) -- unchanged from prior plans, out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 9 test_tray.py + test_settings.py tests GREEN
- Full suite 170 passed (excluding pre-existing port_probe env failures)
- app/tray.py is the real implementation (replaces stub from Plan 02)
- Plan 04 (main.py --background + is_instance_running) is the final plan in Phase 15

## Self-Check: PASSED

All claimed files exist and all commits verified:
- app/tray.py: FOUND
- app/routers/settings.py: FOUND
- assets/icon-watching.ico: FOUND
- assets/icon-changes.ico: FOUND
- commit edb2b30 (Task 1): FOUND
- commit a9bc466 (Task 2): FOUND

---
*Phase: 15-system-tray-and-auto-start*
*Completed: 2026-03-15*
