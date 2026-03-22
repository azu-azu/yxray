---
phase: 20-tech-debt-cleanup
plan: "02"
subsystem: ui
tags: [react, typescript, radix-ui, tabs, error-handling]

# Dependency graph
requires:
  - phase: 18.1-creation-of-pr
    provides: RemotePanel with Tabs and GitLab PR section using gitlab_repo_url
  - phase: 17-branch-management
    provides: mergeBaseSha state in AppShell passed to HistoryPanel for branch compare

provides:
  - addProjectError state + 400/409 error display in App.tsx (ONBOARD-02)
  - activeTab controlled state replacing document.querySelector in RemotePanel (REMOTE-02)
  - mergeBaseSha removed from HistoryPanelProps interface
  - gitlab_repo_url removed from RemoteStatus interface in RemotePanel

affects: [20-tech-debt-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - controlled-tabs: Use Radix Tabs value+onValueChange instead of defaultValue for programmatic tab switching
    - error-overlay: Fixed-position error bar in App root renders above both WelcomeScreen and AppShell

key-files:
  created: []
  modified:
    - app/frontend/src/App.tsx
    - app/frontend/src/components/RemotePanel.tsx
    - app/frontend/src/components/HistoryPanel.tsx
    - app/frontend/src/components/AppShell.tsx

key-decisions:
  - "addProjectError rendered as fixed overlay in App root — visible on both WelcomeScreen and AppShell views"
  - "activeTab controlled state drives Tabs value prop — removes fragile document.querySelector coupling to data-value attribute"
  - "mergeBaseSha useState stays in AppShell (still used by DiffViewer compareTo) — only the HistoryPanel interface prop and JSX call sites were removed"
  - "gitlab_repo_url removed from RemoteStatus — renderPushButton uses repo_url not gitlab_repo_url so removal is safe"

patterns-established:
  - "controlled-tabs: Replace defaultValue with value+onValueChange for programmatic switching"
  - "error-state-clear: setError(null) at top of async handler clears stale errors before each attempt"

requirements-completed: [ONBOARD-02, REMOTE-02]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 20 Plan 02: Frontend Tech Debt Fixes Summary

**Error feedback on add-project 400/409, controlled Radix Tabs replacing document.querySelector, and two dead interface props removed — TypeScript compiles clean**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-22T10:01:13Z
- **Completed:** 2026-03-22T10:03:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `addProjectError` state to App.tsx with 400/409 error messages surfaced as a fixed overlay (ONBOARD-02 — previously silently failed)
- Replaced `document.querySelector('[data-value="gitlab"]')` with `activeTab` controlled state in RemotePanel (REMOTE-02 — removes fragile DOM coupling)
- Removed dead `mergeBaseSha?: string | null` from HistoryPanelProps and both AppShell JSX call sites
- Removed dead `gitlab_repo_url: string | null` from RemoteStatus interface and fetchStatus() assignment

## Task Commits

Each task was committed atomically:

1. **Task 1: App.tsx add-project error feedback (ONBOARD-02)** - `38dfddf` (feat)
2. **Task 2: RemotePanel controlled tabs + dead interface removal (REMOTE-02)** - `69cf99a` (fix)

**Plan metadata:** (docs commit — see final)

## Files Created/Modified

- `app/frontend/src/App.tsx` - addProjectError state, 400/409 handling in doAddProject, fixed overlay render
- `app/frontend/src/components/RemotePanel.tsx` - activeTab state, Tabs value+onValueChange, no document.querySelector, gitlab_repo_url removed
- `app/frontend/src/components/HistoryPanel.tsx` - mergeBaseSha removed from HistoryPanelProps interface
- `app/frontend/src/components/AppShell.tsx` - mergeBaseSha={mergeBaseSha} JSX prop removed from both HistoryPanel call sites

## Decisions Made

- `addProjectError` rendered as fixed overlay at App root — ensures visibility regardless of which screen (WelcomeScreen or AppShell) is displayed when error fires
- `mergeBaseSha` useState itself stays in AppShell because DiffViewer still consumes it via `compareTo={mergeBaseSha}`
- Used HTML entity `&#x2715;` for dismiss button to avoid unicode build issues (consistent with Phase 16.1 pattern)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both audit requirements (ONBOARD-02, REMOTE-02) satisfied with clean TypeScript
- Phase 20 plan 03 can proceed if planned

## Self-Check: PASSED

All files found on disk. Both task commits verified in git log.

---
*Phase: 20-tech-debt-cleanup*
*Completed: 2026-03-22*
