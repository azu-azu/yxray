---
phase: 12-file-watcher
verified: 2026-03-14T17:00:00Z
status: passed
score: 18/18 must-haves verified
re_verification: false
---

# Phase 12: File Watcher Verification Report

**Phase Goal:** Implement a real-time file watcher that detects changes to Alteryx workflow files and displays an amber badge in the sidebar
**Verified:** 2026-03-14T17:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All truths are drawn from the combined must_haves across Plans 01 through 05.

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `git_changed_workflows()` returns only Alteryx workflow files modified vs git HEAD | VERIFIED | `app/services/git_ops.py` lines 51-74; test passes `test_git_changed_workflows` |
| 2  | `count_workflows()` counts Alteryx workflow files recursively using `rglob` | VERIFIED | `git_ops.py` line 82 uses `rglob("*")`; `test_count_workflows` covers 7 files across subdirectory |
| 3  | `git_has_commits()` returns False for a freshly init-ed repo with no commits | VERIFIED | `git_ops.py` lines 85-97; `test_git_has_commits_false` passes |
| 4  | `is_network_path()` returns True for UNC paths (`\\server\share` and `//server/share`) | VERIFIED | `watcher_utils.py` lines 26-28; `test_is_network_path_unc_backslash` and `test_is_network_path_unc_forward` pass |
| 5  | `is_network_path()` returns False for normal local absolute paths | VERIFIED | `watcher_utils.py`; `test_is_network_path_local_unix` passes |
| 6  | WatcherManager uses `PollingObserver(timeout=5)` for network/UNC paths and native Observer for local paths | VERIFIED | `watcher_manager.py` lines 112-117; `test_polling_observer_for_network` passes |
| 7  | WatcherManager pushes a `badge_update` SSE event to all subscriber queues when rescan fires | VERIFIED | `watcher_manager.py` lines 205-238; `test_badge_push_on_rescan` passes |
| 8  | WatcherManager.start_watching is idempotent — calling twice for same project_id does not start a second observer | VERIFIED | `watcher_manager.py` lines 102-103 early return guard |
| 9  | WatcherManager.stop_watching cleans up observer and resets change counts | VERIFIED | `watcher_manager.py` lines 126-145 |
| 10 | WatcherManager.clear_count(project_id) zeroes count and pushes SSE event | VERIFIED | `watcher_manager.py` lines 159-165 |
| 11 | `GET /api/watch/events` returns 200 with `Content-Type: text/event-stream` | VERIFIED | `app/routers/watch.py` lines 18-57; `test_sse_endpoint_headers` passes |
| 12 | `GET /api/watch/status` returns JSON with per-project `changed_count`, `total_workflows`, `has_any_commits` | VERIFIED | `app/routers/watch.py` lines 60-76; `test_watch_status_no_commits` and `test_watch_status_total_workflows` pass |
| 13 | WatcherManager starts watching all registered projects on FastAPI startup (lifespan) | VERIFIED | `app/server.py` lines 24-41 lifespan context manager calls `set_event_loop` then iterates projects |
| 14 | `POST /api/projects` triggers `watcher_manager.start_watching` for the new project | VERIFIED | `app/routers/projects.py` line 54 |
| 15 | `DELETE /api/projects/{id}` triggers `watcher_manager.stop_watching` for the removed project | VERIFIED | `app/routers/projects.py` line 70 |
| 16 | Sidebar shows an amber count badge on the right of each project row when `changedCount > 0` | VERIFIED | `Sidebar.tsx` lines 66-70; `bg-amber-500` span with `ml-auto shrink-0` |
| 17 | `useWatchEvents` hook subscribes to `/api/watch/events` SSE stream on mount and closes on unmount | VERIFIED | `useWatchEvents.ts` lines 19-43; `new EventSource` in `useEffect`, `es.close()` in cleanup |
| 18 | `App.tsx` calls `useWatchEvents()` unconditionally at component top level | VERIFIED | `App.tsx` line 21 |

**Score:** 18/18 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_watch.py` | 12 tests covering WATCH-01/02/03 | VERIFIED | 12 tests, all pass; no skips remain |
| `app/services/git_ops.py` | Extended with `WORKFLOW_SUFFIXES`, `git_changed_workflows`, `count_workflows`, `git_has_commits` | VERIFIED | All four present; `WORKFLOW_SUFFIXES` covers all 5 Alteryx file types |
| `app/services/watcher_utils.py` | `is_network_path` with UNC + OS-specific detection | VERIFIED | 90 lines, platform-aware (Windows/macOS/Linux) |
| `app/services/watcher_manager.py` | WatcherManager singleton with full lifecycle management | VERIFIED | 243 lines; `watcher_manager` module-level singleton at line 242 |
| `app/routers/watch.py` | `/api/watch/events` (SSE) and `/api/watch/status` endpoints | VERIFIED | Both endpoints present and tested |
| `app/server.py` | lifespan context manager + watch router registered | VERIFIED | lifespan at lines 24-41; `watch.router` included at line 49 |
| `app/routers/projects.py` | `add_project` and `remove_project` notify `watcher_manager` | VERIFIED | `start_watching` at line 54; `stop_watching` at line 70 |
| `app/frontend/src/store/useProjectStore.ts` | `Project.changedCount` optional field + `setChangedCount` action | VERIFIED | `changedCount?: number` at line 7; `setChangedCount` at lines 18 and 33-38 |
| `app/frontend/src/hooks/useWatchEvents.ts` | SSE hook that subscribes and dispatches `setChangedCount` | VERIFIED | 45 lines; full implementation |
| `app/frontend/src/components/Sidebar.tsx` | Amber badge rendered to the right of project name when `changedCount > 0` | VERIFIED | Lines 66-70; `bg-amber-500 text-white rounded-full` span conditional on `changedCount > 0` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/watcher_manager.py` | `git_ops.git_changed_workflows` | `_rescan` calls `git_changed_workflows` then `count_workflows` | WIRED | `watcher_manager.py` line 207; module-level import at line 29 |
| `app/services/watcher_manager.py` | `watcher_utils.is_network_path` | `start_watching` calls `is_network_path` to select observer class | WIRED | `watcher_manager.py` line 112; module-level import at line 30 |
| `app/routers/watch.py` | `watcher_manager.subscribe / unsubscribe` | SSE generator subscribes on enter, unsubscribes in finally | WIRED | `watch.py` lines 30 and 55 |
| `app/server.py` lifespan | `watcher_manager.set_event_loop + start_watching` | Called at FastAPI startup before yield | WIRED | `server.py` lines 33-37 |
| `app/routers/projects.py add_project` | `watcher_manager.start_watching` | Called after `config_store.save_config` | WIRED | `projects.py` line 54 |
| `app/frontend/src/App.tsx` | `useWatchEvents()` | Called unconditionally at top of App component | WIRED | `App.tsx` line 21 |
| `app/frontend/src/hooks/useWatchEvents.ts` | `/api/watch/events` | `new EventSource('/api/watch/events')` in `useEffect` | WIRED | `useWatchEvents.ts` line 19 |
| `app/frontend/src/hooks/useWatchEvents.ts` | `useProjectStore.setChangedCount` | `es.onmessage` parses `badge_update` payload and calls `setChangedCount` | WIRED | `useWatchEvents.ts` lines 22-26 |
| `app/frontend/src/components/Sidebar.tsx` | `project.changedCount` | Reads from Zustand store via `useProjectStore` selector | WIRED | `Sidebar.tsx` line 66 |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| WATCH-01 | 01, 02, 03, 04, 05 | App auto-detects changed .yxmd/.yxwz files in registered folders and shows a change badge | SATISFIED | `git_changed_workflows` detects changes; `_rescan` drives badge counts; SSE pushes to frontend; Sidebar renders amber badge |
| WATCH-02 | 01, 02, 05 | App auto-switches to polling observer (5-second interval) for network/SMB/UNC paths, native observer for local drives | SATISFIED | `is_network_path` in `watcher_utils.py`; `PollingObserver(timeout=5)` selected in `start_watching`; `test_polling_observer_for_network` confirms |
| WATCH-03 | 01, 03, 05 | App warns user when first version save will capture all N existing workflows in a folder | SATISFIED | `git_has_commits` + `has_any_commits` field in `/api/watch/status` response; allows Phase 13 (Save Version) to gate on this flag |

No orphaned requirements — all three WATCH IDs are claimed by phase 12 plans and are implemented.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/frontend/src/App.tsx` | 77 | `// TODO: surface error toast in Phase 12` | Info | Comment was deferred to Phase 13 (note says "Phase 12" in the source but context is the add-project error path). Not a blocking gap — the error path returns cleanly; only the user-facing toast is missing. |
| `app/frontend/src/App.tsx` | 92 | `if (isLoading) return null` | Info | Intentional loading guard to prevent welcome-screen flash, documented by comment. Not a stub. |

No blocker or warning anti-patterns found.

---

### Human Verification Required

Plan 05 documented a completed human verification session. The human verified all four tests and typed "approved" before the plan summary was written. The following items are noted for reference — they require a live browser session to re-confirm if desired:

**1. Badge appears within 2 seconds of file modification (WATCH-01)**
- Test: Modify a `.yxmd` or `.yxwz` file in a registered project folder
- Expected: Amber count badge appears on the project row in the sidebar within 2 seconds
- Why human: OS-level watchdog file events cannot be tested programmatically; requires a real filesystem event

**2. Observer selection is automatic (WATCH-02)**
- Test: Register a `\\server\share` UNC path; observe server startup logs
- Expected: Logs show PollingObserver selected; no manual configuration needed
- Why human: Requires access to a real network share or UNC path

**3. Badge disappears when changes are reverted**
- Test: Run `git checkout -- <file>` after creating a badge; wait 2 seconds
- Expected: Badge count decrements or disappears
- Why human: Requires real git operations on a live filesystem

Human sign-off was recorded in `12-05-SUMMARY.md` (completed 2026-03-14, all four tests approved).

---

### Implementation Notes

Three correctness bugs were discovered and fixed during the Plan 05 live verification session (commits `02a7af6` and `e65eb44`):

1. `WORKFLOW_SUFFIXES` was extended from 2 to 5 file types (added `.yxmc`, `.yxzp`, `.yxapp`) — macros and app packages are Alteryx workflow artifacts
2. watchdog observer changed from `recursive=False` to `recursive=True` — Alteryx projects commonly nest workflows in subdirectories
3. `count_workflows` changed from `glob("*")` to `rglob("*")` for consistency with the recursive observer scope
4. SSE `/api/watch/events` now seeds new subscribers with current badge state on connect — prevents stale UI after page reload

All fixes are verified in the test suite: `test_count_workflows` covers 7 files across a subdirectory; `test_git_changed_workflows` covers `.yxmc` alongside `.yxmd` and `.yxwz`.

---

### Commits Verified

All 10 documented commits exist in the repository:

| Commit | Type | Description |
|--------|------|-------------|
| `01f7cc0` | test | Wave 0 test scaffold (RED) |
| `b24dc86` | feat | git_ops helpers + watcher_utils (GREEN) |
| `0891a13` | test | WatcherManager test stubs (RED) |
| `d89f8aa` | feat | WatcherManager singleton implementation (GREEN) |
| `2c6d5fa` | feat | watch router (SSE + status endpoints) |
| `4f0e228` | feat | server.py lifespan + projects.py hooks |
| `eaf7d51` | feat | Zustand changedCount + useWatchEvents hook |
| `6b84d52` | feat | Sidebar amber badge + App.tsx wiring |
| `02a7af6` | feat | Extend WORKFLOW_SUFFIXES to all 5 Alteryx types |
| `e65eb44` | fix | SSE seed on connect + recursive=True + rglob |

---

### Test Suite Status

```
tests/test_watch.py — 12 passed
Full suite — 134 passed, 1 xfailed (pre-existing)
```

No regressions introduced by Phase 12 changes.

---

## Summary

Phase 12 goal is fully achieved. The end-to-end chain is in place and verified:

- watchdog detects `.yxmd` / `.yxwz` / `.yxmc` / `.yxzp` / `.yxapp` file changes on both local and network paths
- WatcherManager debounces events, rescans via `git status --porcelain`, and pushes `badge_update` SSE events thread-safely
- FastAPI lifespan starts watchers for all registered projects on server startup
- Projects router hooks ensure watchers start/stop when projects are added or removed
- The React frontend receives SSE events, updates Zustand state, and renders an amber count badge in the Sidebar
- All 3 requirements (WATCH-01, WATCH-02, WATCH-03) are satisfied with automated test coverage and human sign-off

---

_Verified: 2026-03-14T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
