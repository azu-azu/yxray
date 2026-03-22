---
phase: 13
slug: save-version
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-14
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pytest.ini (root) |
| **Quick run command** | `pytest tests/test_save.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_save.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | SAVE-01 | unit | `pytest tests/test_save.py -x` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | SAVE-01 | unit | `pytest tests/test_save.py::test_git_commit_files -x` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 1 | SAVE-01 | unit | `pytest tests/test_save.py::test_commit_endpoint -x` | ❌ W0 | ⬜ pending |
| 13-01-04 | 01 | 1 | SAVE-01 | unit | `pytest tests/test_save.py::test_commit_empty_files -x` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 2 | SAVE-02 | unit | `pytest tests/test_save.py::test_git_undo_last_commit -x` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 2 | SAVE-02 | unit | `pytest tests/test_save.py::test_undo_endpoint -x` | ❌ W0 | ⬜ pending |
| 13-03-01 | 03 | 2 | SAVE-03 | unit | `pytest tests/test_save.py::test_git_discard_files_backup -x` | ❌ W0 | ⬜ pending |
| 13-03-02 | 03 | 2 | SAVE-03 | unit | `pytest tests/test_save.py::test_git_discard_files_restore -x` | ❌ W0 | ⬜ pending |
| 13-03-03 | 03 | 2 | SAVE-03 | unit | `pytest tests/test_save.py::test_git_discard_untracked -x` | ❌ W0 | ⬜ pending |
| 13-03-04 | 03 | 2 | SAVE-03 | unit | `pytest tests/test_save.py::test_discard_endpoint -x` | ❌ W0 | ⬜ pending |
| 13-04-01 | 04 | 3 | SAVE-01,02,03 | manual | — | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_save.py` — stubs for all SAVE-01, SAVE-02, SAVE-03 backend tests
- [ ] `npx shadcn@latest add checkbox textarea` — required before ChangesPanel can be written

*Existing `tests/conftest.py` and shared fixtures are sufficient — no new conftest needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ChangesPanel renders with pre-checked files, commit message input, Save/Discard buttons | SAVE-01 | Frontend UI state machine — no E2E test framework | Open app with changed files; verify panel appears; verify all files pre-checked; enter message; click Save Version |
| SuccessCard appears post-save with Undo button | SAVE-02 | Frontend state transition after SSE badge clear | After save, verify Success card shows message, file count, "just now"; verify Undo button present |
| Undo confirmation dialog shows correct copy | SAVE-02 | Dialog UX copy verification | Click Undo; verify dialog says files won't change; click Undo Save; verify return to ChangesPanel |
| Discard confirmation dialog shows correct copy | SAVE-03 | Dialog UX copy verification | Select files; click Discard; verify dialog mentions .acd-backup; click Discard; verify files in .acd-backup folder |
| Initial commit warning callout appears on first save | SAVE-01 | Edge case UI state (no commits yet) | Use fresh repo; verify amber callout with "First version save" copy and truncated file list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
