---
phase: 16
slug: remote-auth-and-push
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-15
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_remote.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_remote.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | REMOTE-01 | unit | `uv run pytest tests/test_remote.py::test_request_device_code -x -q` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | REMOTE-01 | unit | `uv run pytest tests/test_remote.py::test_poll_authorization_pending -x -q` | ❌ W0 | ⬜ pending |
| 16-01-03 | 01 | 1 | REMOTE-03 | unit | `uv run pytest tests/test_remote.py::test_store_and_get_github_token -x -q` | ❌ W0 | ⬜ pending |
| 16-02-01 | 02 | 2 | REMOTE-02 | unit | `uv run pytest tests/test_remote.py::test_validate_gitlab_token_valid -x -q` | ❌ W0 | ⬜ pending |
| 16-02-02 | 02 | 2 | REMOTE-02 | unit | `uv run pytest tests/test_remote.py::test_validate_gitlab_token_invalid -x -q` | ❌ W0 | ⬜ pending |
| 16-03-01 | 03 | 2 | REMOTE-04 | unit | `uv run pytest tests/test_remote.py::test_git_push_calls_subprocess -x -q` | ❌ W0 | ⬜ pending |
| 16-03-02 | 03 | 2 | REMOTE-05 | unit | `uv run pytest tests/test_remote.py::test_create_github_repo_private -x -q` | ❌ W0 | ⬜ pending |
| 16-03-03 | 03 | 2 | REMOTE-05 | unit | `uv run pytest tests/test_remote.py::test_create_gitlab_project_private -x -q` | ❌ W0 | ⬜ pending |
| 16-03-04 | 03 | 2 | REMOTE-06 | unit | `uv run pytest tests/test_remote.py::test_git_ahead_behind -x -q` | ❌ W0 | ⬜ pending |
| 16-04-01 | 04 | 3 | REMOTE-01,02,03,04,05,06 | automated | `uv run pytest tests/test_remote.py -x -q` | ❌ W0 | ⬜ pending |
| 16-04-02 | 04 | 3 | REMOTE-01..06 | manual | — | — | ⬜ pending |
| 16-05-01 | 05 | 4 | REMOTE-01,02,03,04,05,06 | manual | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_remote.py` — stubs for REMOTE-01 through REMOTE-06 (19 test functions, one file)
- [ ] `tests/conftest.py` — shared fixtures (mock keyring, mock git repo, mock HTTP)

*Existing test infrastructure (pytest) covers all phase requirements — Wave 0 only needs new test files.*

### Expected test functions in tests/test_remote.py (19 total)

From Plan 16-01 behavior blocks:
- `test_request_device_code`
- `test_poll_authorization_pending`
- `test_poll_slow_down_increases_interval`
- `test_store_and_get_github_token`
- `test_credentials_not_in_config_store`
- `test_validate_gitlab_token_valid`
- `test_validate_gitlab_token_invalid`
- `test_create_github_repo_private`
- `test_find_available_repo_name_collision`
- `test_create_gitlab_project_private`
- `test_git_push_calls_subprocess`
- `test_git_push_uses_askpass_not_url_token`
- `test_git_ahead_behind`
- `test_git_ahead_behind_no_upstream`
- `test_post_github_start`
- `test_get_github_status_connected`
- `test_get_github_status_disconnected`
- `test_post_github_connect`
- `test_post_gitlab_connect_valid`
- `test_post_gitlab_connect_invalid`
- `test_post_push_success`
- `test_get_remote_status_ahead_behind`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub browser OAuth flow opens browser | REMOTE-01 | Requires real browser + GitHub OAuth app | Launch app, click "Connect GitHub", verify browser opens to device flow URL |
| GitLab PAT step-by-step instructions displayed | REMOTE-02 | UI/UX validation | Open GitLab connect dialog, verify instructions are clear and link is present |
| Credentials survive app restart | REMOTE-03 | Requires OS keychain access | Connect GitHub, restart app, verify still authenticated |
| Single-button push works end-to-end | REMOTE-04 | Requires real remote repo | Save a version, click push, verify appears on GitHub/GitLab |
| Auto-create repo on first push | REMOTE-05 | Requires real GitHub/GitLab account | Delete test repo, push again, verify repo auto-created |
| Ahead/behind indicator accuracy | REMOTE-06 | Requires real remote refs | Make local commits, verify indicator updates after panel opens/push |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (single file: tests/test_remote.py)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
