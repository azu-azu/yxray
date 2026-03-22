---
phase: 21
slug: nyquist-wave0-remediation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `pytest tests/test_port_probe.py -x -q` |
| **Full suite command** | `pytest --tb=short -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest --tb=short -q`
- **After every plan wave:** Run `pytest --tb=short -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | Phase 10 fix | unit | `pytest tests/test_port_probe.py -x -q` | ✅ | ⬜ pending |
| 21-01-02 | 01 | 1 | Phase 11 frontmatter | none | `grep wave_0_complete .planning/phases/11-*/11-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-03 | 01 | 1 | Phase 12 frontmatter | none | `grep wave_0_complete .planning/phases/12-*/12-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-04 | 01 | 1 | Phase 13 frontmatter | none | `grep wave_0_complete .planning/phases/13-*/13-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-05 | 01 | 1 | Phase 14 frontmatter | none | `grep wave_0_complete .planning/phases/14-*/14-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-06 | 01 | 1 | Phase 15 frontmatter | none | `grep wave_0_complete .planning/phases/15-*/15-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-07 | 01 | 1 | Phase 16 frontmatter | none | `grep wave_0_complete .planning/phases/16-*/16-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-08 | 01 | 1 | Phase 16.1 frontmatter + path fix | none | `grep wave_0_complete .planning/phases/16.1-*/16.1-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-09 | 01 | 1 | Phase 19 frontmatter | none | `grep wave_0_complete .planning/phases/19-*/19-VALIDATION.md` | ✅ | ⬜ pending |
| 21-01-10 | 01 | 1 | Full suite green | integration | `pytest --tb=short -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_port_probe.py` — exists, 3 tests failing due to port 7433 conflict
- [x] All other phase test files exist and pass

*Existing infrastructure covers all phase requirements once port tests are fixed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
