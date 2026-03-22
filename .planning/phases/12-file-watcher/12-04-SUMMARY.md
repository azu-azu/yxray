---
phase: 12-file-watcher
plan: "04"
subsystem: ui
tags: [react, zustand, sse, eventSource, tailwind, typescript]

# Dependency graph
requires:
  - phase: 12-03
    provides: /api/watch/events SSE endpoint streaming badge_update events with project_id and changed_count

provides:
  - Zustand Project.changedCount optional field tracking live file-change counts per project
  - setChangedCount(id, count) Zustand action for updating changedCount from SSE events
  - useWatchEvents hook subscribing to /api/watch/events SSE and dispatching setChangedCount
  - Amber badge (bg-amber-500) in Sidebar project rows showing live changed-file count
  - App.tsx top-level useWatchEvents() call ensuring badge updates arrive regardless of active project

affects: [phase-13-save-history, phase-14-diff-view, sidebar-layout]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SSE hook pattern: useEffect opens EventSource, parses onmessage, closes on cleanup"
    - "Zustand optional field pattern: changedCount?: number on Project — absent means unset, 0 means watched with no changes"
    - "Amber badge placement: ml-auto shrink-0 inside flex button row with truncate name span"

key-files:
  created:
    - app/frontend/src/hooks/useWatchEvents.ts
  modified:
    - app/frontend/src/store/useProjectStore.ts
    - app/frontend/src/components/Sidebar.tsx
    - app/frontend/src/App.tsx

key-decisions:
  - "useWatchEvents called at App.tsx top level (not Sidebar) so badge updates arrive regardless of which view is active"
  - "Badge hidden entirely when changedCount is 0 or undefined — no '0' badge clutters the UI"
  - "EventSource auto-reconnect relied on for same-host SSE — no manual reconnect logic needed"

patterns-established:
  - "SSE subscription hook: single useEffect, onmessage dispatches to Zustand, onerror logs in DEV only, cleanup calls es.close()"
  - "Flex project row: truncate name + ml-auto badge — handles long project names without pushing badge off screen"

requirements-completed: [WATCH-01]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 12 Plan 04: File Watcher Frontend Badge Summary

**Live amber change-count badge added to Sidebar via Zustand changedCount field, useWatchEvents SSE hook, and unconditional App.tsx wiring**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-14T15:30:32Z
- **Completed:** 2026-03-14T15:32:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended Zustand Project interface with `changedCount?: number` and `setChangedCount` action
- Created `useWatchEvents.ts` hook that opens an EventSource to `/api/watch/events`, parses `badge_update` events, and dispatches `setChangedCount` — closes cleanly on unmount
- Sidebar project button now uses flex layout with a `truncate` name span and an amber badge (`bg-amber-500`) that only renders when `changedCount > 0`
- `useWatchEvents()` called unconditionally at App.tsx top level so badge state updates regardless of which project is active

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Zustand store + create useWatchEvents hook** - `eaf7d51` (feat)
2. **Task 2: Add badge to Sidebar + wire hook in App.tsx** - `6b84d52` (feat)

## Files Created/Modified

- `app/frontend/src/store/useProjectStore.ts` - Added `changedCount?: number` to Project interface; added `setChangedCount(id, count)` action
- `app/frontend/src/hooks/useWatchEvents.ts` - New hook: subscribes to `/api/watch/events` SSE, dispatches `setChangedCount` on `badge_update` events
- `app/frontend/src/components/Sidebar.tsx` - Button changed to flex layout; amber badge rendered conditionally on `changedCount > 0`
- `app/frontend/src/App.tsx` - Import and unconditional call of `useWatchEvents()` at component top level

## Decisions Made

- `useWatchEvents` called at App.tsx top level rather than inside Sidebar — ensures badge updates arrive regardless of which view is active; consistent with how global state hooks are wired
- Badge hidden entirely when `changedCount` is 0 or `undefined` — avoids "0" badge noise while still showing no badge for unwatch or clean projects
- No manual reconnect logic in `useWatchEvents` — same-host EventSource auto-reconnects after error; browser handles it natively

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Python test suite has 3 pre-existing failures in `test_port_probe.py` due to ports 7433-7443 already in use on the dev machine. These are environment-level failures unrelated to this plan. 131 tests passed, 1 xfailed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Live badge infrastructure complete end-to-end: watchdog -> WatcherManager -> SSE endpoint -> useWatchEvents -> Zustand -> Sidebar badge
- Phase 13 (Save/History) can build on the watcher infrastructure already in place
- No blockers

---
*Phase: 12-file-watcher*
*Completed: 2026-03-14*

## Self-Check: PASSED

- FOUND: app/frontend/src/hooks/useWatchEvents.ts
- FOUND: app/frontend/src/store/useProjectStore.ts
- FOUND: app/frontend/src/components/Sidebar.tsx
- FOUND: app/frontend/src/App.tsx
- FOUND: .planning/phases/12-file-watcher/12-04-SUMMARY.md
- FOUND commit eaf7d51 (Task 1)
- FOUND commit 6b84d52 (Task 2)
