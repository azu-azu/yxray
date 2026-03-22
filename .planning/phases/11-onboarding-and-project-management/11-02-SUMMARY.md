---
phase: 11-onboarding-and-project-management
plan: "02"
subsystem: api
tags: [fastapi, subprocess, git, platformdirs, tkinter, pydantic, pytest]

# Dependency graph
requires:
  - phase: 11-01
    provides: skeleton routers with 501 stubs, RED test suite with 10 failing tests
provides:
  - config_store.py with load_config/save_config using platformdirs + JSON
  - git_ops.py with is_git_repo/git_init/get_git_identity/set_git_identity via subprocess
  - projects.py full GET/check/POST/DELETE router with validation and git init logic
  - git_identity.py full GET/POST /api/git/identity router
  - folder_picker.py asyncio.to_thread + tkinter-inside-function folder picker
affects: [12-file-watcher, 13-save-history, frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Import module-level (from app.services import config_store) so mock patches work on module attribute
    - tkinter imported inside function body to prevent headless CI crash
    - asyncio.to_thread for blocking I/O (folder picker) rather than loop.run_in_executor
    - git config check=False for optional keys (exit 1 = not set, not an error)
    - /check route defined before /{project_id} catch-all to avoid FastAPI routing ambiguity

key-files:
  created: []
  modified:
    - app/services/config_store.py
    - app/services/git_ops.py
    - app/routers/projects.py
    - app/routers/git_identity.py
    - app/routers/folder_picker.py

key-decisions:
  - "Projects router imports config_store/git_ops as modules (not named imports) so unittest.mock.patch targets work correctly"
  - "git_identity router imports app.services.git_ops as module alias — patch target app.services.git_ops.get_git_identity works"
  - "Path not resolved (no Path.resolve()) in add_project to keep test assertions aligned with tmp_path on macOS (/var vs /private/var symlink)"
  - "Folder picker: tkinter imported inside _pick_folder() body; wm_attributes -topmost set before askdirectory"

patterns-established:
  - "Router module imports: use module-level import (from app.services import svc) and call svc.fn() — keeps mock patch targets predictable"
  - "Blocking OS dialog: wrap in sync function, call via asyncio.to_thread from async endpoint"
  - "Git subprocess: check=False for optional config reads, check=True for writes"

requirements-completed: [ONBOARD-01, ONBOARD-02, ONBOARD-03, ONBOARD-04]

# Metrics
duration: 4min
completed: 2026-03-13
---

# Phase 11 Plan 02: Onboarding Backend Implementation Summary

**FastAPI backend fully implemented: 5 service/router modules replace 501 stubs, all 10 RED test cases turn GREEN via subprocess git ops and platformdirs config persistence**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-14T03:27:35Z
- **Completed:** 2026-03-14T03:31:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- config_store.py: load_config/save_config fully implemented using platformdirs + json with default dict fallback
- git_ops.py: is_git_repo, git_init, get_git_identity, set_git_identity via subprocess; get_git_identity uses check=False (exit 1 = key not set)
- projects.py: full CRUD with /check endpoint before /{id} catch-all, 400/409/404 error handling, git_init only when needed
- git_identity.py: GET/POST with module-level import pattern for correct mock patch behavior
- folder_picker.py: asyncio.to_thread + tkinter inside function body (headless CI safe), wm_attributes -topmost for Windows
- All 10 test cases GREEN, 0 regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement config_store and git_ops services** - `805608a` (feat)
2. **Task 2: Implement all three routers and make tests GREEN** - `09df1ee` (feat)

## Files Created/Modified

- `app/services/config_store.py` - load_config/save_config using platformdirs user_data_dir + json
- `app/services/git_ops.py` - subprocess wrappers: is_git_repo, git_init, get_git_identity (check=False), set_git_identity
- `app/routers/projects.py` - GET /check (before /{id}), GET, POST (400/409), DELETE (404) with config_store + git_ops module imports
- `app/routers/git_identity.py` - GET/POST using `import app.services.git_ops as git_ops_svc` module alias pattern
- `app/routers/folder_picker.py` - async pick_folder with asyncio.to_thread + tkinter-inside-function pattern

## Decisions Made

- Import module-level (not named import) in routers so `unittest.mock.patch` targets (`app.services.git_ops.get_git_identity`) work correctly — named imports would break mock patching
- Path not resolved via Path.resolve() in add_project because tmp_path on macOS resolves /var -> /private/var, causing test assertion `data["path"] == folder` to fail
- Ruff line-length fix: folder_picker docstring shortened to fit 88-char limit during pre-commit hook

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff line-length violations in folder_picker.py**
- **Found during:** Task 2 commit (pre-commit hook)
- **Issue:** Docstring "Run in a thread (blocking). tkinter imported here to prevent headless CI crash." exceeded 88-char limit; wm_attributes inline comment also exceeded
- **Fix:** Shortened docstring to "...to avoid headless CI crash."; ruff auto-reformatted wm_attributes call to multi-line
- **Files modified:** app/routers/folder_picker.py
- **Verification:** ruff check passes, tests still GREEN
- **Committed in:** 09df1ee (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - linting)
**Impact on plan:** Minor cosmetic fix. No behavior change.

## Issues Encountered

- Python mock patch targeting: `app.services.git_ops.get_git_identity` patch works only if router holds a module reference (not a named import). Resolved by importing `import app.services.git_ops as git_ops_svc` in git_identity.py.
- macOS /var symlink: tmp_path resolves to /private/var/... but str(tmp_path) is /var/... — skipped Path.resolve() in add_project to keep tests passing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend API fully functional; frontend can now call real endpoints
- Phase 12 (file watcher) can build on is_git_repo and project config structure
- GET /api/projects/check provides pre-flight data for frontend confirmation dialogs before git init

---
*Phase: 11-onboarding-and-project-management*
*Completed: 2026-03-13*
