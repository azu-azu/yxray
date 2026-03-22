---
phase: 17
slug: branch-management
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-15
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | BRANCH-01/02/03 | unit | `pytest tests/test_branch.py::test_git_list_branches -x -q` | ✅ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | BRANCH-01/02/03 | unit | `pytest tests/test_branch.py::test_git_create_branch -x -q` | ✅ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | BRANCH-01/02 | unit | `pytest tests/test_branch.py::test_git_checkout -x -q` | ✅ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | BRANCH-01/02/03 | unit | `pytest tests/test_branch.py -x -q` | ✅ W0 | ⬜ pending |
| 17-03-01 | 03 | 3 | BRANCH-03 | unit | `pytest tests/test_branch.py::test_list_branches_endpoint -x -q` | ✅ W0 | ⬜ pending |
| 17-03-02 | 03 | 3 | BRANCH-03 | manual | — | — | ⬜ pending |
| 17-04-01 | 04 | 4 | BRANCH-01/02/03 | unit | `pytest tests/test_branch.py::test_get_merge_base_endpoint -x -q` | ✅ W0 | ⬜ pending |
| 17-04-02 | 04 | 4 | BRANCH-01/02/03 | build | `cd app/frontend && npm run build` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_branch.py` — stubs for BRANCH-01, BRANCH-02, BRANCH-03 (created in Plan 01 Task 1)
  - test_git_list_branches
  - test_git_create_branch
  - test_branch_name_format
  - test_git_checkout
  - test_checkout_blocked_if_dirty
  - test_git_delete_branch
  - test_delete_main_blocked
  - test_list_branches_endpoint
  - test_list_history_with_branch
  - test_get_merge_base_endpoint (added in Plan 01 behavior; implemented in Plan 02 Task 2)

*Wave 0 is satisfied by Plan 01 (type: tdd) which creates tests/test_branch.py before any implementation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Branch label shown in UI header | BRANCH-03 | Frontend UI state — no automated DOM test | Open app, check header shows current branch name as plain text label |
| Switching branches updates UI label | BRANCH-02 | React state update — visual verification | Switch branch from popover, verify label updates without page reload |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
