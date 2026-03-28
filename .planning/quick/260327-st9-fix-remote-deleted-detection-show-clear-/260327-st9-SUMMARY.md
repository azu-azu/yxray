---
phase: 260327-st9
plan: 01
subsystem: remote-push
tags: [bug-fix, git-ops, config-store, remote-panel, tdd]
dependency_graph:
  requires: []
  provides: [RepoNotFoundError, clear_remote_repo, repo_deleted-error-code]
  affects: [app/services/git_ops.py, app/services/config_store.py, app/routers/remote.py, app/frontend/src/components/RemotePanel.tsx]
tech_stack:
  added: []
  patterns: [typed-exception-hierarchy, router-catch-and-clear, frontend-error-kind-union]
key_files:
  created: []
  modified:
    - app/services/git_ops.py
    - app/services/config_store.py
    - app/routers/remote.py
    - app/frontend/src/components/RemotePanel.tsx
    - tests/test_remote.py
decisions:
  - RepoNotFoundError inherits from Exception (not CalledProcessError) — clean separation allows router to catch it without suppressing real process errors
  - clear_remote_repo sets key to None (not deletes) to preserve dict structure; get_remote_repo callers already handle None values
  - repo_deleted error string (not message text) passed over API boundary — frontend does exact string match, no substring fragility
metrics:
  duration: ~8 min
  completed: 2026-03-27
  tasks_completed: 2
  files_modified: 5
---

# Phase 260327-st9: Fix Remote-Deleted Detection — Show Clear Message + Clear URL

One-liner: Three-layer fix — git_ops detects "repository not found" stderr and raises typed `RepoNotFoundError`, router catches it and clears the stale URL from config, frontend shows "Repository was deleted. A new one will be created on your next push." with a Retry button.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RepoNotFoundError + clear_remote_repo | 800c3f1 | git_ops.py, config_store.py, test_remote.py |
| 2 | Router catch + frontend error display | 1149f45 | remote.py, RemotePanel.tsx, test_remote.py |

## What Was Built

**app/services/git_ops.py**
- `class RepoNotFoundError(Exception)` defined before `is_git_repo`
- `git_push()` checks `result.stderr` for `"repository not found"` (case-insensitive) before raising `CalledProcessError` — covers both GitHub ("remote: Repository not found.") and GitLab ("remote: ERROR: Repository not found.")

**app/services/config_store.py**
- `clear_remote_repo(project_id, provider)` — sets `{provider}_url` key to `None` and saves; no-op when project_id not in config

**app/routers/remote.py**
- New `except git_ops.RepoNotFoundError` handler before `CalledProcessError` — calls `clear_remote_repo` then returns `{"success": False, "error": "repo_deleted"}`

**app/frontend/src/components/RemotePanel.tsx**
- `PushErrorKind` union extended with `'repo_deleted'`
- Error detection block: `repo_deleted` branch checked before `auth_expired` and `generic`
- JSX render: `repo_deleted` shows "Repository was deleted. A new one will be created on your next push." with a Retry button that calls `handlePush(provider)`

**tests/test_remote.py**
- 6 new TDD tests: 3 for git_ops error paths, 2 for config_store helper, 1 for router endpoint

## Verification

- 249 backend tests pass (0 failures, 1 xfail as expected)
- TypeScript/Vite build clean — no type errors from new `PushErrorKind` variant
- End-to-end flow verified: deleted repo -> RepoNotFoundError raised -> URL cleared -> `repo_deleted` returned -> clear UI message shown

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `800c3f1` exists in git log
- `1149f45` exists in git log
- All 5 modified files present and contain expected symbols
