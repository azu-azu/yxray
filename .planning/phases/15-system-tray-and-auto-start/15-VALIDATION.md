---
phase: 15
slug: system-tray-and-auto-start
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-14
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, 156 tests passing) |
| **Config file** | pytest.ini (pythonpath=['.']) |
| **Quick run command** | `python -m pytest tests/test_settings.py tests/test_autostart.py tests/test_tray.py -x -q` |
| **Full suite command** | `python -m pytest -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_settings.py tests/test_autostart.py tests/test_tray.py -x -q`
- **After every plan wave:** Run `python -m pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | APP-02 | unit (mock winreg) | `pytest tests/test_autostart.py -x -q` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 0 | APP-04b | unit (mock autostart) | `pytest tests/test_settings.py -x -q` | ❌ W0 | ⬜ pending |
| 15-01-03 | 01 | 0 | APP-05 | unit | `pytest tests/test_tray.py -x -q` | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 0 | APP-02 | unit (mock webbrowser/socket) | `pytest tests/test_main.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 1 | APP-02 | unit | `pytest tests/test_autostart.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-02 | 02 | 1 | APP-02 | unit | `pytest tests/test_main.py::test_background_flag_suppresses_browser -x` | ❌ W0 | ⬜ pending |
| 15-02-03 | 02 | 1 | APP-02 | unit | `pytest tests/test_main.py::test_is_instance_running_true -x` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 1 | APP-05 | unit | `pytest tests/test_tray.py -x -q` | ❌ W0 | ⬜ pending |
| 15-04-01 | 04 | 1 | APP-04b | unit | `pytest tests/test_settings.py -x -q` | ❌ W0 | ⬜ pending |
| 15-05-01 | 05 | 2 | APP-02, APP-05 | manual | See Manual-Only section | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_autostart.py` — stubs for APP-02 (register/unregister/is_enabled with mocked winreg)
- [ ] `tests/test_settings.py` — stubs for APP-04b (GET/POST /api/settings with mocked autostart module)
- [ ] `tests/test_tray.py` — stubs for APP-05 (tray state computation `_compute_state()` pure function)
- [ ] `tests/test_main.py` — stubs for APP-02 (--background flag, second-instance detection with mock socket/webbrowser)

*Framework already installed; no new test infrastructure needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| System tray icon appears in Windows taskbar area | APP-05 | Requires Windows OS + physical display | Run bundled .exe, verify icon visible in system tray |
| Left-click opens browser at localhost:PORT | APP-04b | Requires interactive UI | Left-click tray icon, verify browser opens |
| Right-click shows "Open" + "Quit" menu | APP-05 | Requires interactive UI | Right-click tray icon, verify menu entries |
| Tray icon changes to watching state when watcher is running | APP-05 | Requires visual comparison of icons | Start a project watcher, verify icon changes |
| Tray icon changes to changes-detected state | APP-05 | Requires visual comparison of icons | Modify a tracked file, verify icon changes to amber |
| App starts on Windows boot silently | APP-02 | Requires Windows restart | Reboot Windows, verify app in system tray, no console window, no browser open |
| console=False prevents console window flash | APP-02 | Requires bundled .exe + Windows | Run bundled .exe, verify no console window appears |
| Quit from tray exits the process | APP-05 | Requires interactive UI | Click Quit, verify process exits (check Task Manager) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
