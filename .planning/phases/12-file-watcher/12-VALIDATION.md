---
phase: 12
slug: file-watcher
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-14
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_watch.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_watch.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 0 | WATCH-01 | unit | `pytest tests/test_watch.py::test_git_changed_workflows -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 0 | WATCH-01 | unit | `pytest tests/test_watch.py::test_count_workflows -x` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 0 | WATCH-02 | unit | `pytest tests/test_watch.py::test_is_network_path_unc -x` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 0 | WATCH-02 | unit | `pytest tests/test_watch.py::test_is_network_path_local -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 1 | WATCH-01 | unit | `pytest tests/test_watch.py::test_badge_push_on_rescan -x` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 1 | WATCH-02 | unit | `pytest tests/test_watch.py::test_polling_observer_for_network -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 1 | WATCH-01 | integration | `pytest tests/test_watch.py::test_sse_endpoint_headers -x` | ❌ W0 | ⬜ pending |
| 12-03-02 | 03 | 2 | WATCH-03 | integration | `pytest tests/test_watch.py::test_watch_status_no_commits -x` | ❌ W0 | ⬜ pending |
| 12-03-03 | 03 | 2 | WATCH-03 | integration | `pytest tests/test_watch.py::test_watch_status_total_workflows -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_watch.py` — stubs for WATCH-01, WATCH-02, WATCH-03 (all 9 test functions above)
- [ ] Extend `tests/` with `git_changed_workflows`, `count_workflows`, `git_has_commits` helper tests

*Existing pytest infrastructure covers this phase — no new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Amber badge appears in sidebar after modifying a .yxmd file | WATCH-01 | Requires real Alteryx save with OS file events | Open project in UI, modify a .yxmd file, confirm amber badge appears within 2 seconds |
| PollingObserver auto-selected for UNC/SMB path | WATCH-02 | Requires network share environment | Register a \\server\share project, confirm in logs that PollingObserver is used |
| Badge clears after version save (Phase 13 integration) | WATCH-01 | Phase 13 not yet built | Will verify in Phase 13 UAT |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
