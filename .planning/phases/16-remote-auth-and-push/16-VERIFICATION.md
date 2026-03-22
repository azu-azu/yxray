---
phase: 16-remote-auth-and-push
verified: 2026-03-15T09:00:00Z
status: human_needed
score: 12/12 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 7/12
  gaps_closed:
    - "keyring>=24.0 and httpx>=0.27 added to pyproject.toml dependencies; uv.lock updated; keyring 25.7.0 installed"
    - "All 29 tests in tests/test_remote.py now pass GREEN (previously 18 of 29 failed)"
    - "Connect GitLab CTA button in renderDisconnectedCTA() now has onClick handler that programmatically clicks the GitLab tab trigger"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Full end-to-end GitHub device flow"
    expected: "User sees user_code and verification_uri, enters code on github.com, app polls until authorized, GitHub shows Connected badge with username, credentials persist across app restart"
    why_human: "Real GitHub OAuth device flow with live HTTP calls and OS keyring interaction cannot be verified headlessly"
  - test: "Full end-to-end GitLab PAT connection"
    expected: "User pastes a valid GitLab PAT, app validates it via GET /api/v4/user, GitLab shows Connected badge with username, credential persists in OS keyring across restart"
    why_human: "Requires live GitLab API call and OS keyring write/read"
  - test: "Connect GitLab CTA button navigation"
    expected: "With no provider connected, clicking [Connect GitLab] in the empty-state banner visually activates the GitLab tab and shows the PAT input form"
    why_human: "onClick uses document.querySelector('[data-value=\"gitlab\"]').click() — requires visual confirmation in the browser that the tab switches correctly"
  - test: "Single-button push to GitHub or GitLab"
    expected: "After connecting a provider, clicking [Push to Remote] creates a remote repo if none exists and pushes all local commits; ahead/behind indicator updates to 0 ahead"
    why_human: "Requires connected credentials, a real remote repository, and live git network calls"
  - test: "Credential persistence across restart"
    expected: "After connecting GitHub or GitLab, kill and relaunch the dev server — Remote panel shows Connected badge without re-authenticating"
    why_human: "Requires OS keyring interaction and app restart cycle"
---

# Phase 16: Remote Auth and Push Verification Report

**Phase Goal:** Users can authenticate with GitHub or GitLab, back up saved versions to a remote with a single button, auto-create the remote repo if needed, and see at a glance how far ahead or behind they are from the remote
**Verified:** 2026-03-15T09:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | GitHub device flow start returns user_code and verification_uri | ✓ VERIFIED | test_request_device_code PASSED; remote_auth.py now fully importable (keyring 25.7.0 installed) |
| 2  | GitHub/GitLab tokens stored in OS keyring, never in config_store | ✓ VERIFIED | keyring>=24.0 in pyproject.toml; uv.lock pins keyring 25.7.0; test_store_and_get_github_token and test_credentials_not_in_config_store both PASSED |
| 3  | GitLab PAT validated via GET /api/v4/user, stored on success | ✓ VERIFIED | test_validate_gitlab_token_valid and test_post_gitlab_connect_valid PASSED |
| 4  | GitHub repo creation calls POST /user/repos with private:true | ✓ VERIFIED | test_create_github_repo_private PASSED; github_api.py line 54-60 confirmed |
| 5  | Name collision detection appends -2, -3 suffix | ✓ VERIFIED | test_find_available_repo_name_collision PASSED |
| 6  | git_push uses GIT_ASKPASS, token never in URL | ✓ VERIFIED | test_git_push_uses_askpass_not_url_token PASSED; git_ops.py GIT_ASKPASS pattern confirmed |
| 7  | git_ahead_behind returns (ahead, behind) tuple; (0,0) when no upstream | ✓ VERIFIED | test_git_ahead_behind and test_git_ahead_behind_no_upstream PASSED |
| 8  | git_fetch uses GIT_ASKPASS, silently ignores non-zero returncode | ✓ VERIFIED | test_git_fetch_uses_askpass PASSED |
| 9  | Per-project remote URL stored in config_store, not keyring | ✓ VERIFIED | test_config_store_set_and_get_remote_repo and test_config_store_get_remote_repo_missing PASSED |
| 10 | All 29 tests in tests/test_remote.py pass GREEN | ✓ VERIFIED | 29/29 PASSED in 1.52s |
| 11 | Sidebar cloud icon opens Remote panel; AppShell routes to RemotePanel | ✓ VERIFIED | AppShell.tsx line 88-90 routes 'remote' to RemotePanel; Sidebar.tsx onOpenRemote prop wired; regression check passed |
| 12 | RemotePanel disconnected CTA shows working Connect GitHub and Connect GitLab buttons | ✓ VERIFIED | Connect GitHub onClick=startGithubDeviceFlow (line 434); Connect GitLab onClick queries [data-value="gitlab"] tab trigger and clicks it (lines 437-439) |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `pyproject.toml` | ✓ VERIFIED | keyring>=24.0 at line 19; httpx>=0.27 at line 20; both present and locked in uv.lock (keyring 25.7.0) |
| `app/services/remote_auth.py` | ✓ VERIFIED | Imports successfully at runtime; python3 -c "from app.services import remote_auth" exits 0 |
| `app/services/github_api.py` | ✓ VERIFIED | 71 lines, all 5 functions implemented, httpx calls confirmed |
| `app/services/gitlab_api.py` | ✓ VERIFIED | Both functions implemented |
| `app/services/git_ops.py` | ✓ VERIFIED | git_push, git_fetch, git_ahead_behind all present and tested GREEN |
| `app/routers/remote.py` | ✓ VERIFIED | All 7 endpoints implemented; imports successfully (keyring chain no longer blocked) |
| `app/server.py` | ✓ VERIFIED | app.include_router(remote.router) at line 62 confirmed |
| `app/services/config_store.py` | ✓ VERIFIED | get_remote_repo and set_remote_repo helpers confirmed |
| `app/frontend/src/components/RemotePanel.tsx` | ✓ VERIFIED | 487+ lines; device flow UI, GitLab PAT form, ahead/behind display, push button, CTA buttons all present and wired |
| `app/frontend/src/components/AppShell.tsx` | ✓ VERIFIED | 'remote' activeView routes to RemotePanel; regression check passed |
| `app/frontend/src/components/Sidebar.tsx` | ✓ VERIFIED | Cloud icon, onOpenRemote prop wired |
| `tests/test_remote.py` | ✓ VERIFIED | 29/29 tests PASSED |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_remote.py` | `app/services/remote_auth` | direct import | ✓ WIRED | Import succeeds; all related tests PASSED |
| `tests/test_remote.py` | `app/routers/remote` | TestClient import | ✓ WIRED | Router imports cleanly; test_post_github_start, test_post_push_success, etc. PASSED |
| `app/services/remote_auth.py` | keyring | keyring.set_password / get_password | ✓ WIRED | keyring 25.7.0 installed; test_store_and_get_github_token PASSED |
| `app/services/remote_auth.py` | https://github.com/login/device/code | httpx.post | ✓ WIRED | httpx 0.27.2 installed; DEVICE_CODE_URL constant + httpx.post confirmed |
| `app/services/github_api.py` | https://api.github.com/user/repos | httpx.post | ✓ WIRED | create_github_repo confirmed |
| `app/routers/remote.py` | `app/services/git_ops` | from app.services import git_ops | ✓ WIRED | Confirmed at remote.py line 19 |
| `app/routers/remote.py` | `app/services/remote_auth` | from app.services import remote_auth | ✓ WIRED | Import chain unblocked; router loads cleanly |
| `app/server.py` | `app/routers/remote` | app.include_router(remote.router) | ✓ WIRED | Line 62 of server.py confirmed |
| `AppShell.tsx` | `RemotePanel.tsx` | import + 'remote' branch | ✓ WIRED | Line 10 and 88-90 of AppShell.tsx |
| `Sidebar.tsx` | AppShell | onOpenRemote prop | ✓ WIRED | Regression check confirmed |
| `RemotePanel.tsx` | `/api/remote/status` | fetch in useEffect | ✓ WIRED | fetchStatus() called in useEffect confirmed |
| `RemotePanel.tsx` | `/api/remote/push` | fetch POST in handlePush() | ✓ WIRED | handlePush() confirmed |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| REMOTE-01 | GitHub browser-based OAuth (device flow) | ✓ VERIFIED | test_request_device_code, test_poll_authorization_pending, test_poll_slow_down_increases_interval, test_post_github_start, test_get_github_status_connected all PASSED |
| REMOTE-02 | GitLab PAT with in-app step-by-step instructions and direct link | ✓ VERIFIED (code) / ? HUMAN | test_validate_gitlab_token_valid, test_post_gitlab_connect_valid, test_get_gitlab_status_connected PASSED; frontend GitLab tab with 1-2-3 instructions and Open GitLab Settings link confirmed; end-to-end requires human with live GitLab instance |
| REMOTE-03 | Auth credentials in OS credential store via keyring | ✓ VERIFIED | keyring 25.7.0 installed; test_store_and_get_github_token and test_credentials_not_in_config_store PASSED |
| REMOTE-04 | Single-button push to GitHub/GitLab | ✓ VERIFIED (code) / ? HUMAN | test_post_push_success PASSED; git_push GIT_ASKPASS confirmed; push button wired in RemotePanel; live push requires human |
| REMOTE-05 | Auto-create remote repo on first push | ✓ VERIFIED (code) / ? HUMAN | test_create_github_repo_private, test_create_gitlab_project_private PASSED; push endpoint calls create logic; live repo creation requires human |
| REMOTE-06 | Ahead/behind indicator | ✓ VERIFIED | test_git_ahead_behind, test_get_remote_status_ahead_behind, test_get_remote_status_includes_repo_url all PASSED; frontend ahead/behind display confirmed in RemotePanel.tsx |

All 6 REMOTE requirements are covered and have passing test evidence. Live end-to-end flows require human verification.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/frontend/src/components/RemotePanel.tsx` | 437-439 | Connect GitLab CTA uses document.querySelector('[data-value="gitlab"]') DOM query rather than controlled React state | ℹ️ Info | Works if the tabs component renders a DOM element with data-value="gitlab"; brittle if shadcn Tabs changes its DOM output |

No blocker anti-patterns remain. The single warning from the previous verification (missing keyring/httpx) is resolved. The Connect GitLab CTA onClick uses a DOM-level tab activation approach rather than lifting controlled state — functional but worth noting as a minor code quality item.

---

## Human Verification Required

### 1. Full end-to-end GitHub device flow

**Test:** Start the dev server (`uv run uvicorn app.server:app`). Open the Remote panel. Click [Connect GitHub]. Confirm a user_code and verification_uri appear. Enter the code at github.com/login/device. Wait for the app to poll and show the Connected badge with your GitHub username.
**Expected:** GitHub shows a green Connected badge. Closing and reopening the app shows the same Connected state without re-authenticating.
**Why human:** Real GitHub OAuth device flow with live HTTP calls and OS keyring interaction cannot be verified headlessly.

### 2. Full end-to-end GitLab PAT connection

**Test:** In the Remote panel, switch to the GitLab tab. Follow the on-screen numbered steps, generate a PAT in GitLab settings, paste it into the input, and click Connect GitLab.
**Expected:** GitLab shows a green Connected badge with your GitLab username. Credential persists across app restart.
**Why human:** Requires live GitLab API call and OS keyring write/read.

### 3. Connect GitLab CTA button navigation

**Test:** With no provider connected, the empty-state banner shows both [Connect GitHub] and [Connect GitLab]. Click [Connect GitLab].
**Expected:** The GitLab tab activates and the PAT input form becomes visible.
**Why human:** onClick programmatically clicks the shadcn Tabs trigger DOM element — requires visual confirmation in the browser that the tab switch works correctly.

### 4. Single-button push to GitHub or GitLab

**Test:** After connecting GitHub, open a project that has local commits not yet pushed. Click [Push to Remote] in the Remote panel.
**Expected:** If no remote repo exists, the app creates one automatically and pushes all commits. Ahead/behind indicator updates to 0 ahead.
**Why human:** Requires connected credentials, a real remote repository, and live git network calls.

### 5. Credential persistence across restart

**Test:** After connecting GitHub (device flow) or GitLab (PAT), kill and relaunch the dev server (`Ctrl-C` then `uv run uvicorn app.server:app`). Open the Remote panel.
**Expected:** The Connected badge still shows the correct username without re-authenticating.
**Why human:** Requires OS keyring read on app startup.

---

## Re-verification Summary

### Gaps closed

All three gaps from the initial verification have been resolved:

**Gap 1 — Missing keyring dependency:** `keyring>=24.0` and `httpx>=0.27` are now declared in `pyproject.toml` and are present in `uv.lock` (keyring 25.7.0). `from app.services import remote_auth` now imports successfully.

**Gap 2 — 18 failing tests:** All 29 tests in `tests/test_remote.py` pass GREEN (1.52s). Every previously-failing test — including all auth, router, push, and credential tests — now passes.

**Gap 3 — Dead Connect GitLab CTA button:** `RemotePanel.tsx` lines 437-439 now include an `onClick` handler that programmatically activates the GitLab tab by querying `[data-value="gitlab"]` and calling `.click()`.

### No regressions detected

All 12 previously-passing truths continue to hold. Import chains, server wiring, Sidebar/AppShell routing, and frontend component structure are unchanged and verified.

### Remaining human verification

Automated verification is complete. The 5 items above require a running dev server with real GitHub/GitLab credentials and OS keyring access.

---

_Verified: 2026-03-15T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
