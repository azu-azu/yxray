---
phase: 20
slug: tech-debt-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_autostart.py tests/test_main.py tests/test_projects.py -x -q` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_autostart.py tests/test_main.py tests/test_projects.py -x -q`
- **After every plan wave:** Run `pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | APP-02 | unit | `pytest tests/test_main.py -x -q -k autostart` | ✅ | ⬜ pending |
| 20-01-02 | 01 | 1 | APP-02 | unit | `pytest tests/test_autostart.py -x -q` | ✅ | ⬜ pending |
| 20-01-03 | 01 | 1 | — (maintainability) | unit | `pytest -x -q` | ✅ | ⬜ pending |
| 20-02-01 | 02 | 2 | ONBOARD-02 | manual | Visual verification — add project with duplicate path | N/A | ⬜ pending |
| 20-02-02 | 02 | 2 | REMOTE-02 | manual | Visual verification — GitLab tab switches without DOM query | N/A | ⬜ pending |
| 20-02-03 | 02 | 2 | — (dead props) | unit | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 20-03-01 | 03 | 3 | CI-01 | unit | `pytest tests/test_ci_gitlab_comment.py -x -q` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ci_gitlab_comment.py` — stubs for CI-01 marker detection + find-or-update logic (stdlib pattern mirrors `test_ci_github_comment.py`)

*No framework install required — pytest already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Add project 400/409 shows error in UI | ONBOARD-02 | React render state — no DOM test harness for this component | Add a project with a path already in the list; confirm red error text appears |
| GitLab tab switch via controlled state | REMOTE-02 | Tab interaction requires browser context | Click "Connect GitLab" CTA in RemotePanel; confirm gitlab tab activates without DOM query |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
