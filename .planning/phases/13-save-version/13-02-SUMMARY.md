---
phase: 13-save-version
plan: "02"
subsystem: backend
tags: [git-ops, fastapi, tdd, save, undo, discard]

# Dependency graph
requires:
  - phase: 13-save-version
    plan: "01"
    provides: Failing test stubs for all 12 SAVE-01/02/03 tests
  - phase: 12-file-watcher
    provides: git_has_commits, watcher_manager.clear_count
provides:
  - git_commit_files, git_undo_last_commit, git_discard_files in git_ops.py
  - POST /api/save/commit, /undo, /discard endpoints in app/routers/save.py
  - save router registered in server.py
affects:
  - 13-save-version (plans 03-04 can now call save endpoints from frontend)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "git_discard_files: backup-before-remove safety pattern using shutil.copy2 to .acd-backup/"
    - "_is_tracked: git ls-files --error-unmatch used as tracked/untracked guard"
    - "router uses module-level import of git_ops (not function-level) for correct mock.patch targeting"

key-files:
  created:
    - app/routers/save.py
  modified:
    - app/services/git_ops.py
    - app/server.py
    - tests/test_save.py

key-decisions:
  - "git_discard_files copies BEFORE removing — backup-first safety guarantee for v1"
  - "git_undo_last_commit uses --soft (not --hard) — file content preserved in working tree"
  - "save router uses from app.services import git_ops (module import) so unittest.mock.patch targets work correctly — consistent with Phase 11-02 decision"

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 13 Plan 02: Save Version Backend Implementation Summary

**git_commit_files/undo/discard in git_ops.py + POST /api/save/commit|undo|discard endpoints; all 12 SAVE tests GREEN**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T20:52:45Z
- **Completed:** 2026-03-14T20:55:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `git_commit_files`: stages only explicitly selected files, raises `ValueError` on empty list
- Implemented `git_undo_last_commit`: soft-reset preserves file content in working tree
- Implemented `git_discard_files` + `_is_tracked`: backup-first safety, handles both tracked and untracked files
- Created `app/routers/save.py` with 3 endpoints following exact router pattern from projects.py
- Registered save router in `app/server.py`
- All 12 `tests/test_save.py` tests GREEN; full test suite (146 passed, 1 xfailed) with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend git_ops.py with commit, undo, discard functions** - `cb64c43` (feat)
2. **Task 2: Create app/routers/save.py and register in server.py** - `fdbad9a` (feat)

## Files Created/Modified

- `app/services/git_ops.py` - Added `git_commit_files`, `git_undo_last_commit`, `_is_tracked`, `git_discard_files`; added `shutil` and `pathlib.Path` imports
- `app/routers/save.py` - New file: `CommitBody`, `UndoBody`, `DiscardBody` models; POST /commit, /undo, /discard endpoints
- `app/server.py` - Added save to router import line; added `app.include_router(save.router)`
- `tests/test_save.py` - Replaced all 12 pytest stubs with real assertions (8 git_ops unit tests + 4 endpoint tests using mock.patch)

## Decisions Made

- `git_discard_files` copies to `.acd-backup/` BEFORE removing — guarantees backup-first safety; flat structure (basename only) is acceptable for v1
- `git_undo_last_commit` uses `--soft` not `--hard` — file content is preserved in working tree, commit is removed
- Save router imports `git_ops` as module (`from app.services import git_ops`) so `unittest.mock.patch("app.routers.save.git_ops.git_commit_files")` targets work correctly — same pattern as Phase 11-02

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 line-length in docstring (save.py)**
- **Found during:** Task 2 (pre-commit hook on commit attempt)
- **Issue:** `undo_last_version` docstring exceeded 88 character limit
- **Fix:** Split docstring across two lines
- **Files modified:** `app/routers/save.py`
- **Committed in:** `fdbad9a` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - formatting)
**Impact on plan:** Trivial fix; no scope change.

## Issues Encountered

- Pre-commit ruff E501 on `save.py` docstring required a second commit attempt on Task 2 — fixed inline.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 03 (ChangesPanel UI) can now call all three save endpoints from the frontend
- `has_any_commits` response from `/undo` allows frontend to toggle undo button state
- `.acd-backup/` pattern established for v1 — backup folder created on first discard

---
*Phase: 13-save-version*
*Completed: 2026-03-14*

## Self-Check: PASSED

- git_ops.py: FOUND
- save.py: FOUND
- server.py: FOUND
- test_save.py: FOUND
- 13-02-SUMMARY.md: FOUND
- commit cb64c43: FOUND
- commit fdbad9a: FOUND
