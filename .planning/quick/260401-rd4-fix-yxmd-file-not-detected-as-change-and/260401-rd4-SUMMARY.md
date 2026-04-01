---
phase: 260401-rd4
plan: 01
subsystem: git-ops, remote-push, frontend
tags: [bug-fix, file-detection, push-guard, tdd]
dependency_graph:
  requires: []
  provides: [double-extension-workflow-detection, no-commits-push-guard]
  affects: [app/services/git_ops.py, app/routers/remote.py, app/frontend/src/components/HistoryPanel.tsx]
tech_stack:
  added: []
  patterns: [Path.suffixes all-suffix scan, pre-flight commit guard before subprocess push]
key_files:
  created: []
  modified:
    - app/services/git_ops.py
    - app/routers/remote.py
    - app/frontend/src/components/HistoryPanel.tsx
    - tests/test_watch.py
    - tests/test_remote.py
decisions:
  - Path.suffixes (all suffixes) replaces Path.suffix (last only) in git_changed_workflows — fixes double-extension detection without touching count_workflows or WORKFLOW_SUFFIXES
  - NoPushableCommitsError added after RepoNotFoundError in git_ops.py — consistent placement of custom git exception classes
  - git_has_commits() called at the top of git_push before any subprocess/file I/O — early exit with no side effects
  - Router catches NoPushableCommitsError before RepoNotFoundError — more specific first, then general
  - Existing RepoNotFoundError/CalledProcessError tests updated to mock git_has_commits=True — pre-flight guard intercepted them; mock is the correct fix
metrics:
  duration_minutes: 8
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_changed: 5
---

# Phase 260401-rd4 Plan 01: Fix yxmd double-extension detection and no-commits push guard

**One-liner:** Fixed double-extension Alteryx file detection via `Path.suffixes` scan, and added `NoPushableCommitsError` pre-flight guard in `git_push` with clear frontend message.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix double-extension suffix matching in git_changed_workflows | 1964c6d | app/services/git_ops.py, tests/test_watch.py |
| 2 | Guard git_push against no-commits repo and surface clear error | 4df3245 | app/services/git_ops.py, app/routers/remote.py, app/frontend/src/components/HistoryPanel.tsx, tests/test_remote.py |

## What Was Built

**Bug 1 — Double-extension file detection:**

`Path("test.yxmd.rtf").suffix` returns `".rtf"` which is not in `WORKFLOW_SUFFIXES`. The fix changes both places in `git_changed_workflows` to use `any(s in WORKFLOW_SUFFIXES for s in Path(filename).suffixes)` which checks all suffixes in the chain. A file like `test.yxmd.rtf` now correctly appears in the changed workflows list.

The fix applies to:
- The non-git branch (iterdir loop) — files awaiting first save
- The git status --porcelain parsing branch — modified/untracked files in a repo

`count_workflows` was intentionally left unchanged (uses `f.suffix`) because it scans all files recursively for badge counts and Alteryx does not actually track double-extension files.

**Bug 2 — Push on empty repo:**

`git push` on a repo with no commits exits with `"error: src refspec main does not match any"` — previously hitting the generic `CalledProcessError` path and showing "Check your connection" in the UI.

The fix adds:
1. `NoPushableCommitsError` exception class in `git_ops.py`
2. A pre-flight `git_has_commits()` check at the top of `git_push` — raises `NoPushableCommitsError` before any subprocess/file I/O
3. A `except git_ops.NoPushableCommitsError` handler in the push router returning `{"success": False, "error": "no_commits"}`
4. Frontend `HistoryPanel.tsx` now shows "Save your workflow first before pushing to GitHub/GitLab." when `reason.message === 'no_commits'`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated three existing RepoNotFoundError/CalledProcessError tests**
- **Found during:** Task 2 — full test suite run after GREEN
- **Issue:** `test_git_push_raises_repo_not_found_on_github_message`, `..._on_gitlab_message`, and `test_git_push_raises_called_process_error_for_other_failures` all patch `subprocess.run` directly. The new `git_has_commits()` pre-flight check calls `subprocess.run` and the mock returned `returncode=128` for all calls, causing it to raise `NoPushableCommitsError` instead of reaching the push.
- **Fix:** Added `patch("app.services.git_ops.git_has_commits", return_value=True)` to each of the three tests so the pre-flight passes and the subprocess mock takes effect as intended.
- **Files modified:** tests/test_remote.py
- **Commit:** 4df3245

## Test Results

- `tests/test_watch.py`: 13 passed (includes new `test_git_changed_workflows_double_extension`)
- `tests/test_remote.py`: 42 passed (includes new `test_git_push_raises_no_commits_error` and `test_push_endpoint_no_commits`)
- Full suite: 252 passed, 1 xfailed, 0 failures

## Known Stubs

None — all functionality is fully wired.

## Self-Check: PASSED

- `app/services/git_ops.py` — modified, exists
- `app/routers/remote.py` — modified, exists
- `app/frontend/src/components/HistoryPanel.tsx` — modified, exists
- `tests/test_watch.py` — modified, exists
- `tests/test_remote.py` — modified, exists
- Commit `1964c6d` exists in git log
- Commit `4df3245` exists in git log
