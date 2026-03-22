---
phase: 10-app-scaffold
plan: "01"
subsystem: api
tags: [fastapi, uvicorn, pyinstaller, pytest, starlette, spa, port-probe]

# Dependency graph
requires: []
provides:
  - "FastAPI server (app/server.py) with /health endpoint and SPAStaticFiles mount"
  - "Entry point (app/main.py) with port probe, uvicorn programmatic start, browser open"
  - "find_available_port() returning pre-bound socket to avoid race condition"
  - "SPAStaticFiles subclass for SPA client-side routing fallback"
  - "7 unit tests: 3 port probe, 3 server, 1 CLI bundle smoke test"
affects: [10-app-scaffold, 11-frontend-scaffold, 12-file-watcher, 15-system-tray]

# Tech tracking
tech-stack:
  added: [fastapi>=0.111, uvicorn>=0.29, pyinstaller>=6.6, pyinstaller-versionfile>=3.0, httpx]
  patterns:
    - "SPAStaticFiles subclass overrides get_response() to fall back to index.html"
    - "Port probe: socket.bind() loop passes bound socket directly to uvicorn.Config"
    - "uvicorn programmatic start via asyncio.run(server.serve(sockets=[sock]))"
    - "sys._MEIPASS branch in _static_dir() for PyInstaller bundle path resolution"
    - "freeze_support() first statement in __main__ guard before main()"

key-files:
  created:
    - app/__init__.py
    - app/server.py
    - app/main.py
    - tests/conftest.py
    - tests/test_port_probe.py
    - tests/test_server.py
    - tests/test_cli_bundle.py
  modified:
    - pyproject.toml

key-decisions:
  - "SPAStaticFiles subclass used instead of plain StaticFiles — Starlette StaticFiles(html=True) does not fall back to index.html for unknown paths; subclass required for SPA routing"
  - "pytest pythonpath=['.'] added to pyproject.toml so app/ package is importable in tests without src/ layout convention"
  - "SPAStaticFiles catches all exceptions from super().get_response() and falls back to index.html"

patterns-established:
  - "SPAStaticFiles: extend StaticFiles.get_response() with try/except fallback to index.html"
  - "Port probe: setsockopt(SO_REUSEADDR) + bind() loop; return bound socket to caller"
  - "Server startup: asyncio.run(uvicorn.Server(config).serve(sockets=[sock]))"

requirements-completed: [APP-01, APP-03, APP-04a]

# Metrics
duration: 11min
completed: "2026-03-13"
---

# Phase 10 Plan 01: FastAPI Backend Skeleton Summary

**FastAPI server with /health endpoint, SPAStaticFiles SPA fallback, port probe with pre-bound socket, and PyInstaller-compatible entry point — all TDD-verified in 7 unit tests**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-13T23:08:42Z
- **Completed:** 2026-03-13T23:20:07Z
- **Tasks:** 2 (TDD: RED commit + GREEN commit)
- **Files modified:** 8

## Accomplishments

- FastAPI app in `app/server.py` with `/health` returning `{status, version}` and `SPAStaticFiles` catch-all mount for SPA routing
- Entry point in `app/main.py` with `find_available_port()` (port 7433–7443 probe, pre-bound socket), uvicorn programmatic start, 1-second delayed browser open, and `freeze_support()` as first statement in `__main__` guard
- 7 TDD unit tests covering port probe (free/occupied/all-full), server health (200/body), SPA fallback, and CLI bundle importability — all GREEN
- `pyproject.toml` updated with fastapi, uvicorn, pyinstaller, pyinstaller-versionfile as runtime dependencies and `pythonpath=['.']` for test discovery

## Task Commits

1. **Task 1: Write test scaffold for port probe, server health, and CLI bundle** - `e79db82` (test)
2. **Task 2: Implement FastAPI server and entry point** - `84d8f0f` (feat)

## Files Created/Modified

- `app/__init__.py` - Empty package init
- `app/server.py` - FastAPI app with /health route, SPAStaticFiles mount, _static_dir() with sys._MEIPASS branch
- `app/main.py` - find_available_port(), uvicorn programmatic start, browser open, freeze_support() guard
- `tests/conftest.py` - FastAPI TestClient fixture with patched _static_dir()
- `tests/test_port_probe.py` - 3 unit tests for find_available_port()
- `tests/test_server.py` - 3 unit tests for /health and SPA fallback
- `tests/test_cli_bundle.py` - 1 smoke test confirming acd CLI importability
- `pyproject.toml` - Added fastapi/uvicorn/pyinstaller deps; pythonpath=['.'] for pytest

## Decisions Made

- **SPAStaticFiles subclass**: Starlette's `StaticFiles(html=True)` serves `index.html` for directory requests (`/`) but returns 404 for unknown paths like `/some-route`. A `SPAStaticFiles` subclass that overrides `get_response()` with a try/except fallback to `index.html` is required for SPA client-side routing.
- **pytest pythonpath**: The project uses a `src/` layout for the `alteryx_diff` package (exposed via `.pth` file). The `app/` package is at the repo root. Added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml` to make `app` importable in tests without restructuring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] StaticFiles(html=True) does not provide SPA 404 fallback in Starlette**

- **Found during:** Task 2 (Implement FastAPI server and entry point)
- **Issue:** The plan's research noted `StaticFiles(html=True)` handles SPA fallback, but Starlette's implementation only serves `index.html` for directory listing (`/`), not for arbitrary unknown paths. `GET /nonexistent-route` returned 404.
- **Fix:** Added `SPAStaticFiles(StaticFiles)` subclass in `app/server.py` that wraps `super().get_response()` in try/except and falls back to `index.html` on failure. Updated `test_spa_fallback` to use this class.
- **Files modified:** `app/server.py`, `tests/test_server.py`
- **Verification:** `test_spa_fallback` passes; `GET /nonexistent-route` returns 200 with index.html content.
- **Committed in:** `84d8f0f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix essential for correct SPA routing behavior. No scope creep.

## Issues Encountered

- `uv` binary not available in shell PATH; used `.venv/bin/python -m pip` directly for dependency installation. pydantic-core initially installed with wrong binary (pip `-t` flag) — fixed with `--force-reinstall`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend skeleton complete; ready for Phase 10 Plan 02 (React frontend scaffold)
- `app/server.py` exports `app` (FastAPI instance) ready for additional API routes in later phases
- `/health` endpoint usable for Phase 15 system tray health checks
- `find_available_port()` and `main()` exported from `app/main.py` for PyInstaller entry point

---
*Phase: 10-app-scaffold*
*Completed: 2026-03-13*
