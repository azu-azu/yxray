---
phase: 12-file-watcher
plan: "05"
subsystem: ui
tags: [watchdog, sse, react, tailwind, file-watcher, human-verify]

# Dependency graph
requires:
  - phase: 12-04
    provides: Amber badge in Sidebar wired to Zustand changedCount via useWatchEvents SSE hook

provides:
  - Human sign-off on WATCH-01 (badge appears within 2s of file modification)
  - Human sign-off on WATCH-02 (automatic observer selection — no manual config)
  - Human sign-off on WATCH-03 (/api/watch/status correct has_any_commits + total_workflows)
  - Bug fixes for three live correctness issues discovered during verification

affects: [phase-13-save-history, phase-14-diff-view]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SSE seed pattern: on subscriber connect, push current _change_counts immediately so badge state is visible without any file event"
    - "Watchdog recursive=True required for nested project structures — non-recursive misses subdirectory workflows"
    - "rglob('*') pattern for recursive workflow counting matches watchdog recursive observer scope"

key-files:
  created: []
  modified:
    - app/services/git_ops.py
    - app/services/watcher_manager.py
    - app/routers/watch.py
    - tests/test_watch.py

key-decisions:
  - "WORKFLOW_SUFFIXES extended to .yxmc, .yxzp, .yxapp — all five Alteryx file types now watched and counted"
  - "watchdog recursive=True — subdirectory workflows trigger events; matches Alteryx project structures which nest workflows in subfolders"
  - "SSE seed on connect: new subscribers receive current badge state immediately — prevents stale UI when page reloads or reconnects"
  - "count_workflows uses rglob for consistency with recursive observer scope"

patterns-established:
  - "Verification-driven fixes: human live-test is a final correctness gate that catches OS-level and real-world issues unit tests cannot"

requirements-completed: [WATCH-01, WATCH-02, WATCH-03]

# Metrics
duration: ~30min (verification session including fixes)
completed: 2026-03-14
---

# Phase 12 Plan 05: File Watcher Human Verification Summary

**All three WATCH requirements confirmed live: amber badge appears within 2 seconds of .yxwz modification, observer selection is automatic, /api/watch/status returns correct data — three correctness bugs fixed during verification session**

## Performance

- **Duration:** ~30 min (verification session including live fixes)
- **Started:** 2026-03-14T15:53:00Z
- **Completed:** 2026-03-14T~16:25:00Z
- **Tasks:** 1 (human-verify checkpoint — approved)
- **Files modified:** 4

## Accomplishments

- Human confirmed amber badge appears in the sidebar within 2 seconds of modifying a .yxwz file in a registered project folder (WATCH-01)
- Human confirmed observer selection is automatic — no manual configuration required (WATCH-02)
- Human confirmed /api/watch/status returns correct `has_any_commits`, `changed_count`, and `total_workflows` (WATCH-03)
- Badge confirmed amber/orange, right-aligned, shows plain number, disappears when count returns to 0 (Test 4)
- Three correctness bugs discovered and fixed during the live verification session before final approval

## Task Commits

This plan is a human-verify checkpoint; no new task commits were created by the executor. The verification session produced two fix commits on the `product` branch:

1. **Extend WORKFLOW_SUFFIXES** - `02a7af6` (feat) — added .yxmc, .yxzp, .yxapp
2. **Fix badge on connect + recursive watching** - `e65eb44` (fix) — SSE seed, recursive=True, rglob

## Files Created/Modified

- `app/services/git_ops.py` — WORKFLOW_SUFFIXES extended; `count_workflows` changed to `rglob` for recursive counting
- `app/services/watcher_manager.py` — `recursive=False` changed to `recursive=True` in watchdog observer
- `app/routers/watch.py` — SSE generator now seeds new subscriber queues with current `_change_counts` state on connect
- `tests/test_watch.py` — Tests updated to cover new file types and SSE seed behaviour

## Decisions Made

- `WORKFLOW_SUFFIXES` now covers all five Alteryx file types (.yxmd, .yxwz, .yxmc, .yxzp, .yxapp) — macros and analytic app packages are workflow artifacts too
- watchdog observers run with `recursive=True` — Alteryx projects routinely nest workflows in subdirectories; non-recursive watching missed all of them
- SSE seed on connect sends current badge state immediately — prevents stale UI after page reload or reconnect when files are already modified
- `count_workflows` switched from `glob` to `rglob` so its count matches what the recursive observer actually watches

## Deviations from Plan

### Auto-fixed Issues (applied during live verification before user approval)

**1. [Rule 1 - Bug] Extended WORKFLOW_SUFFIXES to all Alteryx file types**
- **Found during:** Task 1 (human-verify checkpoint — pre-approval fix)
- **Issue:** WORKFLOW_SUFFIXES only included .yxmd and .yxwz; .yxmc (macro), .yxzp (package), .yxapp (analytic app) were silently ignored
- **Fix:** Added three missing suffixes to the frozenset in git_ops.py and updated watchdog patterns in watcher_manager.py
- **Files modified:** app/services/git_ops.py, app/services/watcher_manager.py, tests/test_watch.py
- **Verification:** Tests updated and passing; user confirmed badge responds to .yxwz in live test
- **Committed in:** `02a7af6`

**2. [Rule 1 - Bug] Fixed watchdog non-recursive observation**
- **Found during:** Task 1 (human-verify checkpoint — pre-approval fix)
- **Issue:** `schedule(handler, path, recursive=False)` meant files in subdirectories never triggered events; Alteryx projects commonly nest workflows
- **Fix:** Changed to `recursive=True`
- **Files modified:** app/services/watcher_manager.py
- **Verification:** Live test confirmed events from subdirectory files
- **Committed in:** `e65eb44`

**3. [Rule 1 - Bug] Fixed count_workflows to use rglob (recursive)**
- **Found during:** Task 1 (human-verify checkpoint — pre-approval fix)
- **Issue:** `count_workflows` used `glob('*')` (non-recursive) so `total_workflows` in /api/watch/status undercounted projects with nested folders
- **Fix:** Changed to `rglob('*')` so count matches the recursive observer scope
- **Files modified:** app/services/git_ops.py
- **Verification:** /api/watch/status `total_workflows` now matches actual file count including subdirectories
- **Committed in:** `e65eb44`

**4. [Rule 1 - Bug] Fixed SSE seed — new subscribers received no initial state**
- **Found during:** Task 1 (human-verify checkpoint — pre-approval fix)
- **Issue:** A new SSE subscriber got no events until the next file change; if files were already modified before the page loaded, the badge stayed blank
- **Fix:** On connect, seed the subscriber queue with one `badge_update` event per project that has a non-zero `_change_counts` entry
- **Files modified:** app/routers/watch.py, tests/test_watch.py
- **Verification:** Badge appears immediately on page load when files are already modified
- **Committed in:** `e65eb44`

---

**Total deviations:** 4 auto-fixed (all Rule 1 — bugs)
**Impact on plan:** All four fixes were correctness requirements for WATCH-01 to pass in a real environment; the verification checkpoint acted as the integration test that caught them.

## Issues Encountered

None beyond the four bugs above, all resolved before user approval.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 12 (File Watcher) fully complete: all five WATCH requirements verified end-to-end by human in a live session
- WatcherManager, SSE endpoints, and Sidebar badge are production-ready
- Phase 13 (Save/History) can rely on watcher infrastructure: `WatcherManager.get_changed_workflows(project_id)` and the changedCount Zustand field are stable APIs
- No blockers

---
*Phase: 12-file-watcher*
*Completed: 2026-03-14*
