---
phase: 20
slug: tech-debt-cleanup
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-22
audited: 2026-04-02
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
| 20-01-01 | 01 | 1 | APP-02 | unit | `pytest tests/test_main.py -x -q -k autostart` | ✅ | ✅ green |
| 20-01-02 | 01 | 1 | APP-02 | unit | `pytest tests/test_autostart.py -x -q` | ✅ | ✅ green |
| 20-01-03 | 01 | 1 | — (maintainability) | unit | `pytest -x -q` | ✅ | ✅ green |
| 20-02-01 | 02 | 2 | ONBOARD-02 | manual | Visual verification — add project with duplicate path | N/A | ✅ verified (human) |
| 20-02-02 | 02 | 2 | REMOTE-02 | manual | Visual verification — GitLab tab switches without DOM query | N/A | ✅ verified (human) |
| 20-02-03 | 02 | 2 | — (dead props) | unit | `cd app/frontend && npx tsc --noEmit` | ✅ | ✅ green |
| 20-03-01 | 03 | 3 | CI-01 | unit | `pytest tests/test_ci_gitlab_comment.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_ci_gitlab_comment.py` — stubs for CI-01 marker detection + find-or-update logic (stdlib pattern mirrors `test_ci_github_comment.py`) — **FULFILLED** — 5/5 tests pass; uses `importlib.util.spec_from_file_location` to avoid sys.modules collision with github comment module

*No framework install required — pytest already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Add project 400/409 shows error in UI | ONBOARD-02 | React render state — no DOM test harness for this component | Add a project with a path already in the list; confirm red error text appears |
| GitLab tab switch via controlled state | REMOTE-02 | Tab interaction requires browser context | Click "Connect GitLab" CTA in RemotePanel; confirm gitlab tab activates without DOM query |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s (pytest: 4.55s, tsc: <2s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ COMPLETE — audited 2026-04-02. All 7 tasks verified (5 automated green, 2 manual confirmed in VERIFICATION.md). Wave 0 file exists and passes. TypeScript compiles clean. Full pytest suite: 9/9 must-haves verified per VERIFICATION.md.
