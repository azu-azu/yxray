---
phase: 14
slug: history-and-diff-viewer
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-14
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, confirmed in tests/) |
| **Config file** | pyproject.toml (existing project) |
| **Quick run command** | `pytest tests/test_history.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_history.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | HIST-01, HIST-02 | unit/endpoint | `pytest tests/test_history.py -x` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 1 | HIST-01 | unit | `pytest tests/test_history.py::test_git_log -x` | ❌ W0 | ⬜ pending |
| 14-02-02 | 02 | 1 | HIST-01 | unit | `pytest tests/test_history.py::test_git_log_empty -x` | ❌ W0 | ⬜ pending |
| 14-02-03 | 02 | 1 | HIST-01 | endpoint | `pytest tests/test_history.py::test_list_history_endpoint -x` | ❌ W0 | ⬜ pending |
| 14-02-04 | 02 | 1 | HIST-01 | endpoint | `pytest tests/test_history.py::test_list_history_empty -x` | ❌ W0 | ⬜ pending |
| 14-03-01 | 03 | 2 | HIST-02 | endpoint | `pytest tests/test_history.py::test_diff_endpoint -x` | ❌ W0 | ⬜ pending |
| 14-03-02 | 03 | 2 | HIST-02 | endpoint | `pytest tests/test_history.py::test_diff_endpoint_first_commit -x` | ❌ W0 | ⬜ pending |
| 14-03-03 | 03 | 2 | HIST-02 | unit | `pytest tests/test_history.py::test_git_show_file -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_history.py` — stubs for HIST-01 and HIST-02 (RED tests before implementation)
- [ ] `app/routers/history.py` — new router stub required for TestClient imports
- [ ] Register `history.router` in `app/server.py` — required for endpoint tests to reach router

*All test files are new; existing infrastructure (conftest.py, pytest config) covers fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| History timeline renders correctly in UI with date/author/commit message | HIST-01 | Frontend rendering requires browser | Load app, save a version, open history tab, verify flat timeline |
| Clicking history entry shows ACD diff inline (no new tab) | HIST-02 | iframe blob URL rendering requires browser | Click any history entry, verify iframe appears with ACD HTML report |
| Project-switch clears history and diff viewer | HIST-01, HIST-02 | UI state transition requires browser | Switch projects, verify history panel resets |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
