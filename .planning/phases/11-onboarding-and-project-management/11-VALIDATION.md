---
phase: 11
slug: onboarding-and-project-management
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| Task 1: Install dependencies and create backend skeleton | 01 | 1 | ONBOARD-01,02,03,04 | import | `python -c "from app.routers import projects; print('OK')"` | ❌ W0 | ⬜ pending |
| Task 2: Write failing test stubs (RED phase) | 01 | 1 | ONBOARD-01,02,04 | collect | `pytest tests/test_projects.py tests/test_git_identity.py --collect-only -q` | ❌ W0 | ⬜ pending |
| Task 1: Implement config_store and git_ops services | 02 | 2 | ONBOARD-02 | unit | `pytest tests/test_projects.py -x -q` | ❌ W0 | ⬜ pending |
| Task 2: Implement all three routers (including check endpoint) | 02 | 2 | ONBOARD-02,03 | integration | `pytest tests/test_projects.py tests/test_git_identity.py -v` | ❌ W0 | ⬜ pending |
| Task 1: Register routers in server.py | 04 | 3 | ONBOARD-04 | integration | `pytest tests/test_server.py tests/test_projects.py -x -q` | ❌ W0 | ⬜ pending |
| Task 2: Implement GitIdentityCard and wire add-folder flow | 04 | 3 | ONBOARD-02,03 | build | `cd app/frontend && npx tsc --noEmit && npm run build` | N/A | ⬜ pending |
| Task 2: Verify complete onboarding flow end-to-end | 05 | 4 | ONBOARD-01,02,03,04 | e2e | manual — verify all 5 UX steps per Plan 05 Task 2 | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is Plan 01. The following files must exist before Plan 02 executes:

- [ ] `tests/test_projects.py` — stubs for ONBOARD-01 first-run detection, ONBOARD-02 folder add + git init + check endpoint, ONBOARD-04 project switching (10 test stubs total)
- [ ] `tests/test_git_identity.py` — stubs for ONBOARD-03 git identity detection

Note: No `tests/conftest.py` is needed for this phase. Mocking is done inline within each test function using `unittest.mock.patch`. If shared fixtures become necessary during execution, they can be added then — but it is not a Wave 0 requirement.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Welcome screen shown on first launch | ONBOARD-01 | Requires browser window to render; no headless test | Launch app fresh (no config), verify welcome screen appears before any other UI |
| Project list shows in left panel | ONBOARD-04 | UI layout verification | Add 2 projects, verify both appear in left panel and clicking switches active project |
| Native folder picker opens | ONBOARD-02 | OS dialog; cannot be automated headlessly | Click "Add folder" button, verify OS file picker opens |
| Folder with no git history: pre-confirmation dialog appears BEFORE any git operation | ONBOARD-02 | Requires OS folder picker + live backend | Select a non-git folder; verify "Set up version control?" dialog appears with Cancel and Set Up buttons BEFORE git init runs; Cancel aborts entirely |
| Folder with existing git history: added silently | ONBOARD-02 | Requires OS folder picker + live backend | Add a git repo folder; verify NO dialog appears at any point |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (Plans 01 creates all test files)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
