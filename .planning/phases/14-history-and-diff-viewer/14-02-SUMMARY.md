---
phase: 14-history-and-diff-viewer
plan: "02"
subsystem: api
tags: [fastapi, git, subprocess, tempfile, pytest, tdd]

# Dependency graph
requires:
  - phase: 14-01-history-and-diff-viewer
    provides: history router stub, RED test suite in tests/test_history.py
  - phase: 13-save-version
    provides: git_ops.py module with WORKFLOW_SUFFIXES, git_has_commits, git_discard_files patterns
provides:
  - git_log(folder) — returns flat commit list newest-first with sha/message/author/timestamp/files_changed/has_parent
  - git_show_file(folder, sha, filepath) — returns bytes at commit or raises FileNotFoundError
  - GET /api/history/{project_id}?folder= — returns JSON commit list
  - GET /api/history/{sha}/diff?folder=&file= — returns HTML diff or {is_first_commit:true} JSON
affects: [14-03-history-and-diff-viewer, 15-system-tray]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Two-pass git log (headers then diff-tree per SHA) avoids fragile blank-line parsing
    - mkstemp for temp files — Windows-safe alternative to NamedTemporaryFile
    - Module-level git_ops import (noqa: F401) enables mock.patch targeting
    - compare_to query param allows arbitrary commit comparisons beyond direct parent

key-files:
  created: []
  modified:
    - app/services/git_ops.py
    - app/routers/history.py

key-decisions:
  - "Two-pass git log approach (headers pass + diff-tree per SHA) chosen over single-pass --name-only to avoid blank-line parsing fragility"
  - "mkstemp pattern used for temp files instead of NamedTemporaryFile — Windows file-locking compatibility"
  - "compare_to optional query param added to get_diff — allows arbitrary commit pair diffs, not just parent"
  - "list_history declared before get_diff in FastAPI router — route declaration order matters for /sha/diff path matching"

patterns-established:
  - "Two-pass git log: first subprocess for headers, second subprocess per SHA for changed files"
  - "_run_diff helper: write bytes to mkstemp files, run pipeline_run(DiffRequest), render HTML, unlink in finally"

requirements-completed: [HIST-01, HIST-02]

# Metrics
duration: 5min
completed: 2026-03-15
---

# Phase 14 Plan 02: History and Diff Viewer Backend Summary

**git_log() and git_show_file() in git_ops.py plus full /api/history router driving 9 tests GREEN via two-pass subprocess and mkstemp ACD pipeline pattern**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-15T00:26:23Z
- **Completed:** 2026-03-15T00:31:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- git_log(folder) implemented using two-pass subprocess approach — commit headers then diff-tree per SHA for workflow-only file lists
- git_show_file(folder, sha, filepath) implemented returning raw bytes or raising FileNotFoundError
- GET /api/history/{project_id} returns full commit list or [] based on git_has_commits
- GET /api/history/{sha}/diff returns {is_first_commit: true} JSON for first commit, full ACD HTMLResponse for all others
- All 9 tests in tests/test_history.py GREEN with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement git_log() and git_show_file() in git_ops.py** - `2230d3b` (feat)
2. **Task 2: Implement history.py router endpoints** - `744d793` (feat)

## Files Created/Modified

- `app/services/git_ops.py` - Added git_log() and git_show_file() functions
- `app/routers/history.py` - Full implementation of list_history and get_diff endpoints plus _run_diff helper

## Decisions Made

- Two-pass git log approach (headers then diff-tree per SHA) avoids fragile blank-line parsing from `--name-only` single-pass
- mkstemp pattern used for temp file creation — NamedTemporaryFile has file-locking issues on Windows
- `compare_to` optional query parameter added to get_diff to enable arbitrary commit comparisons
- list_history route declared before get_diff in FastAPI — declaration order affects path matching for `/{sha}/diff`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Ruff pre-commit hook auto-fixed a minor formatting issue on first commit attempt — re-staged and committed cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend complete for Phase 14: all history and diff API endpoints are live and tested
- Plan 14-03 (HistoryPanel frontend) can consume GET /api/history/{project_id} and GET /api/history/{sha}/diff directly
- HistoryPanel.tsx and badge.tsx stubs already created in commit 742c91d

---
*Phase: 14-history-and-diff-viewer*
*Completed: 2026-03-15*
