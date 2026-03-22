---
phase: 18-ci-polish
plan: "01"
subsystem: ci
tags: [tdd, red-state, gitlab-ci, github-actions, test-scaffold]
dependency_graph:
  requires: []
  provides: [tests/test_ci_github_comment.py, cleaned .gitlab-ci.yml]
  affects: [18-02-PLAN.md]
tech_stack:
  added: []
  patterns: [sys.path insertion for non-package script import, unittest.mock for urlopen]
key_files:
  created:
    - tests/test_ci_github_comment.py
  modified:
    - /Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml
decisions:
  - "Marker constant defined as module-level MARKER var in test file — single source of truth for expected first-line value"
  - "Tests use sys.path.insert to import non-package helper from alteryx repo — no install required"
  - "Task 2 committed in /alteryx repo (separate git repo) — correct git context for .gitlab-ci.yml change"
metrics:
  duration_min: 2
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 2
---

# Phase 18 Plan 01: CI Test Scaffold and GitLab Cleanup Summary

**One-liner:** RED test scaffold for CI-01/CI-02 marker and is_private_repo behaviours, plus GitLab CI test-job placeholder removed (CI-03).

## What Was Built

### Task 1 — RED test scaffold (tests/test_ci_github_comment.py)

7 failing tests in 3 groups, covering the CI-01 and CI-02 behaviours that Plan 02 will implement:

- **Group 1 (CI-01):** `test_build_comment_includes_marker`, `test_build_no_files_comment_includes_marker` — assert `<!-- acd-diff-report -->` is the first line of each function's output.
- **Group 2 (CI-02):** `test_is_private_repo_returns_true_on_missing_env`, `test_is_private_repo_returns_false_for_public`, `test_is_private_repo_returns_true_on_exception` — cover the three is_private_repo paths (missing env, public API response, urlopen exception).
- **Group 3 (CI-02):** `test_build_comment_contains_report_table_when_html_exists`, `test_build_comment_has_no_table_when_no_html` — assert per-file report table inclusion when html_count > 0.

All 7 tests fail with `TypeError: build_comment() got an unexpected keyword argument 'run_url'` and `AttributeError: module 'generate_diff_comment' has no attribute 'is_private_repo'` — RED state confirmed. Zero collection errors.

### Task 2 — GitLab CI cleanup (CI-03)

Removed from `/Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml`:
- The `test-job` block (stage: test, echo script)
- `- test` from the `stages:` list

Result: `stages:` now contains only `- diff`. The `alteryx-diff` job and all its configuration is unchanged.

## Verification

- `pytest tests/test_ci_github_comment.py -q` → 7 failed, 0 errors (RED confirmed)
- `grep -c "test-job" /alteryx/.gitlab-ci.yml` → 0
- `grep "stages" /alteryx/.gitlab-ci.yml -A 2` → shows only `- diff`

## Commits

| Task | Commit | Repo | Description |
|------|--------|------|-------------|
| 1 | 1e26cc4 | alteryx_diff | test(18-01): add RED test scaffold for CI-01 and CI-02 behaviours |
| 2 | 4f3d5aa | alteryx | chore(18-01): remove test-job placeholder from GitLab CI (CI-03) |

## Deviations from Plan

None — plan executed exactly as written. Pre-commit ruff E501 required shortening several docstring lines; no logic changed.

## Self-Check: PASSED
