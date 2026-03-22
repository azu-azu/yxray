---
phase: 14-history-and-diff-viewer
plan: 03
subsystem: ui
tags: [react, typescript, tailwind, shadcn, iframe, blob-url]

# Dependency graph
requires:
  - phase: 14-01
    provides: history router endpoints (GET /api/history, GET /api/history/{sha}/diff)
  - phase: 14-02
    provides: git_log() and git_show_file() in git_ops.py

provides:
  - HistoryPanel.tsx — scrollable commit list with CommitEntry type, onSelectEntry, onUndo
  - DiffViewer.tsx — diff viewer fetching HTML report and rendering via iframe + blob URL

affects:
  - 14-04 (AppShell wiring — imports and renders both components)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Blob URL isolation pattern: fetch HTML diff report, create blob URL, render in iframe to avoid style/script collisions"
    - "Cancelled flag pattern: useEffect cleanup sets cancelled=true to prevent state updates after unmount"
    - "Relative timestamp helper: formatRelativeTime() using Date.now() arithmetic, no library dependency"

key-files:
  created:
    - app/frontend/src/components/HistoryPanel.tsx
    - app/frontend/src/components/DiffViewer.tsx
  modified: []

key-decisions:
  - "DiffViewer uses iframe + blob URL for HTML isolation — ACD diff reports contain their own style/script tags that collide if injected into the React DOM directly"
  - "retryCount state in DiffViewer triggers re-fetch on error without duplicating useEffect logic"
  - "HistoryPanel inline file selector uses tab buttons for 2-4 files, shadcn Select for 5+ files — avoids modal overhead for small file sets"

patterns-established:
  - "Blob URL pattern: createObjectURL(new Blob([html], {type: text/html})) with revokeObjectURL in cleanup"
  - "Cancelled flag: let cancelled = false; return () => { cancelled = true } prevents stale state updates"

requirements-completed: [HIST-01, HIST-02]

# Metrics
duration: ~15min
completed: 2026-03-14
---

# Phase 14 Plan 03: History and Diff Viewer Components Summary

**Pure React HistoryPanel and DiffViewer components — HistoryPanel renders commit timeline with inline file selector; DiffViewer fetches ACD HTML diff report and renders it isolated in an iframe via blob URL**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-14T22:30:00Z
- **Completed:** 2026-03-14T22:45:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- HistoryPanel renders scrollable commit list with message, author, relative timestamp, "Latest" badge on first entry
- HistoryPanel supports single-file direct selection and multi-file inline selector (tab buttons for 2-4 files, shadcn Select for 5+)
- DiffViewer fetches `/api/history/{sha}/diff` and renders HTML report in iframe via blob URL for complete style isolation
- DiffViewer handles loading spinner, first-commit friendly message, network errors with retry, and useEffect cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Create HistoryPanel.tsx** - `742c91d` (feat)
2. **Task 2: Create DiffViewer.tsx** - `106c2bd` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/frontend/src/components/HistoryPanel.tsx` - Scrollable commit list; exports CommitEntry interface and HistoryPanel component
- `app/frontend/src/components/DiffViewer.tsx` - Diff viewer; fetches HTML report and renders via iframe blob URL

## Decisions Made
- DiffViewer uses iframe + blob URL instead of raw HTML injection — ACD diff reports have their own styles/scripts that collide with the app's styles if injected directly into the React DOM tree
- retryCount state added to DiffViewer to trigger re-fetch cleanly without duplicating useEffect dependencies
- HistoryPanel inline file selector uses tab buttons for 2-4 files and shadcn Select for 5+ files to balance UX

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added error handling with try/catch in DiffViewer useEffect**
- **Found during:** Task 2 (Create DiffViewer.tsx)
- **Issue:** Plan's blob URL pattern example had no try/catch — network errors would leave loading=true forever with no recovery path
- **Fix:** Wrapped loadDiff() body in try/catch setting error state on failure; added setError(null) and setIframeSrc(null) reset at start of each load attempt
- **Files modified:** app/frontend/src/components/DiffViewer.tsx
- **Verification:** TypeScript compiles cleanly; component handles fetch errors gracefully with visible error message and Retry button
- **Committed in:** 106c2bd (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (missing critical error handling)
**Impact on plan:** Auto-fix required for correct operation. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HistoryPanel and DiffViewer are complete pure components ready for AppShell wiring in Plan 04
- Props interfaces match the Plan 04 AppShell integration spec exactly
- Both components compile with no TypeScript errors

---
*Phase: 14-history-and-diff-viewer*
*Completed: 2026-03-14*
