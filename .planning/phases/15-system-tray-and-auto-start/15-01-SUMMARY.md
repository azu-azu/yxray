---
phase: 15-system-tray-and-auto-start
plan: 01
subsystem: testing
tags: [pytest, tdd, red-state, winreg, autostart, system-tray, fastapi, starlette]

# Dependency graph
requires:
  - phase: 14-history-and-diff-viewer
    provides: existing 153 passing tests that must remain green
provides:
  - "Failing test stubs for autostart service (register/unregister/is_enabled)"
  - "Failing test stubs for settings router (GET/POST /api/settings)"
  - "Failing test stubs for tray state computation (_compute_state)"
  - "Failing test stubs for main.py --background flag and is_instance_running"
affects: [15-02, 15-03, plans implementing autostart/settings/tray]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Graceful RED pattern: try/except ImportError sets module to None; _require() calls pytest.fail() with clear message"
    - "sys.modules injection for Windows-only winreg module — patch.dict(sys.modules, {'winreg': mock}) before function call"
    - "Pure function test isolation — _compute_state() tested without pystray or OS dependency"

key-files:
  created:
    - tests/test_autostart.py
    - tests/test_settings.py
    - tests/test_tray.py
    - tests/test_main.py
  modified: []

key-decisions:
  - "Graceful RED pattern used throughout: ImportError caught at module level; _require() helper provides clear FAILED message rather than collection ERROR"
  - "winreg mocked via sys.modules injection (patch.dict) — winreg is Windows-only and doesn't exist on macOS/Linux; module-level import in implementation will be deferred"
  - "test_background_flag_suppresses_browser uses hasattr(module, 'is_instance_running') as sentinel — main() already exists but --background support doesn't; this avoids false-pass from patched asyncio.run"
  - "_compute_state tests are pure function tests — no pystray/OS deps required; function takes dict and returns (state_str, tooltip_str)"

patterns-established:
  - "Graceful RED sentinel: if _module is None or function missing -> pytest.fail('X not implemented yet')"
  - "winreg sys.modules injection: patch.dict(sys.modules, {'winreg': mock_obj}) for Windows-registry tests on any platform"

requirements-completed: [APP-02, APP-05]

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 15 Plan 01: System Tray & Auto-Start -- Test Stubs Summary

**18 failing pytest stubs establishing test contracts for autostart (winreg), settings router, tray state, and main.py --background flag -- all FAILED not ERROR.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-14T18:32:53Z
- **Completed:** 2026-03-14T18:36:47Z
- **Tasks:** 2
- **Files modified:** 4 (all created)

## Accomplishments

- 6 RED stubs for `app.services.autostart` (register/unregister/is_enabled with winreg mocking)
- 5 RED stubs for `app.tray._compute_state` (pure function: idle/watching/changes states, singular vs plural)
- 4 RED stubs for `app.routers.settings` (GET/POST /api/settings with autostart mock)
- 3 RED stubs for `app.main` (--background flag + is_instance_running True/False)
- Existing 153 passing tests remain green; 3 pre-existing port_probe failures are environment-caused and unrelated

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing test stubs for autostart service and main.py** - `ff0f3c8` (test)
2. **Task 2: Write failing test stubs for settings router and tray state** - `e081a6f` (test)

## Files Created/Modified

- `tests/test_autostart.py` - 6 RED stubs: register_writes_run_key, is_enabled_false/true, unregister_removes_key/already_absent, non_windows_returns_false
- `tests/test_main.py` - 3 RED stubs: background_flag_suppresses_browser, is_instance_running_true/false
- `tests/test_settings.py` - 4 RED stubs: get_settings_enabled/disabled, post_settings_enable/disable
- `tests/test_tray.py` - 5 RED stubs: state_changes_detected, state_watching, state_idle, state_multiple_projects_aggregates, state_singular_change

## Decisions Made

- Graceful RED pattern used throughout (try/except ImportError + _require() helper) so tests report FAILED not collection ERROR -- this is the established pattern from prior phases
- winreg mocked via `patch.dict(sys.modules, {"winreg": MagicMock()})` because winreg is Windows-only; the autostart implementation will do a deferred import gated on `sys.platform == "win32"`
- `test_background_flag_suppresses_browser` uses `hasattr(_main_module, "is_instance_running")` as sentinel because `main()` already exists in app.main -- without this sentinel, the test could falsely pass when `asyncio.run` is patched and timer never fires
- `_compute_state` is designed as a pure function (dict -> tuple) so tray state tests need no pystray or OS dependency

## Deviations from Plan

None - plan executed exactly as written. Ruff linting issues (SIM117 nested-with, E501 line-too-long, I001 import-sort) were auto-fixed by pre-commit hooks and re-staged.

## Issues Encountered

- Pre-existing test_port_probe.py failures (3 tests) -- port 7433 is in use in the current environment. These existed before this plan and are out of scope. Documented in deferred items.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 18 test stubs are in RED state and ready to be driven GREEN by Plans 02 and 03
- Plan 02 target: `app/services/autostart.py` (drives test_autostart.py GREEN)
- Plan 03 targets: `app/routers/settings.py`, `app/tray.py`, main.py --background flag (drives remaining stubs GREEN)
- No blockers

---
*Phase: 15-system-tray-and-auto-start*
*Completed: 2026-03-14*
