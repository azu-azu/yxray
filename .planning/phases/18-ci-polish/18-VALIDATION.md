---
phase: 18
slug: ci-polish
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-15
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (unit tests) + YAML linting + file inspection |
| **Config file** | none — tests live in tests/test_ci_github_comment.py |
| **Quick run command** | `cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest tests/test_ci_github_comment.py -q 2>&1 \| tail -5` |
| **Full suite command** | `python -m pytest tests/test_ci_github_comment.py -v && find ci-templates/ -type f \| sort` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Verify file exists and content matches intent
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-T1 | 01 | 1 | CI-01, CI-02 | automated | `cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest tests/test_ci_github_comment.py -x -q 2>&1 \| tail -5` | tests/test_ci_github_comment.py | ⬜ pending |
| 18-01-T2 | 01 | 1 | CI-03 | automated | `grep -c "test-job" /Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml` | /Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml | ⬜ pending |
| 18-02-T1 | 02 | 2 | CI-01, CI-02 | automated | `cd /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff && python -m pytest tests/test_ci_github_comment.py -q 2>&1 \| tail -5` | /Users/laxmikantmukkawar/alteryx/.github/scripts/generate_diff_comment.py | ⬜ pending |
| 18-02-T2 | 02 | 2 | CI-01 | automated | `grep -c "listComments" /Users/laxmikantmukkawar/alteryx/.github/workflows/pr-diff-report.yml` | /Users/laxmikantmukkawar/alteryx/.github/workflows/pr-diff-report.yml | ⬜ pending |
| 18-03-T1 | 03 | 3 | CI-04 | automated | `find /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff/ci-templates -type f \| sort` | ci-templates/ (directory) | ⬜ pending |
| 18-03-T2 | 03 | 3 | CI-04 | automated | `wc -l /Users/laxmikantmukkawar/Documents/Projects/alteryx_diff/ci-templates/README.md` | ci-templates/README.md | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is Plan 01 Task 1: the RED test scaffold. This task creates tests/test_ci_github_comment.py with 7 failing tests before any implementation is written. Wave 0 is complete when pytest collects the tests without ImportError and all 7 tests fail with AttributeError or AssertionError (not collection errors).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PR comment updates instead of creating new | CI-01 | Requires GitHub Actions runtime | Check workflow YAML uses find-or-update pattern with `listComments` + MARKER constant |
| Per-file HTML report table in PR comment | CI-02 | Requires GitHub Actions runtime | Check generate_diff_comment.py builds `| Workflow File |` table when html_count > 0; is_private_repo() controls note text |
| No test-job in GitLab CI | CI-03 | File inspection | `grep "test-job" /Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml` returns empty |
| README complete setup instructions | CI-04 | Content quality judgment | Read ci-templates/README.md — covers GITHUB_TOKEN, GITLAB_TOKEN, expose_as, and step-by-step copy for both GitHub and GitLab |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all test scaffold creation (Plan 01 Task 1)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
