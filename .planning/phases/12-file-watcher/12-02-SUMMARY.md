---
phase: 12-file-watcher
plan: 02
subsystem: services, testing
tags: [watchdog, asyncio, threading, tdd, sse, observer-pattern]

# Dependency graph
requires:
  - phase: 12-file-watcher
    plan: 01
    provides: git_changed_workflows, count_workflows, git_has_commits, is_network_path

provides:
  - app/services/watcher_manager.py with WatcherManager class and watcher_manager singleton
  - Full observer lifecycle: start_watching (idempotent), stop_watching, subscribe, unsubscribe, clear_count, get_status
  - thread-safe badge_update SSE push via loop.call_soon_threadsafe

affects:
  - 12-03 (SSE router imports watcher_manager.subscribe/unsubscribe)
  - 13-xx (clear_count called after successful git commit to reset badge)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Thread-boundary bridge: watchdog daemon thread -> asyncio event loop via loop.call_soon_threadsafe
    - Debounce pattern: threading.Timer(1.5s) cancels-and-restarts on each file event
    - Snapshot iteration: list(self._subscribers) to avoid mutation during SSE fan-out
    - Lazy config import: get_status() imports config_store inside method body to avoid circular imports

key-files:
  created:
    - app/services/watcher_manager.py
  modified:
    - tests/test_watch.py

key-decisions:
  - "WatcherManager uses PollingObserver(timeout=5) for network/UNC paths and native Observer for local paths"
  - "loop.call_soon_threadsafe used for all cross-thread queue pushes — asyncio.Queue is not thread-safe"
  - "_WorkflowEventHandler uses on_any_event (not on_modified) to catch Alteryx temp-file-rename save pattern"
  - "get_status() lazy-imports config_store inside method body to avoid circular import at module load time"
  - "contextlib.suppress(ValueError) used in unsubscribe() per ruff SIM105 — replaces try/except/pass pattern"

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 12 Plan 02: WatcherManager Singleton Summary

**WatcherManager singleton orchestrating watchdog observer lifecycles with debounced rescans and thread-safe asyncio SSE badge_update fan-out via loop.call_soon_threadsafe**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-14T15:24:50Z
- **Completed:** 2026-03-14T15:28:17Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Unskipped test_badge_push_on_rescan and test_polling_observer_for_network with real implementations
- Created app/services/watcher_manager.py with full WatcherManager class and watcher_manager singleton
- Thread-boundary bridge correctly uses loop.call_soon_threadsafe for all asyncio queue pushes
- PollingObserver(timeout=5) selected automatically for network/UNC paths; native Observer for local paths
- Debounce via threading.Timer(1.5s) with cancel-and-restart on each file event
- All 9 test_watch.py non-integration tests pass GREEN; full suite shows no new regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Enable skipped WatcherManager tests (RED)** - `0891a13` (test)
2. **Task 2: Implement WatcherManager singleton (GREEN)** - `d89f8aa` (feat)

_Note: TDD tasks have separate test and feat commits_

## Files Created/Modified

- `app/services/watcher_manager.py` - WatcherManager class with full lifecycle management + module-level singleton
- `tests/test_watch.py` - Unskipped and implemented test_badge_push_on_rescan and test_polling_observer_for_network

## Decisions Made

- `WatcherManager` uses `PollingObserver(timeout=5)` for UNC/network paths detected by `is_network_path()`; native OS `Observer` for all other paths
- `loop.call_soon_threadsafe(q.put_nowait, event)` is the only correct way to push to asyncio queues from watchdog daemon threads — direct `q.put_nowait()` from a watchdog thread is a data race
- `_WorkflowEventHandler.on_any_event` instead of `on_modified` is required because Alteryx saves workflows via atomic temp-file rename (creates a new file, then renames), which fires `FileCreatedEvent` not `FileModifiedEvent`
- `get_status()` lazy-imports `config_store` inside the method body to break a potential circular import chain at module load time
- `contextlib.suppress(ValueError)` used in `unsubscribe()` per ruff SIM105 lint rule

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff linting failures on initial test file**
- **Found during:** Task 1 commit
- **Issue:** Nested `with` statements violated SIM117; long lines violated E501
- **Fix:** Flattened nested `with` blocks to parenthesized multi-context form; reformatted long strings
- **Files modified:** tests/test_watch.py
- **Commit:** 0891a13

**2. [Rule 3 - Blocking] Ruff linting failures on watcher_manager.py**
- **Found during:** Task 2 commit
- **Issue:** Docstring line too long (E501); try/except/pass instead of contextlib.suppress (SIM105)
- **Fix:** Shortened docstring; added `import contextlib`; replaced try/except/pass with contextlib.suppress; ruff auto-fixed the final nested-with issue
- **Files modified:** app/services/watcher_manager.py
- **Commit:** d89f8aa

## Issues Encountered

Pre-existing `test_port_probe.py` failures (3 tests) were present before this plan — port 7433 already bound on the machine. Not caused by this plan. All other 128 tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `watcher_manager` singleton is importable: `from app.services.watcher_manager import watcher_manager`
- Plan 03 can implement the SSE router using `watcher_manager.subscribe()` / `watcher_manager.unsubscribe()`
- 3 integration stubs in test_watch.py remain skipped (Plan 03 will unskip them)
- Phase 13 can call `watcher_manager.clear_count(project_id)` after successful git commits
- No blockers

## Self-Check: PASSED

- FOUND: app/services/watcher_manager.py
- FOUND: commit 0891a13 (test RED)
- FOUND: commit d89f8aa (feat GREEN)

---
*Phase: 12-file-watcher*
*Completed: 2026-03-14*
