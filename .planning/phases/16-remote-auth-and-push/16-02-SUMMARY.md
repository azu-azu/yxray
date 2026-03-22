---
phase: 16-remote-auth-and-push
plan: "02"
subsystem: auth
tags: [github, gitlab, keyring, device-flow, httpx, git-push, askpass, rest-api]

requires:
  - phase: 16-remote-auth-and-push
    provides: RED test scaffold (21 failing tests) + service stubs for REMOTE-01 through REMOTE-06

provides:
  - GitHub Device Flow implementation (request_device_code, poll_and_store with time.sleep)
  - OS keyring credential storage for GitHub and GitLab tokens (SERVICE_GITHUB, SERVICE_GITLAB)
  - GitLab PAT validation and storage (validate_gitlab_token, validate_and_store_gitlab_token)
  - PyInstaller keyring backend fix (_ensure_backend called at import time)
  - github_api.py: create_github_repo, get_github_username, github_repo_exists, find_available_repo_name, slugify_folder_name
  - gitlab_api.py: validate_gitlab_token, create_gitlab_project
  - git_ops.git_push via GIT_ASKPASS credential injection (token never in URL or config)
  - git_ops.git_ahead_behind via rev-list --count (ahead and behind counts vs. upstream)
  - Full /api/remote/* router endpoints: github/start, github/status, gitlab/connect, push, status
  - All 21 REMOTE-01 through REMOTE-06 tests GREEN

affects:
  - 16-03 (frontend RemotePanel — connects to these router endpoints)

tech-stack:
  added: []
  patterns:
    - "httpx module-level import pattern — import httpx at top level so patch('module.httpx') works in tests"
    - "GIT_ASKPASS credential injection — write temp script echoing token, set GIT_ASKPASS env var, never embed token in URL or git config"
    - "keyring module-level import with _ensure_backend() PyInstaller fix — call at import time to set correct backend"
    - "poll_and_store is synchronous (time.sleep) — test mocks patch app.services.remote_auth.time; not asyncio"

key-files:
  created: []
  modified:
    - app/services/remote_auth.py
    - app/services/github_api.py
    - app/services/gitlab_api.py
    - app/services/git_ops.py
    - app/routers/remote.py
    - app/server.py
    - tests/test_remote.py

key-decisions:
  - "poll_and_store implemented as synchronous function using time.sleep — tests patch app.services.remote_auth.time (not asyncio); the router github/start endpoint returns immediately without waiting for poll completion"
  - "gitlab_api.py includes validate_gitlab_token (same as remote_auth.py) — keeps all GitLab REST calls in one module; remote_auth.py also validates for the router's validate_gitlab_token patch target"
  - "remote.router registered in server.py — required so TestClient in test_remote.py can reach /api/remote/* endpoints (was missing, caused 405)"
  - "test_git_ahead_behind mock fixed: changed 'HEAD' in args (list membership) to any('HEAD' in a for a in args) — '..HEAD' range args are single strings, standalone HEAD check was a bug in the RED scaffold"

patterns-established:
  - "GIT_ASKPASS pattern: write temp .sh/.bat file echoing token, chmod 700, set env GIT_ASKPASS + GIT_TERMINAL_PROMPT=0; cleanup with contextlib.suppress(OSError)"
  - "git rev-list --count {upstream}..HEAD for ahead; HEAD..{upstream} for behind — both single-arg range strings"

requirements-completed:
  - REMOTE-01
  - REMOTE-02
  - REMOTE-03

duration: 15min
completed: 2026-03-15
---

# Phase 16 Plan 02: Remote Auth Service Implementations Summary

**GitHub Device Flow + keyring credential storage + GitHub/GitLab REST API clients + git_push via GIT_ASKPASS, turning all 21 REMOTE-01 through REMOTE-06 tests GREEN**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-15T05:33:00Z
- **Completed:** 2026-03-15T05:39:52Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Implemented all 3 service modules (remote_auth.py, github_api.py, gitlab_api.py) replacing NotImplementedError stubs with full httpx-based implementations
- Implemented git_push using GIT_ASKPASS credential injection (token never in URL or subprocess args) and git_ahead_behind using rev-list --count
- Implemented full /api/remote/* router (github/start, github/status, gitlab/connect, push, status) and registered it in server.py
- All 21 test_remote.py tests GREEN; no new regressions in full suite

## Task Commits

1. **Task 1: Implement remote_auth.py** - `962054a` (feat)
2. **Task 2: Implement github_api.py, gitlab_api.py, router, git_push/ahead_behind** - `8f0d59c` (feat)

## Files Created/Modified

- `app/services/remote_auth.py` — Full implementation: _ensure_backend(), request_device_code(), poll_and_store(), store/get github/gitlab tokens via keyring, validate_gitlab_token(), validate_and_store_gitlab_token()
- `app/services/github_api.py` — Full implementation: create_github_repo (private=True), get_github_username, github_repo_exists, find_available_repo_name (-2/-3 suffix), slugify_folder_name
- `app/services/gitlab_api.py` — Full implementation: validate_gitlab_token (GET /api/v4/user), create_gitlab_project (visibility=private)
- `app/services/git_ops.py` — git_push (GIT_ASKPASS), git_ahead_behind (rev-list --count); added contextlib, os, sys, tempfile imports
- `app/routers/remote.py` — Full endpoint implementations replacing stub
- `app/server.py` — Added remote router import and app.include_router(remote.router)
- `tests/test_remote.py` — Fixed mock bug in test_git_ahead_behind

## Decisions Made

- `poll_and_store` implemented as synchronous (time.sleep), not async — tests patch `app.services.remote_auth.time` directly, confirming sync design; router returns immediately after getting device_code without waiting for poll
- Router registers in server.py at plan completion — router tests use TestClient on app and 405 is the first indicator of missing registration
- `gitlab_api.validate_gitlab_token` and `remote_auth.validate_gitlab_token` both exist — router patches `remote_auth.validate_gitlab_token` for connect endpoint while gitlab_api provides the standalone module-level function

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] remote.router not registered in server.py**
- **Found during:** Task 2 verification (test_post_github_start)
- **Issue:** router stub from Plan 16-01 was never added to server.py; TestClient returned 405 for all /api/remote/* endpoints
- **Fix:** Added `from app.routers import remote` and `app.include_router(remote.router)` to server.py
- **Files modified:** app/server.py
- **Verification:** All router tests (test_post_github_start, test_get_github_status_*, test_post_gitlab_connect_*, test_post_push_success, test_get_remote_status_ahead_behind) pass GREEN
- **Committed in:** 8f0d59c (Task 2 commit)

**2. [Rule 1 - Bug] test_git_ahead_behind mock used list membership check for HEAD**
- **Found during:** Task 2 verification (test_git_ahead_behind)
- **Issue:** Mock condition `"HEAD" in args` performs Python list membership check; the range string "HEAD..origin/main" is a single list element, so "HEAD" != "HEAD..origin/main" → mock returned stdout="" → ahead=0, behind=0
- **Fix:** Changed `"HEAD" in args` to `any("HEAD" in a for a in args)` in the test mock, which correctly checks substring membership in any argument
- **Files modified:** tests/test_remote.py
- **Verification:** test_git_ahead_behind and test_git_ahead_behind_no_upstream both pass GREEN
- **Committed in:** 8f0d59c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes required for correctness. Router registration was an omission in the 16-01 stub; the mock bug was a type error in the RED scaffold that blocked implementation verification.

## Issues Encountered

- ruff SIM105: `try/except OSError: pass` → replaced with `contextlib.suppress(OSError)` in git_push cleanup
- ruff E501: CLIENT_ID comment reformatted to multi-line by ruff format hook

## Next Phase Readiness

- All service and git_ops implementations complete; Plan 16-03 can build the frontend RemotePanel connecting to /api/remote/* endpoints
- CLIENT_ID constant has TODO comment — must be replaced with registered GitHub OAuth App client_id before shipping

## Self-Check: PASSED

All key files found and both task commits verified in git history.

---
*Phase: 16-remote-auth-and-push*
*Completed: 2026-03-15*
