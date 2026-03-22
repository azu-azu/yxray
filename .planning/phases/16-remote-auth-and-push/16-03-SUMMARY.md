---
phase: 16-remote-auth-and-push
plan: "03"
subsystem: backend
tags: [git-ops, remote-auth, push, config-store, fastapi]
dependency_graph:
  requires: [16-01, 16-02]
  provides: [git_push, git_fetch, git_ahead_behind, remote_router_full, config_store_remote_helpers]
  affects: [app/services/git_ops.py, app/routers/remote.py, app/services/config_store.py, app.spec]
tech_stack:
  added: []
  patterns:
    - GIT_ASKPASS temp-script pattern for credential injection (same in git_fetch as git_push)
    - config_store remote_repos dict keyed by project_id and provider
    - contextlib.suppress for non-critical subprocess errors in status endpoint
key_files:
  created: []
  modified:
    - app/services/git_ops.py
    - app/routers/remote.py
    - app/services/config_store.py
    - app.spec
    - tests/test_remote.py
decisions:
  - "[16-03] git_fetch uses identical GIT_ASKPASS temp-script pattern as git_push — ignores non-zero returncode (unreachable remote is not an error)"
  - "[16-03] POST /github/connect stores PAT without API validation — user is trusted; consistent with device-flow path that also stores unvalidated token"
  - "[16-03] GET /status calls git_fetch before git_ahead_behind when token + repo_url available; silently degrades to (0,0) on fetch error"
  - "[16-03] config_store remote_repos stored as dict keyed by project_id then provider_url — not in keyring (as per plan must_haves)"
  - "[16-03] test_post_push_success updated to mock config_store.get_remote_repo — new push flow requires stored URL to skip auto-create path"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 5
---

# Phase 16 Plan 03: Git Push Operations and Full Remote Router Summary

**One-liner:** Full remote push backend — git_fetch/push/ahead_behind in git_ops, all /api/remote/* endpoints, config_store remote URL persistence, keyring hiddenimports in app.spec.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing tests for git_fetch, github/connect, gitlab/status, config_store, repo_url | cf5e1b3 | tests/test_remote.py |
| 1 GREEN | Add git_fetch to git_ops.py | ca97f7a | app/services/git_ops.py |
| 2 GREEN | Full remote router + config_store helpers + app.spec keyring imports | b460919 | app/routers/remote.py, app/services/config_store.py, app.spec, tests/test_remote.py |

## What Was Built

### git_ops.py additions
- `git_fetch(folder, remote_url, token)` — GIT_ASKPASS temp-script pattern; non-zero returncode silently ignored (unreachable remote)

### app/routers/remote.py (full implementation)
- `POST /api/remote/github/start` — device flow start (existed, kept)
- `GET /api/remote/github/status` — token check (existed, kept)
- `POST /api/remote/github/connect` — **NEW** GitHub PAT fallback; stores token directly via `store_github_token()`
- `POST /api/remote/gitlab/connect` — validate + store GitLab PAT (existed, kept)
- `GET /api/remote/gitlab/status` — **NEW** GitLab token check
- `POST /api/remote/push` — **UPDATED** uses `config_store.get_remote_repo()` for URL; auto-creates repo if no URL stored; calls `git_push` with GIT_ASKPASS
- `GET /api/remote/status` — **UPDATED** includes `repo_url` from config_store; calls `git_fetch` + `git_ahead_behind` when token+URL available

### app/services/config_store.py additions
- `get_remote_repo(project_id)` — returns `{}` or `{"github_url": "...", "gitlab_url": "..."}`
- `set_remote_repo(project_id, provider, url)` — persists under `cfg["remote_repos"][project_id]["{provider}_url"]`

### app.spec
- Added `keyring`, `keyring.backends`, `keyring.backends.Windows`, `keyring.backends.macOS`, `keyring.credentials`, `httpx` to hiddenimports

## Test Results

- `tests/test_remote.py`: 29 passed (8 new tests added in this plan)
- Full suite (excluding pre-existing test_port_probe failure): 199 passed, 1 xfailed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_post_push_success mock insufficient for new push implementation**
- **Found during:** Task 2 GREEN
- **Issue:** Existing test only mocked `git_ops.git_push` and `get_github_token`; new push route calls `config_store.get_remote_repo()` which returned `{}`, triggering auto-create repo path that made a real HTTP call
- **Fix:** Added `config_store.get_remote_repo` mock returning a pre-existing repo URL in test
- **Files modified:** tests/test_remote.py
- **Commit:** b460919

**2. [Rule 1 - Bug] ruff SIM105 lint error — bare except/pass pattern**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Two `try/except Exception: pass` blocks triggered SIM105; ruff also auto-formatted import grouping
- **Fix:** Replaced with `contextlib.suppress(Exception)` blocks; added `import contextlib`
- **Files modified:** app/routers/remote.py
- **Commit:** b460919

## Self-Check: PASSED

All files confirmed present, all commits confirmed in git log:
- app/services/git_ops.py — FOUND (contains git_fetch)
- app/routers/remote.py — FOUND (contains POST /github/connect)
- app/services/config_store.py — FOUND (contains get_remote_repo)
- app.spec — FOUND (contains keyring.backends.Windows)
- cf5e1b3 — FOUND (RED tests commit)
- ca97f7a — FOUND (git_fetch implementation)
- b460919 — FOUND (full remote router + config_store + app.spec)
