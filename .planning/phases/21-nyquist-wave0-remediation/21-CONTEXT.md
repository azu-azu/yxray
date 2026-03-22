# Phase 21: Nyquist Wave-0 Remediation - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Retroactively verify and update Nyquist wave_0 compliance for 9 already-completed v1.1 phases (10, 11, 12, 13, 14, 15, 16, 16.1, 19). Most referenced test files already exist — this phase audits what's there, fills any gaps, and flips `wave_0_complete: true` in each VALIDATION.md. Creating net-new application features is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Test coverage standard
- wave_0_complete: true requires test files to exist AND all tests to pass green
- Tests must pass on Linux CI only — Windows-specific behavior (system tray, registry, .exe) stays in Manual-Only Verifications as already documented
- Only frontmatter needs updating (wave_0_complete: true, nyquist_compliant: true) — per-task status table is too granular to maintain retroactively

### Gap-filling strategy
- If a test file exists but tests are still stubs (not yet passing): fix the stubs to make them pass green — do not use pytest.skip()
- If a wave_0 requirement lists a test file that doesn't exist at all: write it — all gaps must be filled
- For Windows-specific tests (e.g., actual winreg): write Linux-compatible versions using mocks (winreg is already mocked in test_autostart.py pattern)

### Plan structure
- 1 plan (21-01-PLAN.md) with one task per phase (9 tasks total: phases 10, 11, 12, 13, 14, 15, 16, 16.1, 19)
- Each task: audit wave_0 gaps → fix/write missing tests → run pytest for that phase's tests → update VALIDATION.md frontmatter
- Tasks run sequentially — each phase verified before moving to the next (easier to isolate failures)

### Claude's Discretion
- Which specific test assertions to write for any missing tests (should cover the critical path for the phase)
- Exact mock setup for platform-specific code

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py`: FastAPI TestClient fixture with tmp_path and monkeypatch — reusable for server/endpoint tests
- `tests/test_history.py`, `tests/test_save.py`, `tests/test_branch.py`: Established patterns for git repo fixtures using `_make_git_repo(tmp_path)` helper
- `tests/test_autostart.py`, `tests/test_tray.py`, `tests/test_main.py`: Windows-mocked patterns using monkeypatch/mock for winreg, socket, webbrowser
- `tests/test_watch.py`, `tests/test_projects.py`: Already-existing tests for phases 12 and 11

### Established Patterns
- All tests use pytest with tmp_path for isolation
- Windows-specific modules mocked via `unittest.mock.patch` or monkeypatch
- Git repo tests use subprocess to create real minimal git repos in tmp_path
- FastAPI endpoints tested via TestClient (not running server)

### Integration Points
- All 9 VALIDATION.md files already have "Wave 0 Requirements" sections listing expected test files
- Phase 19 VALIDATION.md explicitly says "no new test files needed — all 11 branch tests exist and are GREEN" — fastest to close
- CI runs `pytest tests/ -x -q` on Linux (ubuntu-latest)

</code_context>

<specifics>
## Specific Ideas

- Phase 19 should be the easiest — just verify tests pass and flip frontmatter
- Phase 15 (system tray) pattern is already established in test_autostart.py and test_tray.py — mocked winreg, not real Windows
- The `gsd:validate-phase` skill is prescribed by the roadmap for each phase

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-nyquist-wave0-remediation*
*Context gathered: 2026-03-22*
