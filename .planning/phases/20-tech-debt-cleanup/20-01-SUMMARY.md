---
phase: 20-tech-debt-cleanup
plan: "01"
subsystem: app-core
tags: [autostart, type-safety, regression-fix, tdd]
dependency_graph:
  requires: []
  provides: [autostart-guard, config-store-overloads]
  affects: [app/main.py, app/services/config_store.py, tests/test_main.py]
tech_stack:
  added: []
  patterns: [module-level-import-for-patchability, tdd-red-green, typing-overload]
key_files:
  created: []
  modified:
    - app/main.py
    - app/services/config_store.py
    - tests/test_main.py
decisions:
  - "autostart and tray imports moved to module level so unittest.mock.patch targets work in tests"
  - "autostart guard placed in main.py caller (not inside register_autostart) per RESEARCH.md Pitfall 1"
  - "@overload stubs are documentation-only: zero runtime behavior change"
metrics:
  duration: "~8 min"
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_modified: 3
---

# Phase 20 Plan 01: Autostart Guard + config_store @overload Summary

**One-liner:** Autostart toggle regression fixed with `is_autostart_enabled()` guard in main.py; `get_remote_repo` annotated with `@overload` stubs for type-checker narrowing.

## What Was Built

### Task 1: Autostart Guard (TDD)

Fixed the APP-02 behavioral regression where every manual app launch unconditionally called `register_autostart()`, silently overwriting the user's Settings toggle.

**Changes to `app/main.py`:**
- Moved `autostart` and `tray` imports from lazy (inside `main()`) to module level — required for `unittest.mock.patch` targets to resolve correctly
- Added guard: `if not autostart.is_autostart_enabled(): autostart.register_autostart()`

**Changes to `tests/test_main.py`:**
- Added `test_main_does_not_reregister_when_already_enabled`: patches `is_autostart_enabled` to return `True`, asserts `register_autostart` is NOT called

TDD followed: test written first (RED — `AttributeError: module 'app.main' has no attribute 'autostart'`), then implementation drove it GREEN.

### Task 2: @overload for get_remote_repo

Added type-checker narrowing via `@overload` stubs to `app/services/config_store.py`:
- `get_remote_repo(project_id, provider: str) -> str | None`
- `get_remote_repo(project_id, provider: None = None) -> dict`
- Updated docstring to document both call forms
- Zero runtime behavioral change — implementation signature unchanged

## Verification Results

```
pytest tests/test_main.py tests/test_autostart.py -x -q
10 passed, 1 warning
```

Full suite: 235 passed, 1 xfailed (pre-existing environment port test excluded per STATE.md).

Guard line confirmed: `grep "if not autostart.is_autostart_enabled" app/main.py` returns line 89.
Overloads confirmed: `grep "@overload" app/services/config_store.py` returns lines 36 and 40.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | d1716b9 | feat(20-01): add autostart guard in main.py + new test |
| Task 2 | 66888a7 | feat(20-01): add @overload stubs for get_remote_repo dual return type |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] autostart not patchable as app.main.autostart**

- **Found during:** Task 1 RED phase — patch("app.main.autostart.is_autostart_enabled") failed with `AttributeError: module 'app.main' has no attribute 'autostart'`
- **Issue:** `autostart` was imported lazily inside `main()` — not accessible as a module attribute, so `unittest.mock.patch` couldn't resolve the target
- **Fix:** Moved both `autostart` and `tray` imports to module level; removed the lazy `from app.services import autostart  # noqa: PLC0415` and `from app import tray  # noqa: PLC0415` lines from inside `main()`
- **Files modified:** app/main.py
- **Commit:** d1716b9
