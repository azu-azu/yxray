---
phase: 10
slug: app-scaffold
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | APP-01 | unit | `pytest tests/test_port_probe.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | APP-03 | unit | `pytest tests/test_server.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | APP-04 | unit | `pytest tests/test_cli_bundle.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | APP-01 | integration | `pytest tests/test_build.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | APP-03 | manual | N/A — requires Windows | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_port_probe.py` — stubs for APP-01 (port fallback logic)
- [ ] `tests/test_server.py` — stubs for APP-03 (server startup, browser open)
- [ ] `tests/test_cli_bundle.py` — stubs for APP-04 (acd CLI accessible at runtime)
- [ ] `tests/test_build.py` — stubs for APP-01 (PyInstaller .exe build smoke test)
- [ ] `tests/conftest.py` — shared fixtures (mock uvicorn, mock socket)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| .exe runs standalone on Windows without Python | APP-01 | Requires actual Windows machine + PyInstaller build | Build .exe, copy to clean Windows VM, double-click, verify no Python error |
| Browser tab opens at correct localhost:PORT | APP-03 | Requires running .exe process | Run .exe, verify OS default browser opens at correct URL |
| Port fallback works when 7433 is occupied | APP-03 | Requires live port manipulation | Occupy 7433, run .exe, verify server starts on 7434 |
| acd diff output correct inside .exe | APP-04 | End-to-end bundled CLI test | Run .exe, trigger diff via UI, verify output matches standalone acd CLI |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
