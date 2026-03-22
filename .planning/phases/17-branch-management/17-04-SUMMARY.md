---
phase: 17-branch-management
plan: "04"
subsystem: ui
tags: [react, svg, graphview, branch-management, diff-viewer, compare-toggle]

# Dependency graph
requires:
  - phase: 17-03
    provides: Branch chip + popover in ChangesPanel, activeBranch Zustand state, AppShell fetchBranch, history branch param
  - phase: 17-02
    provides: Backend branch API (list, create, checkout, delete, merge-base endpoint)
  - phase: 16.1
    provides: GraphView single-column SVG, HistoryPanel with list/graph views
provides:
  - "DiffViewer compare toggle [vs previous save] [vs main] shown when on experiment branch with merge-base"
  - "compareTo prop on DiffViewer — passes merge-base SHA as compare_to query param to diff endpoint"
  - "mergeBaseSha state in AppShell — fetched from /api/branch/{id}/merge-base when on experiment/ branch"
  - "allBranchEntries state in AppShell — all-branch git log for multi-branch GraphView"
  - "GraphView two-column SVG: main commits in left (gray/blue), experiment commits in right (amber)"
  - "Branch connector line in amber from branch-point main node to first experiment node"
  - "Single-branch GraphView path unchanged (Phase 16.1 regression-free)"
affects:
  - phase-18-ci-polish

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compare toggle state machine: compareMode ('previous' | 'main') drives fetch URL with optional compare_to param"
    - "Multi-branch GraphView: allBranchEntries as combined timeline index; experimentShas Set for O(1) column assignment"
    - "Branch connector heuristic: last main entry (bottommost) to last experiment entry (oldest on branch)"
    - "allBranchEntries fetch: conditional on currentBranch.startsWith('experiment/') in fetchHistory to avoid extra API call on main"

key-files:
  created: []
  modified:
    - app/frontend/src/components/DiffViewer.tsx
    - app/frontend/src/components/HistoryPanel.tsx
    - app/frontend/src/components/AppShell.tsx

key-decisions:
  - "mergeBaseSha fetched in fetchBranch (not fetchHistory) — it's a branch property, not history property; stays current after branch switch"
  - "allBranchEntries fetched in fetchHistory since it's history data and needs to refresh alongside filtered branch history"
  - "Multi-branch GraphView uses allBranchEntries as row index (Map<sha, rowIdx>) — entries from both branches share the same vertical timeline"
  - "Branch connector uses last main entry as branch point — simpler than parent-SHA matching; correct for typical experiment branch topology"
  - "compareMode reset NOT added on sha change — user may want to compare different commits in the same branch in the same mode"

patterns-established:
  - "Compare toggle pattern: isExperimentBranch + compareTo controls toggle visibility; compareMode state drives URL params"
  - "Dual-fetch pattern: fetchHistory on experiment branch makes two requests (branch-filtered + all-branch); on main makes one"

requirements-completed:
  - BRANCH-01
  - BRANCH-02
  - BRANCH-03

# Metrics
duration: 5min
completed: "2026-03-15"
---

# Phase 17 Plan 04: Branch-Aware History, Compare Toggle, and Multi-Branch GraphView Summary

**Branch-aware HistoryPanel with re-fetch on switch, DiffViewer compare toggle (vs previous save / vs main) for experiment branches, and two-column SVG GraphView with amber experiment nodes and branch connector line**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T18:18:00Z
- **Completed:** 2026-03-15T18:23:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `compareTo` / `isExperimentBranch` props to DiffViewer with toggle UI using existing Tailwind classes; compareMode drives `compare_to` query param to the diff endpoint
- Wired AppShell to fetch merge-base SHA (via existing `/api/branch/{id}/merge-base`) when switching to experiment branches and pass it to DiffViewer
- Extended GraphView to render a two-column SVG for experiment branches: main commits on left (gray/blue, unchanged), experiment commits on right (amber #f59e0b), branch connector line between branch point and oldest experiment commit

## Task Commits

Each task was committed atomically:

1. **Task 1: DiffViewer compare toggle + AppShell merge-base wiring** - `9d247d7` (feat)
2. **Task 2: GraphView multi-branch SVG rendering** - `aec914c` (feat)

## Files Created/Modified

- `app/frontend/src/components/DiffViewer.tsx` - Added `compareTo`, `isExperimentBranch` props; `compareMode` state; compare toggle UI in header; `compareMode`/`compareTo` added to useEffect deps
- `app/frontend/src/components/HistoryPanel.tsx` - Added `activeBranch`, `mergeBaseSha`, `allBranchEntries` to `HistoryPanelProps`; extended `GraphViewProps` with same; full multi-branch SVG rendering path in GraphView while preserving single-branch path
- `app/frontend/src/components/AppShell.tsx` - Added `mergeBaseSha` + `allBranchEntries` state; `fetchBranch` fetches merge-base for experiment branches; `fetchHistory` conditionally fetches all-branch entries; both reset on project change; all HistoryPanel + DiffViewer render sites pass new props

## Decisions Made

- `mergeBaseSha` is fetched in `fetchBranch` rather than `fetchHistory` — it's a branch property (not per-history-entry) and should refresh immediately on branch switch, which `fetchBranch` handles.
- `allBranchEntries` is fetched in `fetchHistory` because it's history data and needs to stay in sync with the filtered branch history on each re-fetch.
- The multi-branch GraphView uses `allBranchEntries` as the row index (a `Map<sha, rowIndex>`) so both main and experiment commits share the same vertical timeline — this gives a natural visual representation of time order across both columns.
- Branch connector heuristic: the last entry in `mainEntries` (oldest main commit = bottommost row) is used as the branch point, connecting to the last entry in `entries` (oldest experiment commit). This is correct for the typical experiment-branch topology (branched from a recent main commit).
- The `merge-base` endpoint in `branch.py` was already implemented in Plan 02 — no changes needed.

## Deviations from Plan

None - plan executed exactly as written. The merge-base endpoint was already present in branch.py from Plan 02 as documented in the plan context.

## Issues Encountered

- Pre-existing `test_port_probe::test_find_available_port_returns_7433` failure (port 7433 occupied on dev machine) — not a Phase 17-04 regression; documented in STATE.md from Phase 15. All 214 other backend tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 17 branch management is now fully complete across all 4 plans (BRANCH-01, BRANCH-02, BRANCH-03 delivered)
- Branch feature end-to-end: branch chip UI → create/switch/delete → branch-filtered history → compare toggle → multi-branch graph
- Visual verification recommended: on experiment branch, open HistoryPanel graph view (two columns expected), click a commit (compare toggle should appear in DiffViewer header)

## Self-Check: PASSED
