---
phase: 20-tech-debt-cleanup
plan: "03"
subsystem: ci
tags: [gitlab, python, ci, comment-dedup, find-or-update, testing]

# Dependency graph
requires:
  - phase: 20-01
    provides: autostart guard and config_store @overload stubs
  - phase: 20-02
    provides: frontend tech debt fixes (controlled tabs, dead props, error feedback)
  - phase: 18-ci-polish
    provides: GitHub Actions find-or-update comment pattern (reference implementation)
provides:
  - GitLab CI find-or-update MR comment — second pipeline run updates existing comment via PUT instead of POST
  - MARKER constant in generate_diff_comment.py (GitLab) matching GitHub version
  - post_or_update_note() function dispatching PUT vs POST based on existing marker presence
  - 5 tests covering marker, PUT dispatch, POST dispatch, and no-token skip
  - Human verification of all 6 Phase 20 tech debt items confirmed resolved
affects: [future-ci-plans, phase-21]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "find-or-update comment pattern: list notes, check marker, PUT if found else POST — mirrors GitHub Actions dedup"
    - "sys.path.insert import pattern for non-package scripts in separate repo (mirrors test_ci_github_comment.py)"
    - "post_or_update_note() reads GITLAB_TOKEN at call time (not module level) for test patchability with patch.dict"

key-files:
  created:
    - tests/test_ci_gitlab_comment.py
  modified:
    - /Users/laxmikantmukkawar/alteryx/.gitlab/scripts/generate_diff_comment.py
    - /Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml

key-decisions:
  - "post_or_update_note() re-reads GITLAB_TOKEN at call time so patch.dict works in tests — module-level read would be stale after patching"
  - "CI_MERGE_REQUEST_IID used (not CI_MERGE_REQUEST_ID) — notes API path requires iid per GitLab docs"
  - "MARKER added to GitLab generate_diff_comment.py build_comment()/build_no_files_comment() output — Python owns the marker, not shell"
  - "curl POST block replaced by Python post_or_update_note() call — token check handled internally by function"

patterns-established:
  - "find-or-update pattern: list → scan marker → PUT existing or POST new (consistent across GitHub and GitLab CI)"

requirements-completed: [CI-01]

# Metrics
duration: 30min
completed: 2026-03-22
---

# Phase 20 Plan 03: GitLab CI Find-or-Update MR Comment Summary

**GitLab CI comment dedup parity with GitHub Actions: post_or_update_note() replaces curl POST with PUT-or-POST dispatch keyed on <!-- acd-diff-report --> marker**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-03-22T20:00:00Z
- **Completed:** 2026-03-22T20:37:34Z
- **Tasks:** 3 (including human verification checkpoint)
- **Files modified:** 3

## Accomplishments

- Added MARKER constant and post_or_update_note() to GitLab generate_diff_comment.py, matching GitHub Actions parity
- Replaced .gitlab-ci.yml curl POST block with Python post_or_update_note() invocation
- Created 5-test suite in tests/test_ci_gitlab_comment.py covering all dispatch paths (PUT when found, POST when not found, skip when no token)
- Human verified all 6 Phase 20 tech debt items end-to-end and confirmed resolved

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 test scaffold + generate_diff_comment.py marker + post_or_update_note()** - `290b954` (test/feat — TDD RED then GREEN in alteryx repo)
2. **Task 2: Update .gitlab-ci.yml to call post_or_update_note()** - `7793078` (fix — committed in /Users/laxmikantmukkawar/alteryx repo)
3. **Task 3: Human verification checkpoint** - approved (no code change — checkpoint gate)

**Plan metadata:** committed with docs(20-03) commit

_Note: Tasks 1 and 2 committed in separate git repos: alteryx_diff (test file) and alteryx (.gitlab files)_

## Files Created/Modified

- `tests/test_ci_gitlab_comment.py` - 5 tests: marker in build_comment/build_no_files_comment, PUT dispatch, POST dispatch, no-token skip
- `/Users/laxmikantmukkawar/alteryx/.gitlab/scripts/generate_diff_comment.py` - Added MARKER constant, prepend to build_comment()/build_no_files_comment(), added list_notes()/post_note()/update_note()/post_or_update_note()
- `/Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml` - Replaced curl --request POST .../notes block with Python post_or_update_note() invocation

## Decisions Made

- `post_or_update_note()` re-reads `os.environ.get("GITLAB_TOKEN")` at call time rather than using module-level `_TOKEN` — necessary for `patch.dict` to work in tests since module-level reads happen at import time before patching
- `CI_MERGE_REQUEST_IID` used (not `CI_MERGE_REQUEST_ID`) — GitLab notes API path is `merge_requests/:iid`; using `:id` would silently hit the wrong resource
- Python owns the MARKER — build_comment() prepends it, not the shell block in .gitlab-ci.yml — consistent with GitHub version and avoids double-marker if script is called multiple times
- The outer `if [ -n "$GITLAB_TOKEN" ]` shell guard was removed — post_or_update_note() handles the missing-token case internally with an early return and warning print

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 20 (tech debt cleanup) is complete — all 6 items resolved and human-verified
- CI-01 requirement marked complete: GitLab CI find-or-update parity with GitHub Actions
- Phase 21 (or any future CI work) can rely on consistent comment dedup behavior across both GitHub and GitLab

---
*Phase: 20-tech-debt-cleanup*
*Completed: 2026-03-22*
