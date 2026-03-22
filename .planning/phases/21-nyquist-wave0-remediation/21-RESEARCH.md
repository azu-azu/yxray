# Phase 21: Nyquist Wave-0 Remediation - Research

**Researched:** 2026-03-22
**Domain:** pytest test infrastructure audit, existing test file verification
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- wave_0_complete: true requires test files to exist AND all tests pass green
- Tests must pass on Linux CI only — Windows-specific behavior (system tray, registry, .exe) stays in Manual-Only Verifications as already documented
- Only frontmatter needs updating (wave_0_complete: true, nyquist_compliant: true) — per-task status table is too granular to maintain retroactively
- If a test file exists but tests are still stubs (not yet passing): fix the stubs to make them pass green — do not use pytest.skip()
- If a wave_0 requirement lists a test file that doesn't exist at all: write it — all gaps must be filled
- For Windows-specific tests (e.g., actual winreg): write Linux-compatible versions using mocks (winreg is already mocked in test_autostart.py pattern)
- 1 plan (21-01-PLAN.md) with one task per phase (9 tasks total: phases 10, 11, 12, 13, 14, 15, 16, 16.1, 19)
- Each task: audit wave_0 gaps → fix/write missing tests → run pytest for that phase's tests → update VALIDATION.md frontmatter
- Tasks run sequentially — each phase verified before moving to the next

### Claude's Discretion

- Which specific test assertions to write for any missing tests (should cover the critical path for the phase)
- Exact mock setup for platform-specific code

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 21 retroactively flips 9 VALIDATION.md files to `wave_0_complete: true`. The research confirms that for 8 of the 9 phases (11, 12, 13, 14, 15, 16, 16.1, 19) all test files already exist and all tests currently pass — those phases only need a frontmatter update. Phase 10 is the only phase requiring real work: its port probe tests are environment-sensitive (fail when port 7433 is already bound on the developer machine) and will also fail on CI if the port is occupied. The fix is to mock the socket binding in `test_port_probe.py` so all three tests pass regardless of environment.

Phase 16.1 has a minor mismatch: its VALIDATION.md references `app/tests/test_git_ops.py` as the Wave 0 gap, but the `git_pushed_shas` and `is_pushed` tests were actually written in `tests/test_history.py` (which passes green). The VALIDATION.md text should be corrected to reference the correct file when flipping frontmatter.

**Primary recommendation:** Fix Phase 10 port tests first (the only real code change), then flip all 9 VALIDATION.md frontmatters. Phase 19 is the trivially fastest close.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.x | Test runner for all backend tests | Already installed, used by all 240 existing tests |
| unittest.mock | stdlib | Mocking Windows-specific modules (winreg, socket) | Already used throughout — no extra dep |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI TestClient | (via httpx) | Testing HTTP endpoints without running server | Already used in conftest.py fixture |
| tmp_path (pytest fixture) | built-in | Isolated git repo creation in tests | Already used in test_branch.py, test_history.py, test_save.py |

**Installation:** No new packages needed — all dependencies already installed.

---

## Architecture Patterns

### Established Pattern: `_make_git_repo(tmp_path)`

Every test that needs a git repo uses subprocess to create a minimal git repo in a temp dir. The pattern is already established in test_branch.py, test_history.py, test_save.py, test_watch.py.

```python
# Pattern from test_branch.py
import subprocess

def _make_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)
    return path
```

### Established Pattern: Windows Module Mocking

For winreg, pystray, and other Windows-only modules, the project uses `unittest.mock.patch.dict(sys.modules, ...)` to inject fake modules before importing the real app modules.

```python
# Pattern from test_autostart.py
import sys
from unittest.mock import MagicMock, patch

fake_winreg = MagicMock()
fake_winreg.HKEY_CURRENT_USER = 0x80000001
fake_winreg.OpenKey.return_value.__enter__ = lambda s: fake_winreg
fake_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

with patch.dict(sys.modules, {"winreg": fake_winreg}):
    from app.services import autostart
```

### Established Pattern: FastAPI TestClient via conftest.py

```python
# From tests/conftest.py
@pytest.fixture
def client(tmp_path, monkeypatch):
    # Creates minimal index.html, patches _static_dir, builds test_app
    # with routes copied from app.server.app
    yield TestClient(test_app)
```

### Anti-Patterns to Avoid

- **Using `pytest.skip()`:** Locked decision says fix stubs, not skip them.
- **Real network calls in tests:** All remote tests mock keyring, subprocess, and HTTP calls.
- **Real port binding assertions:** Port 7433 may be occupied — must use socket mocking.
- **test_build.py (PyInstaller smoke):** Phase 10 VALIDATION lists it as Wave 0 but it requires a Windows runner. It stays as Manual-Only — do not write it for Linux CI.

---

## Per-Phase Gap Analysis

This section is the core of the research — the exact state of each phase.

### Phase 10 — App Scaffold

**Current state:** NEEDS CODE CHANGES

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_port_probe.py | YES | NO — 3 failures | Environment-sensitive: tests bind to real port 7433, fail when it's occupied |
| tests/test_server.py | YES | YES | None |
| tests/test_cli_bundle.py | YES | YES | None |
| tests/test_build.py | NO | N/A | Windows-only PyInstaller build — stays Manual-Only |

**Root cause of port failures:** `test_find_available_port_returns_7433` asserts `port == 7433` but the app itself is running on 7433 during development, causing the function to return 7434. This will also fail on CI if anything binds 7433 first.

**Fix required:** Mock the socket binding in `test_port_probe.py` so the function under test operates against a predictable, controlled environment. Use `unittest.mock.patch` on `socket.socket` or pre-bind a known-free port for the duration of the test.

**Alternative fix (simpler):** Use `monkeypatch` to pre-release port 7433 before the test — but this is still environment-sensitive. Better: rewrite the test to use mocking so it doesn't depend on real port availability at all. The `test_find_available_port_skips_occupied` and `test_find_available_port_raises_when_all_full` tests can work via real socket binding to ephemeral ports (avoid 7433 specifically).

**Concrete recommended approach for Phase 10:**
- `test_find_available_port_returns_7433`: patch `socket.socket` constructor to return a mock that succeeds on first bind. This avoids real ports entirely.
- `test_find_available_port_skips_occupied` and `test_find_available_port_raises_when_all_full`: rewrite using high ephemeral port ranges (e.g., 19900–19910) that are extremely unlikely to be occupied on CI, avoiding 7433.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 11 — Onboarding and Project Management

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_projects.py | YES | YES (8 tests) | None |
| tests/test_git_identity.py | YES | YES (2 tests) | None |

Note: VALIDATION.md already has `nyquist_compliant: true` but `wave_0_complete: false`. Just needs the wave_0 flag flipped.

**Frontmatter action:** Update `wave_0_complete: true` (nyquist_compliant already true)

---

### Phase 12 — File Watcher

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_watch.py | YES | YES (12 tests) | None |

All 9 Wave 0 test functions from VALIDATION.md are present: `test_git_changed_workflows`, `test_count_workflows`, `test_is_network_path_unc_backslash`, `test_is_network_path_unc_forward`, `test_is_network_path_local_unix`, `test_badge_push_on_rescan`, `test_polling_observer_for_network`, `test_sse_endpoint_headers`, `test_watch_status_no_commits`, `test_watch_status_total_workflows` — plus 2 more bonus tests.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 13 — Save Version

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_save.py | YES | YES (11 tests) | None |

All Wave 0 test functions present: `test_git_commit_files`, `test_git_commit_files_empty_files_list`, `test_commit_endpoint`, `test_commit_empty_files`, `test_git_undo_last_commit`, `test_undo_endpoint`, `test_git_discard_files_backup`, `test_git_discard_files_restore`, `test_git_discard_untracked`, `test_discard_endpoint` — plus bonus tests.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 14 — History and Diff Viewer

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_history.py | YES | YES (13 tests) | None |

All Wave 0 test functions present: `test_git_log`, `test_git_log_empty`, `test_list_history_endpoint`, `test_list_history_empty`, `test_diff_endpoint`, `test_diff_endpoint_first_commit`, `test_git_show_file` — plus bonus tests (including Phase 16.1 additions).

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 15 — System Tray and Auto-Start

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_autostart.py | YES | YES (6 tests) | None |
| tests/test_settings.py | YES | YES (4 tests) | None |
| tests/test_tray.py | YES | YES (5 tests) | None |
| tests/test_main.py | YES | YES (4 tests) | None |

All wave_0 test functions present and passing.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 16 — Remote Auth and Push

**Current state:** FRONTMATTER ONLY

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_remote.py | YES | YES (28 tests) | None |

All 19+ Wave 0 test functions from VALIDATION.md are present and pass.

Note: VALIDATION.md already has `nyquist_compliant: true` but `wave_0_complete: false`. Just needs the wave_0 flag flipped.

**Frontmatter action:** Update `wave_0_complete: true` (nyquist_compliant already true)

---

### Phase 16.1 — Git History UX with Push Integration and Git Graph View

**Current state:** FRONTMATTER ONLY + VALIDATION.md text correction

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_history.py | YES | YES (13 tests including is_pushed) | None |

The VALIDATION.md Wave 0 Requirements section references:
- `app/tests/test_git_ops.py` — this file does NOT exist and was never created
- `app/tests/test_history.py` — wrong path (should be `tests/test_history.py`)

The actual tests (`test_git_pushed_shas_no_upstream`, `test_git_pushed_shas_uses_upstream_ref`, `test_list_history_includes_is_pushed`, `test_list_history_is_pushed_false_when_not_in_set`) are all in `tests/test_history.py` and pass green.

**Action:** Update VALIDATION.md Wave 0 Requirements to reflect reality (tests are in tests/test_history.py), then flip frontmatter.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

### Phase 19 — Close Audit Gaps

**Current state:** FRONTMATTER ONLY (easiest phase)

| Test File | Exists | Passes | Gap |
|-----------|--------|--------|-----|
| tests/test_branch.py | YES | YES (11 tests) | None |

VALIDATION.md already says "All 11 branch tests exist and are GREEN" in the Wave 0 Requirements section.

**Frontmatter action:** Update `wave_0_complete: true`, `nyquist_compliant: true`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Socket mocking for port tests | Custom socket replacement class | `unittest.mock.patch('socket.socket')` | Standard mock pattern, zero overhead |
| Git repo in tests | Real git operations against real repos | `_make_git_repo(tmp_path)` helper | Already established project pattern |
| Windows API in CI tests | Skip or guard tests | `patch.dict(sys.modules, {'winreg': fake_winreg})` | Already established in test_autostart.py |

---

## Common Pitfalls

### Pitfall 1: test_port_probe.py Will Fail on CI if Not Fixed

**What goes wrong:** The test binds to real port 7433. On CI, if the app process or another test occupies the port, the assertion `port == 7433` fails.

**Why it happens:** The test was written assuming 7433 is free, which is true on a fresh CI runner but not on a developer machine with a running app instance.

**How to avoid:** Use `unittest.mock.patch` to control `socket.socket` behavior rather than real port binding. For `test_find_available_port_returns_7433`, mock the socket constructor to return a fake socket that reports success on first bind attempt. For the occupied-port tests, bind to a high ephemeral port range (e.g., 19900+) that's not 7433 to avoid conflicts.

**Warning signs:** `OSError: [Errno 48] Address already in use` or assertion `7434 == 7433` in CI logs.

### Pitfall 2: Flipping Wave 0 Without Running Tests First

**What goes wrong:** If frontmatter is flipped before verifying tests actually pass in the current repo state, CI may be broken.

**Why it happens:** Implicit assumption that "tests exist" equals "tests pass."

**How to avoid:** Each task must run `pytest tests/<phase-specific-tests> -x -q` and confirm green before updating VALIDATION.md frontmatter.

### Pitfall 3: Phase 16.1 Correcting Wrong Path May Confuse Planner

**What goes wrong:** VALIDATION.md says `app/tests/test_git_ops.py` but reality is `tests/test_history.py`. If the planner tries to create `app/tests/test_git_ops.py` it introduces confusion.

**How to avoid:** Research finding (HIGH confidence): the tests are already in `tests/test_history.py` and pass. The VALIDATION.md text update replaces the incorrect path reference, no new file creation needed.

---

## Code Examples

### Port Test Mocking Pattern (Phase 10 Fix)

```python
# Source: unittest.mock standard library
from unittest.mock import MagicMock, patch
import socket

def test_find_available_port_returns_7433(monkeypatch):
    """find_available_port() returns 7433 when it is free."""
    real_socket_class = socket.socket

    def mock_socket_factory(*args, **kwargs):
        s = MagicMock(spec=real_socket_class)
        s.bind = MagicMock()  # succeeds without error
        s.__enter__ = lambda self: self
        s.__exit__ = MagicMock(return_value=False)
        return s

    with patch('socket.socket', side_effect=mock_socket_factory):
        from app.main import find_available_port
        port, sock = find_available_port(start=7433, count=11)
        assert port == 7433
```

### Frontmatter Update Pattern (All 9 Phases)

Each VALIDATION.md starts with:
```yaml
---
phase: XX
slug: phase-name
status: draft
nyquist_compliant: false   # change to true
wave_0_complete: false     # change to true
created: YYYY-MM-DD
---
```

The only two fields that change are `nyquist_compliant: true` and `wave_0_complete: true`.

### Verifying Each Phase Before Flip

```bash
# Phase 10 (after port test fix)
python -m pytest tests/test_port_probe.py tests/test_server.py tests/test_cli_bundle.py -x -q

# Phase 11
python -m pytest tests/test_projects.py tests/test_git_identity.py -x -q

# Phase 12
python -m pytest tests/test_watch.py -x -q

# Phase 13
python -m pytest tests/test_save.py -x -q

# Phase 14
python -m pytest tests/test_history.py -x -q

# Phase 15
python -m pytest tests/test_settings.py tests/test_autostart.py tests/test_tray.py tests/test_main.py -x -q

# Phase 16
python -m pytest tests/test_remote.py -x -q

# Phase 16.1 (uses test_history.py for git_pushed_shas and is_pushed)
python -m pytest tests/test_history.py -x -q -k "pushed_shas or is_pushed"

# Phase 19
python -m pytest tests/test_branch.py -x -q

# Full suite gate (ignore known-deferred port test OR fix it first)
python -m pytest tests/ -x -q
```

---

## State of the Art

| Old State | New State | What Changes |
|-----------|-----------|--------------|
| 9 VALIDATION.md files: wave_0_complete: false | 9 VALIDATION.md files: wave_0_complete: true | Frontmatter reflects reality |
| test_port_probe.py: 3 failures (environment-sensitive) | test_port_probe.py: 3 passing (mocked socket) | Robust on all environments including CI |
| Phase 16.1 VALIDATION references non-existent app/tests/test_git_ops.py | Phase 16.1 VALIDATION references existing tests/test_history.py | Documentation matches reality |

**Known deferred item not in scope:** `test_find_available_port_returns_7433` failure was already documented in `.planning/phases/15-system-tray-and-auto-start/deferred-items.md`. Phase 21 resolves it by fixing the test.

---

## Open Questions

1. **Should test_port_probe.py use full mock or ephemeral-port strategy?**
   - What we know: Current tests fail when port 7433 is occupied by the running app
   - What's unclear: Full socket mocking is clean but more code; ephemeral port rewrite (use ports 19900+) is simpler but still does real socket binding
   - Recommendation: Full `unittest.mock.patch('socket.socket')` for `test_find_available_port_returns_7433` (cleanest); real socket binding on ephemeral ports (19900-19910) for the occupied/raises tests (simpler, still robust on CI)

2. **Phase 16 VALIDATION references conftest.py as a Wave 0 gap — is conftest.py already sufficient?**
   - What we know: `tests/conftest.py` exists with FastAPI TestClient fixture; test_remote.py passes with 28 tests
   - What's unclear: Whether the VALIDATION.md meant "add remote-specific conftest fixtures" or just "ensure conftest.py exists"
   - Recommendation: Existing conftest.py is sufficient — tests pass, no gap to fill, just flip frontmatter

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` with `pythonpath = ["."]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements to Test Map

Phase 21 has no formal requirement IDs. The success criteria maps to:

| Criteria | Test Type | Automated Command |
|----------|-----------|-------------------|
| Phase 10 port tests pass in all environments | unit (mocked) | `pytest tests/test_port_probe.py -x -q` |
| Phase 11 tests green | unit | `pytest tests/test_projects.py tests/test_git_identity.py -x -q` |
| Phase 12 tests green | unit/integration | `pytest tests/test_watch.py -x -q` |
| Phase 13 tests green | unit/integration | `pytest tests/test_save.py -x -q` |
| Phase 14 tests green | unit/integration | `pytest tests/test_history.py -x -q` |
| Phase 15 tests green | unit (mocked) | `pytest tests/test_autostart.py tests/test_settings.py tests/test_tray.py tests/test_main.py -x -q` |
| Phase 16 tests green | unit (mocked) | `pytest tests/test_remote.py -x -q` |
| Phase 16.1 tests green (in test_history.py) | unit/integration | `pytest tests/test_history.py -x -q` |
| Phase 19 tests green | unit | `pytest tests/test_branch.py -x -q` |
| Full suite green | all | `python -m pytest tests/ -q` |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/<phase-specific-tests> -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] Fix `tests/test_port_probe.py` — 3 tests need socket mocking to pass in any environment (Phase 10 only gap)

All other test files exist and pass. No new test files need to be created.

---

## Sources

### Primary (HIGH confidence)

- Direct inspection of `tests/` directory — file existence verified
- `python -m pytest tests/ -q --tb=no` — 240 passing, 3 failing (all 3 in test_port_probe.py), 1 xfailed
- `python -m pytest tests/test_projects.py tests/test_git_identity.py tests/test_watch.py tests/test_save.py tests/test_history.py tests/test_autostart.py tests/test_settings.py tests/test_tray.py tests/test_main.py tests/test_remote.py tests/test_branch.py -q --tb=no` — 106 passing, 0 failing
- All 9 VALIDATION.md files read directly — Wave 0 Requirements sections compared against actual test file contents
- `.planning/phases/15-system-tray-and-auto-start/deferred-items.md` — confirms port test failure is pre-existing known issue

### Secondary (MEDIUM confidence)

- STATE.md decision log — confirms test_port_probe failure is pre-existing environment-specific issue deferred to Phase 15 deferred-items.md
- CONTEXT.md locked decisions — confirm strategy for this phase

---

## Metadata

**Confidence breakdown:**
- Per-phase gap analysis: HIGH — verified by running the tests
- Port test fix approach: HIGH — standard unittest.mock pattern used throughout the project
- Phase 16.1 file path correction: HIGH — confirmed tests exist in test_history.py and pass
- Frontmatter updates: HIGH — mechanical change to known fields

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable test infrastructure, no fast-moving dependencies)
