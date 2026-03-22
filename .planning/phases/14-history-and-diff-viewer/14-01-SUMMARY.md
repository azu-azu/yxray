---
phase: 14-history-and-diff-viewer
plan: 01
subsystem: api
tags: [fastapi, pytest, tdd, git, history]

# Dependency graph
requires:
  - phase: 13-save-version
    provides: module-level git_ops import pattern and mock.patch targeting convention
provides:
  - tests/test_history.py with 9 RED tests for HIST-01 and HIST-02 endpoints
  - app/routers/history.py stub router registered in server.py
affects: [14-02-backend-implementation]

# Tech tracking
tech-stack:
  added: []
  patterns: [stub router with NotImplementedError stubs, module-level import for mock.patch targeting, TDD RED-first scaffold]

key-files:
  created:
    - tests/test_history.py
    - app/routers/history.py
  modified:
    - app/server.py

key-decisions:
  - "history router uses module-level git_ops import (noqa: F401) so mock.patch targeting app.routers.history.git_ops works correctly"
  - "test_git_log_filters_non_workflow_files added as extra RED test beyond the 8 in plan — validates files_changed only contains workflow suffixes"

patterns-established:
  - "Stub router pattern: create router with NotImplementedError stubs before writing tests — ensures endpoints are reachable via TestClient during RED phase"
  - "Module-level import kept with noqa: F401 for mock.patch target — matches save.py convention from Phase 13"

requirements-completed: [HIST-01, HIST-02]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 14 Plan 01: History and Diff Viewer — Test Scaffold Summary

**9-test RED scaffold with stub history router registered in server.py — contracts defined before any implementation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T22:07:31Z
- **Completed:** 2026-03-14T22:09:42Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `app/routers/history.py` stub with `list_history` and `get_diff` endpoints raising NotImplementedError
- Registered history router in `app/server.py` so TestClient can reach `/api/history/*` paths
- Created `tests/test_history.py` with 9 RED tests (ImportError confirms functions not yet implemented)

## Task Commits

Each task was committed atomically:

1. **Task 1: Stub router + server.py registration** - `cd74ebd` (feat)
2. **Task 2: RED test suite** - `710b488` (test)

**Plan metadata:** (docs commit follows)

_Note: TDD plan — both commits establish RED state. Plan 02 drives tests GREEN._

## Files Created/Modified

- `app/routers/history.py` — Stub router with NotImplementedError for list_history (GET /{project_id}) and get_diff (GET /{sha}/diff); module-level git_ops import for mock.patch
- `app/server.py` — Added history router import and app.include_router(history.router) after save.router
- `tests/test_history.py` — 9 RED tests: 3 git_log unit tests, 2 git_show_file unit tests, 2 list_history endpoint tests, 2 diff endpoint tests

## Decisions Made

- Kept `from app.services import git_ops` with `# noqa: F401` in stub — ruff removes unused imports, but the import is required for `mock.patch("app.routers.history.git_ops.git_log")` to work (same pattern as save.py from Phase 13)
- Added `test_git_log_filters_non_workflow_files` as 9th test (plan specified 8) — this test verifies the filtering contract explicitly, which Plan 02 must implement correctly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added test_git_log_filters_non_workflow_files**
- **Found during:** Task 2 (test suite creation)
- **Issue:** Plan listed 8 tests but the git_log specification requires files_changed to contain only workflow suffixes — no test covered this filtering behavior
- **Fix:** Added test_git_log_filters_non_workflow_files to explicitly contract that behavior
- **Files modified:** tests/test_history.py
- **Verification:** Test collected (9 total) and fails RED with ImportError
- **Committed in:** 710b488 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (missing behavioral contract test)
**Impact on plan:** Adds one test that Plan 02 must satisfy. No scope creep — contracts filtering behavior the spec already required.

## Issues Encountered

- Ruff pre-commit hook removed the pipeline_run, DiffRequest, and HTMLRenderer imports from the stub as unused. These are re-added in Plan 02 when implementation uses them. The git_ops import was kept with `noqa: F401` since it's required for mock.patch targeting.
- Pre-existing flaky test `test_port_probe.py::test_find_available_port_returns_7433` fails when port 7433 is already in use — logged to deferred-items, unrelated to this plan.

## Next Phase Readiness

- Test contracts fully defined: Plan 02 has unambiguous targets
- Mock patch targets established: `app.routers.history.git_ops.git_log`, `app.routers.history.git_ops.git_show_file`, `app.routers.history.git_ops.git_has_commits`, `app.routers.history.pipeline_run`
- Router registered in server.py — endpoint tests will reach the routes once NotImplementedError stubs are replaced

---
*Phase: 14-history-and-diff-viewer*
*Completed: 2026-03-14*
