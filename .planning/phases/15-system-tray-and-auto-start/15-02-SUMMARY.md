---
phase: 15-system-tray-and-auto-start
plan: 02
subsystem: autostart-service
tags: [python, winreg, autostart, background-mode, pyinstaller, tdd, green]

# Dependency graph
requires:
  - phase: 15-system-tray-and-auto-start
    plan: 01
    provides: RED test stubs for autostart, main.py background flag, is_instance_running
provides:
  - "app/services/autostart.py with register/unregister/is_autostart_enabled (winreg, deferred import)"
  - "app/main.py with is_instance_running(), --background flag, tray thread stub, autostart registration"
  - "app/tray.py stub (start_tray) enabling tray import before Plan 03 pystray implementation"
  - "app.spec with console=False, pystray/PIL hiddenimports, three icon asset datas entries"
affects: [15-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred winreg import (inside function body, after platform guard) for cross-platform CI safety"
    - "is_instance_running delegates to find_available_port(count=1) so test patches on find_available_port propagate"
    - "Tray stub module (app/tray.py) created before full Plan 03 pystray implementation to satisfy import"

key-files:
  created:
    - app/services/autostart.py
    - app/tray.py
  modified:
    - app/main.py
    - app.spec

key-decisions:
  - "is_instance_running delegates to find_available_port(start=7433, count=1) so test_background_flag_suppresses_browser patch on find_available_port propagates correctly (port 7433 in use in dev environment)"
  - "app/tray.py stub created (Rule 3 auto-fix) because test_main.py does not mock 'from app import tray' — stub prevents ImportError during test run before Plan 03 implements pystray"
  - "PIL removed from app.spec excludes list (was excluded in Phase 10 debug spec; pystray now requires Pillow)"

requirements-completed: [APP-02]

# Metrics
duration: 4min
completed: 2026-03-15
---

# Phase 15 Plan 02: Autostart Service + main.py Background Mode Summary

**Autostart service with Windows HKCU Run key registration, --background flag suppression of browser open, and is_instance_running() second-instance detection; test_autostart.py and test_main.py all GREEN.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-15T01:58:59Z
- **Completed:** 2026-03-15T02:02:00Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Created `app/services/autostart.py` with `register_autostart()`, `is_autostart_enabled()`, `unregister_autostart()` — all winreg imports deferred inside function bodies with `sys.platform != "win32"` guard for macOS/CI safety
- Updated `app/main.py` with `is_instance_running()`, `--background` flag handling, autostart registration call, tray thread start, browser timer only on manual launch
- Created `app/tray.py` stub with `start_tray()` to satisfy `from app import tray` import before Plan 03 pystray implementation
- Updated `app.spec`: `console=True` → `console=False`; added pystray/PIL to hiddenimports; added three icon asset datas entries; removed PIL from excludes

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/services/autostart.py** - `7b6d544` (feat)
2. **Task 2: Update app/main.py + app.spec** - `1ad5f60` (feat)

## Files Created/Modified

- `app/services/autostart.py` - register_autostart(), is_autostart_enabled(), unregister_autostart() with deferred winreg import
- `app/tray.py` - start_tray() stub (no-op logging; Plan 03 will implement pystray)
- `app/main.py` - is_instance_running(), background_mode flag, second-instance detection, autostart registration, tray thread start, conditional browser timer
- `app.spec` - console=False, pystray/PIL hiddenimports, icon asset datas, PIL removed from excludes

## Decisions Made

- `is_instance_running()` delegates to `find_available_port(start=7433, count=1)` rather than creating its own socket directly. This ensures that `test_background_flag_suppresses_browser` (which patches `app.main.find_available_port`) causes `is_instance_running` to return False in the test context — without this, the real socket.bind on port 7433 (in-use in dev environment) would return True and trigger `sys.exit(0)`, breaking the test.
- `app/tray.py` stub created as Rule 3 auto-fix: `from app import tray` inside `main()` would raise `ImportError` during test execution because `test_main.py` does not mock that import. The stub provides the required `start_tray()` function signature.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created app/tray.py stub to satisfy tray import in main()**
- **Found during:** Task 2 — test_main.py failing with `ImportError: cannot import name 'tray' from 'app'`
- **Issue:** `app/tray.py` does not exist until Plan 03; `main()` does `from app import tray` which fails during tests since test_main.py does not patch this import
- **Fix:** Created minimal `app/tray.py` stub with `start_tray(port, server)` no-op function
- **Files modified:** `app/tray.py` (created)
- **Commit:** `1ad5f60`

**2. [Rule 1 - Bug] is_instance_running delegates to find_available_port for test compatibility**
- **Found during:** Task 2 — `test_background_flag_suppresses_browser` raised `SystemExit: 0` because is_instance_running() returned True (port 7433 in use in dev environment) before the real test logic ran
- **Issue:** Direct `socket.socket().bind()` in `is_instance_running()` was not intercepted by the test's `find_available_port` patch, so the real bind ran against the occupied port
- **Fix:** Implemented `is_instance_running()` using `find_available_port(start=7433, count=1)` so the test patch propagates correctly
- **Files modified:** `app/main.py`
- **Commit:** `1ad5f60`

## Issues Encountered

- Pre-existing test_port_probe.py failures (3 tests) — port 7433 is in use in the dev environment. These existed before this plan and are out of scope.
- test_settings.py (4) and test_tray.py (5) remain RED — Plan 03 targets.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03 target: `app/tray.py` full pystray implementation (drives test_tray.py GREEN)
- Plan 03 target: `app/routers/settings.py` (drives test_settings.py GREEN)
- All 9 Plan 02 target tests GREEN (test_autostart.py: 6, test_main.py: 3)
- No blockers

---
*Phase: 15-system-tray-and-auto-start*
*Completed: 2026-03-15*
