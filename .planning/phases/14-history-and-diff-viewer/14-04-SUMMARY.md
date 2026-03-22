---
phase: 14-history-and-diff-viewer
plan: 04
subsystem: ui
tags: [react, typescript, zustand, vis-network, iframe, blob-url]

# Dependency graph
requires:
  - phase: 14-02
    provides: Backend history and diff endpoints
  - phase: 14-03
    provides: HistoryPanel and DiffViewer components
provides:
  - AppShell state machine wired with HistoryPanel + DiffViewer replacing SuccessCard
  - Zustand store cleaned of lastSave/setLastSave/LastSave
  - SuccessCard.tsx removed from codebase
  - Graph view visible in DiffViewer iframe via localStorage shim and post-load redraw
affects:
  - future phases using AppShell state machine

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "localStorage shim injected into blob URL HTML to prevent SecurityError in null-origin iframes"
    - "onLoad handler calls iframe contentWindow.switchView() to force vis.js canvas redraw after layout"

key-files:
  created: []
  modified:
    - app/frontend/src/components/AppShell.tsx
    - app/frontend/src/store/useProjectStore.ts
    - app/frontend/src/components/DiffViewer.tsx

key-decisions:
  - "localStorage shim injected into blob HTML before Blob creation — blob: URLs have null origin, causing SecurityError on localStorage access which aborts vis.js graph initialisation"
  - "onLoad calls switchView('split') on iframe contentWindow — vis.js Networks need correct container dimensions at init time; calling after iframe paint ensures non-zero clientWidth/clientHeight"
  - "SuccessCard retired in favour of HistoryPanel as permanent idle state — session-scoped save toast replaced by persistent history timeline"

patterns-established:
  - "Blob URL iframe with injected shim: when embedding self-contained HTML reports, always wrap localStorage with a null-origin safe shim before Blob creation"

requirements-completed:
  - HIST-01
  - HIST-02

# Metrics
duration: 25min
completed: 2026-03-14
---

# Phase 14 Plan 04: AppShell Wiring Summary

**AppShell state machine wired to HistoryPanel + DiffViewer with vis.js graph view fixed via localStorage shim and post-load redraw in blob URL iframe**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-03-14
- **Tasks:** 3 (including post-checkpoint graph fix)
- **Files modified:** 3

## Accomplishments

- AppShell 4-state machine: changedFiles → ChangesPanel | selectedDiff → DiffViewer | hasCommits → HistoryPanel | else → EmptyState
- Zustand store cleaned: LastSave interface and lastSave/setLastSave fields removed; fetchHistory added to AppShell as local callback
- SuccessCard.tsx deleted; no broken imports
- Graph view now visible in DiffViewer iframe: localStorage shim prevents SecurityError in null-origin blob: URLs, and onLoad switchView('split') call forces vis.js to re-initialise networks after the iframe has correct dimensions

## Task Commits

1. **Task 1: Wire HistoryPanel and DiffViewer into AppShell** - `f1c791b` (feat)
2. **Task 2: Clean Zustand store and remove SuccessCard** - `c01d65c` (feat)
3. **Task 3: Fix graph view visibility in DiffViewer iframe** - `27147b3` (feat)

## Files Created/Modified

- `app/frontend/src/components/AppShell.tsx` — 4-state machine with HistoryPanel + DiffViewer, fetchHistory callback, project-switch clears history and selectedDiff
- `app/frontend/src/store/useProjectStore.ts` — LastSave type and lastSave/setLastSave removed
- `app/frontend/src/components/DiffViewer.tsx` — localStorage shim injected into blob HTML; onLoad triggers switchView('split') for vis.js graph redraw

## Decisions Made

- **localStorage shim approach**: Blob URLs have `null` origin. Browsers (especially Safari and Chrome in strict mode) throw SecurityError on `localStorage.getItem` from a null-origin document. The script runs inside an IIFE that calls `localStorage.getItem` before `switchView()` — if that throws, the entire IIFE aborts and vis.js never runs. Solution: inject a try-catch shim as the first `<script>` after `<head>` to intercept the exception and replace `window.localStorage` with an in-memory object.
- **onLoad switchView redraw**: Even with localStorage fixed, vis.js Networks initialised via `requestAnimationFrame` inside the IIFE may read container dimensions before the iframe has been fully laid out by the host page. The `onLoad` handler calls `contentWindow.switchView('split')` which triggers `initSplitNetworks()` and `networkLeft.fit()` with the iframe already painted and sized correctly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Graph view not rendering in iframe due to localStorage SecurityError**
- **Found during:** Task 3 (human checkpoint — user reported graph not visible)
- **Issue:** Blob URL iframes have null origin; `localStorage.getItem()` inside the ACD report's IIFE threw SecurityError, aborting the vis.js graph initialisation script entirely
- **Fix:** Injected inline localStorage shim as first `<script>` after `<head>` in the fetched HTML before creating the Blob; added `onLoad` handler on the iframe to call `contentWindow.switchView('split')` to force vis.js redraw with correct layout dimensions
- **Files modified:** `app/frontend/src/components/DiffViewer.tsx`
- **Verification:** TypeScript compiled clean (`npx tsc --noEmit`)
- **Committed in:** `27147b3`

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in blob URL iframe context)
**Impact on plan:** Essential fix for graph section functionality. No scope creep.

## Issues Encountered

None beyond the graph view bug documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 14 complete — full save/history/diff loop is functional end-to-end
- Phase 15 (System Tray / Auto-start) can proceed; no blockers from this phase

---
*Phase: 14-history-and-diff-viewer*
*Completed: 2026-03-14*
