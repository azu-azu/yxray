---
phase: 17-branch-management
plan: "01"
subsystem: backend-api
tags: [tdd, branch-management, red-tests, stub-router]
dependency_graph:
  requires: []
  provides:
    - tests/test_branch.py (RED test suite for BRANCH-01/02/03)
    - app/routers/branch.py (stub router with 5 endpoints)
  affects:
    - app/server.py (branch.router registered)
tech_stack:
  added: []
  patterns:
    - TDD RED: graceful _require_branch() pattern from test_remote.py
    - Stub router: NotImplementedError endpoints for GREEN phase targeting
    - module-level import: git_ops + subprocess for mock.patch targeting
key_files:
  created:
    - tests/test_branch.py
    - app/routers/branch.py
  modified:
    - app/server.py
decisions:
  - "branch.router registered after remote.router in server.py — consistent with incremental router registration pattern"
  - "All branch name inputs in request body or query params — never in path segments (experiment/ contains / breaking URL path)"
  - "Module-level subprocess import in branch.py — enables mock.patch('app.routers.branch.subprocess.run') for merge-base tests"
  - "test_list_history_with_branch passes in RED state — history endpoint already accepts extra query params; this is correct behavior"
metrics:
  duration_seconds: 147
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 17 Plan 01: Branch Management RED Test Scaffold Summary

**One-liner:** RED test suite and stub router for branch list/create/checkout/delete/merge-base with NotImplementedError stubs.

## What Was Built

TDD Wave 0 for Phase 17 branch management. Created `tests/test_branch.py` with 11 tests covering all BRANCH-01/02/03 requirements, all failing with `NotImplementedError` as required for RED discipline. Created `app/routers/branch.py` with 5 stub endpoints and registered `branch.router` in `app/server.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write RED tests for all BRANCH requirements | c01c406 | tests/test_branch.py |
| 2 | Create branch.py stub router + register in server.py | 17f412b | app/routers/branch.py, app/server.py |

## Verification Results

- `python -m pytest tests/ --collect-only -q` → 218 tests collected, 0 errors
- `python -m pytest tests/test_branch.py -q` → 10 failed (NotImplementedError), 1 passed — RED confirmed
- `python -m pytest tests/ -x -q --ignore=tests/test_branch.py` → 130 passed (pre-existing test_port_probe failure is environment-specific, documented in STATE.md)

## Decisions Made

1. Branch name inputs (containing `/`) go in request body or query params — never path segments (prevents URL routing breakage with `experiment/2026-...` style names)
2. Module-level `import subprocess` in `branch.py` enables `mock.patch("app.routers.branch.subprocess.run")` for merge-base tests
3. `test_list_history_with_branch` passes in RED state — the history endpoint already accepts extra query params gracefully; this is correct, not a test error

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- tests/test_branch.py: EXISTS
- app/routers/branch.py: EXISTS
- app/server.py: contains `branch` import and `app.include_router(branch.router)`: VERIFIED
- Commit c01c406: EXISTS
- Commit 17f412b: EXISTS
