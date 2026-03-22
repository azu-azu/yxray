---
phase: 12-file-watcher
plan: "03"
subsystem: api
tags: [fastapi, sse, watchdog, asyncio, lifespan, event-stream]

requires:
  - phase: 12-02
    provides: WatcherManager singleton with set_event_loop/start_watching/stop_watching/subscribe/unsubscribe/get_status API
  - phase: 11-01
    provides: app/server.py FastAPI app, app/routers/projects.py add/remove project endpoints

provides:
  - GET /api/watch/events — EventSourceResponse SSE stream delivering badge_update events to React clients
  - GET /api/watch/status — JSON per-project status dict {changed_count, total_workflows, has_any_commits}
  - FastAPI lifespan context manager that starts WatcherManager on startup and stops all observers on shutdown
  - projects.py add_project and remove_project notify watcher_manager on each change

affects:
  - 13-save-version
  - any phase connecting frontend badge UI to SSE stream

tech-stack:
  added: [sse-starlette (EventSourceResponse), asynccontextmanager (stdlib)]
  patterns:
    - Request-aware async generator with asyncio.wait_for + request.is_disconnected() for clean SSE disconnect handling
    - FastAPI lifespan replaces deprecated on_event startup/shutdown handlers
    - Module-level watcher_manager singleton imported into both server.py and projects.py

key-files:
  created:
    - app/routers/watch.py
  modified:
    - app/server.py
    - app/routers/projects.py
    - tests/test_watch.py

key-decisions:
  - "SSE generator uses asyncio.wait_for(q.get(), timeout=0.5) + request.is_disconnected() instead of bare await q.get() — allows clean disconnect detection and makes generator testable without ASGI transport"
  - "test_sse_endpoint_headers calls route handler directly with AsyncMock(return_value=True) for is_disconnected — TestClient.stream() hangs on infinite SSE generators because Starlette TestClient only sends http.disconnect after response_complete is set"
  - "lifespan accesses watcher_manager._observers directly in shutdown loop — acceptable since WatcherManager is a singleton in the same process and stop_watching handles all cleanup"

patterns-established:
  - "SSE Pattern: EventSourceResponse wrapping async generator that polls queue with wait_for and checks is_disconnected() each iteration"
  - "Lifespan Pattern: load_config() in lifespan startup to start watchers for already-registered projects"

requirements-completed: [WATCH-01, WATCH-02, WATCH-03]

duration: 25min
completed: "2026-03-14"
---

# Phase 12 Plan 03: Watch Router + Lifespan Wiring Summary

**SSE /api/watch/events and /api/watch/status endpoints wired into FastAPI via lifespan, with project add/remove hooks pushing events live to connected React clients**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-14T15:22:57Z
- **Completed:** 2026-03-14T15:47:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `app/routers/watch.py` with `GET /api/watch/events` (infinite SSE stream via `EventSourceResponse`) and `GET /api/watch/status` (per-project JSON badge state)
- Replaced bare `FastAPI(...)` constructor with lifespan context manager in `server.py` that calls `set_event_loop + start_watching` for all registered projects on startup and `stop_watching` for all on shutdown
- Added `watcher_manager.start_watching` / `stop_watching` calls to `projects.py` `add_project` / `remove_project` so live projects are watched immediately after registration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create watch router (SSE events + status endpoints)** - `2c6d5fa` (feat)
2. **Task 2: Wire lifespan into server.py + register watch router + hook projects.py** - `4f0e228` (feat)

## Files Created/Modified

- `app/routers/watch.py` — New router: GET /api/watch/events (EventSourceResponse + disconnect-aware generator) and GET /api/watch/status
- `app/server.py` — Added asynccontextmanager lifespan, watcher_manager import, config_store import; watch router registered
- `app/routers/projects.py` — Added watcher_manager import; start_watching/stop_watching calls in add_project/remove_project
- `tests/test_watch.py` — Implemented 3 previously-skipped integration tests (test_sse_endpoint_headers, test_watch_status_no_commits, test_watch_status_total_workflows)

## Decisions Made

- **SSE disconnect detection:** Used `asyncio.wait_for(q.get(), timeout=0.5)` + `request.is_disconnected()` in the generator instead of bare `await q.get()`. The plan specified `await q.get()` but this causes `TestClient.stream()` to hang indefinitely because Starlette's TestClient only sends `http.disconnect` after `response_complete` is set — which never happens with an infinite generator. The `wait_for` pattern is also safer in production since it allows the server to detect client disconnect within 0.5s rather than waiting for the next event.

- **SSE test approach:** `test_sse_endpoint_headers` calls the route handler function directly with a mocked `Request` (where `is_disconnected()` immediately returns `True`) rather than using `TestClient.stream()`. This verifies the `EventSourceResponse` object's `status_code` and `media_type` without needing a full ASGI transport connection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SSE generator made disconnect-responsive to fix TestClient hang**
- **Found during:** Task 1 (test_sse_endpoint_headers verification)
- **Issue:** The plan's `async def event_generator()` used bare `await q.get()` which blocks indefinitely. `TestClient.stream()` hangs because the Starlette TestClient transport waits for `response_complete` before sending `http.disconnect`, creating a deadlock with an infinite generator.
- **Fix:** Changed generator to use `asyncio.wait_for(q.get(), timeout=_QUEUE_POLL_INTERVAL)` + `if await request.is_disconnected(): break`. Route handler signature updated to `async def watch_events(request: Request)`.
- **Files modified:** `app/routers/watch.py`, `tests/test_watch.py`
- **Verification:** `test_sse_endpoint_headers` passes in under 1s; all 12 test_watch.py tests pass
- **Committed in:** `2c6d5fa` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The fix improves production behavior (cleaner disconnect detection) while making tests tractable. No scope creep.

## Issues Encountered

- `TestClient.stream()` for SSE endpoints with infinite generators is a known limitation: Starlette's test transport only sends `http.disconnect` after `response_complete`, causing a deadlock. Resolved by making the generator responsive to disconnect via `asyncio.wait_for`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 13 (Save Version) can call `GET /api/watch/status` to check `has_any_commits` before committing
- Phase 13 can call `watcher_manager.clear_count(project_id)` after a successful commit to reset the badge
- Frontend SSE subscription (`EventSource("/api/watch/events")`) ready to connect and receive `badge_update` events
- All 12 test_watch.py tests GREEN; full test suite passes (131 pass, 3 pre-existing port-probe failures unrelated to this phase)

---
*Phase: 12-file-watcher*
*Completed: 2026-03-14*
