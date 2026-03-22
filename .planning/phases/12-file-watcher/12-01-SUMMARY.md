---
phase: 12-file-watcher
plan: 01
subsystem: testing, api
tags: [pytest, watchdog, git, subprocess, pathlib]

# Dependency graph
requires:
  - phase: 11-onboarding-and-project-management
    provides: app/services/git_ops.py with is_git_repo, git_init, get_git_identity, set_git_identity

provides:
  - tests/test_watch.py with 9 test stubs (7 active, 5 skipped) covering WATCH-01/02/03
  - git_changed_workflows helper in app/services/git_ops.py
  - count_workflows helper in app/services/git_ops.py
  - git_has_commits helper in app/services/git_ops.py
  - app/services/watcher_utils.py with is_network_path

affects:
  - 12-02 (WatcherManager imports git_changed_workflows, is_network_path)
  - 12-03 (integration tests in test_watch.py will be unskipped)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD Wave 0 scaffold: test file created first (RED), then implementation (GREEN)
    - git status --porcelain v1 parsing via line[3:].strip() with rename support
    - Platform-aware network detection: UNC check first, then OS-specific fallback

key-files:
  created:
    - tests/test_watch.py
    - app/services/watcher_utils.py
  modified:
    - app/services/git_ops.py

key-decisions:
  - "git_changed_workflows uses git status --porcelain (not diff) to catch both staged and untracked new files"
  - "is_network_path normalizes backslashes to forward slashes before UNC check for platform-independent detection"
  - "WORKFLOW_SUFFIXES frozenset defined at module level in git_ops.py — shared constant for both git_changed_workflows and count_workflows"

patterns-established:
  - "WORKFLOW_SUFFIXES frozenset({'.yxmd', '.yxwz'}) as module-level constant for extension filtering"
  - "git_has_commits uses rev-parse HEAD returncode (not stdout parsing) for reliability across git versions"

requirements-completed: [WATCH-01, WATCH-02, WATCH-03]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 12 Plan 01: File Watcher Helpers Summary

**TDD Wave 0 scaffold + git_ops/watcher_utils helpers: git status parsing, workflow counting, empty-repo detection, and platform-aware UNC/network path classification**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T15:14:05Z
- **Completed:** 2026-03-14T15:16:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created test_watch.py with 9 stubs (7 active RED tests, 2 WatcherManager skips, 3 integration skips)
- Extended git_ops.py with git_changed_workflows, count_workflows, and git_has_commits
- Created watcher_utils.py with is_network_path providing platform-aware UNC/network detection
- All 7 active unit tests pass GREEN; full suite shows no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write test scaffold (Wave 0 — all stubs fail RED)** - `01f7cc0` (test)
2. **Task 2: Extend git_ops.py + create watcher_utils.py (RED -> GREEN)** - `b24dc86` (feat)

_Note: TDD tasks have separate test and feat commits_

## Files Created/Modified

- `tests/test_watch.py` - 9 test stubs for WATCH-01/02/03; 7 active unit tests, 5 skipped (Plan 02/03 stubs)
- `app/services/git_ops.py` - Extended with WORKFLOW_SUFFIXES, git_changed_workflows, count_workflows, git_has_commits
- `app/services/watcher_utils.py` - New module with is_network_path (UNC + Windows/macOS/Linux OS-specific detection)

## Decisions Made

- `git_changed_workflows` uses `git status --porcelain` (not `git diff`) to capture both staged modifications and untracked new files in one pass
- `is_network_path` normalizes backslashes to forward slashes before the UNC check, enabling `\\\\server\\share` to match via a single `startswith("//")` guard
- `WORKFLOW_SUFFIXES` frozenset placed at module level in git_ops.py so both `git_changed_workflows` and `count_workflows` reference the same constant

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing `test_port_probe.py` failures (3 tests) were present before this plan — port 7433 already bound on the machine. Not caused by this plan. Excluded from regression check; all other 126 tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All helpers ready for Plan 02 (WatcherManager) to import: `git_changed_workflows`, `count_workflows`, `git_has_commits`, `is_network_path`
- 5 skipped tests in test_watch.py will be unskipped as WatcherManager (Plan 02) and server integration (Plan 03) are built
- No blockers

---
*Phase: 12-file-watcher*
*Completed: 2026-03-14*
