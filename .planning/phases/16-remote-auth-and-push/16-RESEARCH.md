# Phase 16: Remote Auth and Push - Research

**Researched:** 2026-03-15
**Domain:** GitHub OAuth Device Flow, GitLab PAT, keyring credential storage, git push via subprocess, GitHub/GitLab REST API
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **GitHub OAuth mechanism:** Device flow (OAuth Device Authorization Grant) — app shows a code + `github.com/login/device` URL; user opens browser, enters code, clicks Authorize
- **PAT fallback:** Supported for environments where device flow is blocked — user pastes token manually
- **GitHub scopes:** `repo` only
- **After connect:** Green "Connected" status badge shown in Remote panel; no username display needed in v1
- **GitHub OAuth App:** Must be registered; `client_id` baked into the app
- **GitLab auth:** PAT only (no OAuth for GitLab in this phase)
- **GitLab UX:** Inline numbered 1-2-3 steps + "Open GitLab Settings" button linking to token settings page
- **Credential storage:** `keyring` (Windows Credential Manager / macOS Keychain) — never plaintext
- **Credential scope:** Global (one GitHub account, one GitLab account) — applies to all projects
- **Remote panel:** New sidebar nav item (cloud icon) between History and Settings; two tabs (GitHub | GitLab)
- **Per-project remote:** Each project folder maps to its own remote repo
- **AppShell `activeView`:** Gains new `'remote'` branch alongside `'default'`, `'settings'`
- **Auto-repo creation:** Repo name = folder name slugified; always private; brief inline confirmation before creating; collision suffix (`-2`, `-3`)
- **Ahead/behind indicator:** Displayed in Remote panel above Push button; format `↑ 3 ahead · ↓ 0 behind`; refreshes on panel open and after each push only (no background polling)
- **Disconnected empty state:** CTA copy with [Connect GitHub] and [Connect GitLab] buttons

### Claude's Discretion

- Exact copy/phrasing for GitLab PAT step-by-step instructions
- Loading/spinner states during OAuth polling and push operations
- Error message copy for push failures (network error, auth expired, etc.)
- How to surface push progress for large repos (progress indicator vs. simple spinner)

### Deferred Ideas (OUT OF SCOPE)

- Pull / sync from remote
- Disconnect / revoke token flow (possible small follow-up in Phase 16 or 17 — noted)
- Multiple GitHub accounts
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REMOTE-01 | User can connect to GitHub using browser-based OAuth (no PAT required) | GitHub Device Flow endpoints, polling mechanism, error codes documented below |
| REMOTE-02 | User can connect to GitLab using a personal access token with in-app instructions and direct link to GitLab settings | GitLab PAT auth header format and validation endpoint documented below |
| REMOTE-03 | Auth credentials stored in OS credential store (Windows Credential Manager / macOS Keychain via keyring) | keyring 25.7 API, PyInstaller bundling fix documented below |
| REMOTE-04 | User can back up (push) saved versions with a single button | git push via subprocess with GIT_ASKPASS credential injection documented below |
| REMOTE-05 | If no remote repo exists, app creates one automatically on GitHub or GitLab when user first pushes | GitHub POST /user/repos and GitLab POST /api/v4/projects endpoints documented below |
| REMOTE-06 | Ahead/behind indicator shows how many saves are local-only vs. remote-only | git rev-list --count commands and git fetch strategy documented below |
</phase_requirements>

---

## Summary

Phase 16 involves four distinct technical sub-problems: (1) GitHub OAuth Device Flow polling — a multi-step async protocol with a specific error code vocabulary; (2) GitLab PAT validation via a simple REST call; (3) OS credential storage via the `keyring` library, which has a known PyInstaller bundling issue requiring an explicit workaround in app.spec; (4) git push via subprocess with safe credential injection using `GIT_ASKPASS`, keeping tokens out of git config and process listings. The REST API calls for auto-repo creation and ahead/behind counting are straightforward single-request operations once the token is in hand.

The project already uses the subprocess-only pattern for all git operations (no GitPython). The new services (`remote_auth.py`, `github_api.py`) must follow the module-level import pattern established in Phases 11–15 to enable `unittest.mock.patch`. The frontend needs the shadcn `Tabs` component (not yet in the UI directory) and follows the self-fetching panel pattern already established by `SettingsPanel`.

**Primary recommendation:** Implement GitHub Device Flow as a polling loop on the backend (FastAPI background task or synchronous poll endpoint), store credentials in `keyring` with explicit backend registration to fix PyInstaller discovery, and use `GIT_ASKPASS` environment variable injection for `git push` to keep tokens out of `.git/config`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `keyring` | 25.7.0 | OS credential store (Windows Credential Manager / macOS Keychain) | Only cross-platform Python library for OS-native credential storage; zero-plaintext guarantee |
| `requests` | already in Python stdlib-compat; use `httpx` or `urllib.request` | GitHub/GitLab REST API calls | Project currently uses `subprocess` + stdlib; `httpx` matches FastAPI's async style; no extra dependency if sync calls are acceptable |
| shadcn `Tabs` | (shadcn CLI) | GitHub/GitLab tab switcher in Remote panel | Already decided; matches existing shadcn pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | latest (add to pyproject.toml) | HTTP client for GitHub/GitLab REST API calls | Async-compatible, already in FastAPI ecosystem; preferred over `requests` for FastAPI backends |
| `slugify` (optional) | — | Folder name → repo slug | Only if slug logic is complex; a simple inline regex (`re.sub(r'[^a-z0-9]+', '-', ...)`) avoids a dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `httpx` calls | `PyGithub` or `python-gitlab` | Libraries add ~5MB+ to bundle; raw httpx calls are 3–4 lines each; for this phase's narrow scope (create repo, get user info) raw calls are cleaner |
| `GIT_ASKPASS` credential injection | Embed token in remote URL | URL embedding leaks token in `.git/config` and process listings; `GIT_ASKPASS` is the safe pattern |
| `httpx` | `urllib.request` (stdlib) | `urllib.request` avoids adding a dependency but is verbose; `httpx` is already in the FastAPI ecosystem; acceptable trade-off |

**Installation:**
```bash
uv add keyring httpx
# shadcn Tabs component:
npx shadcn@latest add tabs
```

---

## Architecture Patterns

### Recommended File Structure
```
app/
├── routers/
│   └── remote.py               # All /api/remote/* endpoints
├── services/
│   ├── remote_auth.py          # GitHub device flow, PAT validation, keyring read/write
│   └── github_api.py           # GitHub REST: repo create, ahead/behind, user info
│   └── gitlab_api.py           # GitLab REST: repo create, ahead/behind, PAT validate
app/frontend/src/components/
├── RemotePanel.tsx              # Self-fetching panel; contains GitHub/GitLab tabs
└── ui/
    └── tabs.tsx                 # shadcn Tabs (add via CLI)
```

### Pattern 1: GitHub OAuth Device Flow (Backend)

**What:** Two-step exchange — get device code, poll for access token.
**When to use:** GitHub connection initiation.

```python
# Source: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
import httpx, time

DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL       = "https://github.com/login/oauth/access_token"
CLIENT_ID       = "your_client_id_here"  # baked into app

def request_device_code() -> dict:
    """Step 1: Get device_code and user_code from GitHub."""
    resp = httpx.post(
        DEVICE_CODE_URL,
        data={"client_id": CLIENT_ID, "scope": "repo"},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()
    # Returns: {device_code, user_code, verification_uri, expires_in, interval}

def poll_for_token(device_code: str, interval: int) -> str | None:
    """Step 2: Poll until user authorizes or timeout. Returns access_token or None."""
    deadline = time.time() + 900  # expires_in default 900s
    while time.time() < deadline:
        time.sleep(interval)
        resp = httpx.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()
        if "access_token" in data:
            return data["access_token"]
        error = data.get("error")
        if error == "authorization_pending":
            continue  # keep waiting
        if error == "slow_down":
            interval += 5  # GitHub adds 5s penalty
        if error in ("expired_token", "access_denied"):
            return None  # terminal errors
    return None
```

**Polling error codes (HIGH confidence — official docs):**
| Code | Action |
|------|--------|
| `authorization_pending` | Continue polling at `interval` |
| `slow_down` | Add 5 seconds to `interval`, then continue |
| `expired_token` | Abort — request new codes |
| `access_denied` | Abort — user cancelled |
| `device_flow_disabled` | Abort — GitHub App needs device flow enabled in settings |

### Pattern 2: Remote Router — polling endpoint design

**What:** Frontend needs to initiate device flow and poll for result without holding a long HTTP connection.
**Approach:** Two-endpoint model:
1. `POST /api/remote/github/start` — returns `{user_code, verification_uri}` immediately; kicks off background polling via `asyncio.create_task`
2. `GET /api/remote/github/status` — returns `{state: "pending"|"connected"|"error"}` — frontend polls every 3s until connected

This avoids SSE complexity and matches the project's existing patterns.

```python
# Source: FastAPI background tasks pattern (Phases 11-15 established)
import asyncio
_poll_task: asyncio.Task | None = None  # module-level state

@router.post("/github/start")
async def start_github_auth() -> dict:
    global _poll_task
    data = remote_auth.request_device_code()
    _poll_task = asyncio.create_task(
        remote_auth.poll_and_store(data["device_code"], data["interval"])
    )
    return {
        "user_code": data["user_code"],
        "verification_uri": data["verification_uri"],
    }

@router.get("/github/status")
def get_github_status() -> dict:
    token = remote_auth.get_github_token()  # reads from keyring
    return {"connected": token is not None}
```

### Pattern 3: Credential Storage with keyring

**What:** Store/retrieve GitHub token and GitLab PAT in OS credential store.
**Critical:** Set keyring backend explicitly to fix PyInstaller bundling issue.

```python
# Source: https://pypi.org/project/keyring/ + https://github.com/jaraco/keyring/issues/324
import keyring
import sys

SERVICE_GITHUB = "AlteryxGitCompanion:github"
SERVICE_GITLAB = "AlteryxGitCompanion:gitlab"
USERNAME_KEY   = "token"  # single credential per service

def _ensure_backend() -> None:
    """Fix PyInstaller backend discovery — call once at module import."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: entry point discovery is broken; explicitly set backend
        if sys.platform == "win32":
            import keyring.backends.Windows
            keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
        elif sys.platform == "darwin":
            import keyring.backends.macOS
            keyring.set_keyring(keyring.backends.macOS.Keyring())

_ensure_backend()

def store_github_token(token: str) -> None:
    keyring.set_password(SERVICE_GITHUB, USERNAME_KEY, token)

def get_github_token() -> str | None:
    return keyring.get_password(SERVICE_GITHUB, USERNAME_KEY)

def store_gitlab_token(token: str) -> None:
    keyring.set_password(SERVICE_GITLAB, USERNAME_KEY, token)

def get_gitlab_token() -> str | None:
    return keyring.get_password(SERVICE_GITLAB, USERNAME_KEY)
```

### Pattern 4: git push with safe credential injection

**What:** Push local commits to remote without storing the token in `.git/config`.
**When to use:** Every push operation.

```python
# Source: https://blog.devops.dev/using-git-askpass-to-wire-in-token-authentication
# and https://git-scm.com/docs/gitcredentials
import subprocess, os, tempfile, stat

def git_push(folder: str, remote_url: str, token: str) -> None:
    """Push current branch to remote_url using GIT_ASKPASS token injection.

    Avoids storing token in .git/config or process command-line arguments.
    remote_url should be https (not token-embedded): https://github.com/owner/repo.git
    """
    # Write a tiny askpass helper script to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="acd_askpass_"
    ) as f:
        # Git calls askpass with prompt text; we always return the token
        f.write(f"#!/usr/bin/env python3\nimport sys\nprint('{token}')\n")
        askpass_path = f.name
    os.chmod(askpass_path, stat.S_IRWXU)  # executable for owner only

    try:
        env = os.environ.copy()
        env["GIT_ASKPASS"] = askpass_path
        env["GIT_TERMINAL_PROMPT"] = "0"  # disable interactive prompts

        # Set remote (overwrite if exists)
        subprocess.run(
            ["git", "-C", folder, "remote", "set-url", "--add", "--push", "origin", remote_url],
            capture_output=True, env=env,
        )
        # Ensure remote exists (add if not)
        r = subprocess.run(
            ["git", "-C", folder, "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "-C", folder, "remote", "add", "origin", remote_url],
                capture_output=True, check=True, env=env,
            )
        else:
            subprocess.run(
                ["git", "-C", folder, "remote", "set-url", "origin", remote_url],
                capture_output=True, check=True, env=env,
            )

        subprocess.run(
            ["git", "-C", folder, "push", "-u", "origin", "HEAD"],
            capture_output=True, text=True, check=True, env=env,
        )
    finally:
        os.unlink(askpass_path)  # cleanup temp file
```

**Note:** `git push -u origin HEAD` pushes the current branch (works for any branch name including `main` or `master`) and sets the upstream tracking reference.

### Pattern 5: GitHub REST API — repo creation and ahead/behind

```python
# Source: https://docs.github.com/en/rest/repos
import httpx

def create_github_repo(token: str, name: str) -> dict:
    """POST /user/repos — create private repo. Returns {clone_url, html_url, ...}."""
    resp = httpx.post(
        "https://api.github.com/user/repos",
        json={"name": name, "private": True, "auto_init": False},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    resp.raise_for_status()
    return resp.json()  # .clone_url is the HTTPS remote URL

def get_github_username(token: str) -> str:
    """GET /user — resolve owner name for constructing remote URLs."""
    resp = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    resp.raise_for_status()
    return resp.json()["login"]

def github_repo_exists(token: str, owner: str, repo_name: str) -> bool:
    """Check if repo exists before creating."""
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo_name}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    return resp.status_code == 200
```

### Pattern 6: GitLab REST API — PAT validation and repo creation

```python
# Source: https://docs.gitlab.com/api/rest/authentication/ and GitLab Projects API
import httpx

GITLAB_BASE = "https://gitlab.com/api/v4"  # configurable for self-hosted

def validate_gitlab_token(token: str) -> dict | None:
    """GET /user — returns user info or None if token is invalid."""
    resp = httpx.get(
        f"{GITLAB_BASE}/user",
        headers={"PRIVATE-TOKEN": token},
    )
    if resp.status_code == 200:
        return resp.json()  # .username
    return None

def create_gitlab_project(token: str, name: str) -> dict:
    """POST /projects — create private project. Returns {http_url_to_repo, ...}."""
    resp = httpx.post(
        f"{GITLAB_BASE}/projects",
        json={"name": name, "visibility": "private"},
        headers={"PRIVATE-TOKEN": token},
    )
    resp.raise_for_status()
    return resp.json()  # .http_url_to_repo is the HTTPS remote URL
```

### Pattern 7: Ahead/behind count (git-native)

```python
# Source: https://brandonrozek.com/blog/ahead-behind-git/
# Use git fetch first to update remote refs, then rev-list to count.

def git_fetch(folder: str, token: str, remote_url: str) -> None:
    """Fetch remote refs to update ahead/behind tracking info."""
    # Use same GIT_ASKPASS pattern as git_push for credential injection
    ...

def git_ahead_behind(folder: str) -> tuple[int, int]:
    """Return (ahead, behind) commit counts vs. origin/HEAD.

    Requires remote refs to be up to date (call git_fetch first).
    Returns (0, 0) if no remote tracking branch exists.
    """
    # Get current tracking branch
    r = subprocess.run(
        ["git", "-C", folder, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return (0, 0)  # no upstream set

    tracking = r.stdout.strip()  # e.g. "origin/main"

    ahead = subprocess.run(
        ["git", "-C", folder, "rev-list", "--count", f"{tracking}..HEAD"],
        capture_output=True, text=True,
    )
    behind = subprocess.run(
        ["git", "-C", folder, "rev-list", "--count", f"HEAD..{tracking}"],
        capture_output=True, text=True,
    )
    return (
        int(ahead.stdout.strip() or "0"),
        int(behind.stdout.strip() or "0"),
    )
```

### Pattern 8: RemotePanel (Frontend)

```typescript
// Source: SettingsPanel pattern (Phase 15-04) — self-fetching, no props
// shadcn Tabs: https://ui.shadcn.com/docs/components/radix/tabs
import { useState, useEffect } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

export function RemotePanel() {
  const [status, setStatus] = useState<RemoteStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/remote/status')
      .then(r => r.json())
      .then(d => { setStatus(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 text-sm text-muted-foreground">Loading...</div>

  return (
    <div className="p-6 space-y-6 max-w-md">
      <h2 className="text-lg font-semibold">Remote Backup</h2>
      <Tabs defaultValue="github">
        <TabsList>
          <TabsTrigger value="github">GitHub</TabsTrigger>
          <TabsTrigger value="gitlab">GitLab</TabsTrigger>
        </TabsList>
        <TabsContent value="github">
          {/* GitHub device flow UI */}
        </TabsContent>
        <TabsContent value="gitlab">
          {/* GitLab PAT UI */}
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

### Anti-Patterns to Avoid

- **Embedding token in remote URL:** `https://token@github.com/owner/repo.git` writes the token to `.git/config` in plaintext and leaks in process listings. Use `GIT_ASKPASS` instead.
- **Polling device flow synchronously in an HTTP handler:** The device flow can take up to 15 minutes. Start polling as an `asyncio.create_task` and return immediately; use a status endpoint.
- **Storing credentials in `config_store.py`:** `config_store` writes to disk in JSON — credentials MUST go through `keyring` only. CONTEXT.md explicitly forbids credentials via config_store.
- **Calling `keyring.get_password()` in a PyInstaller bundle without backend registration:** Will raise `RuntimeError: No recommended backend was available`. Call `_ensure_backend()` at module import time.
- **Using `git rev-list` for ahead/behind without fetching first:** Reports stale data based on last-fetched refs. Always `git fetch` before computing ahead/behind.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS credential store | Custom JSON/encrypted file | `keyring` 25.7 | Platform-specific encryption, DPAPI on Windows, Keychain on macOS — impossible to replicate safely |
| GitHub OAuth state machine | Custom polling + error handling | Pattern documented above from official docs | Exact error codes (`slow_down` +5s penalty, `authorization_pending` vs `expired_token`) are non-obvious |
| GitLab token validation | Custom regex / format check | `GET /api/v4/user` with token | Only real validation is a live API call; format checking gives false confidence |
| Repo slug generation | Complex Unicode normalization | Simple `re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')` | One-liner is sufficient for folder names; don't add `python-slugify` dependency |

**Key insight:** The credential storage problem looks simple (just save a string) but actually requires OS-level encryption that differs per platform. The `keyring` library abstracts this correctly; a custom solution would be plaintext or would reinvent DPAPI/Keychain integration.

---

## Common Pitfalls

### Pitfall 1: keyring PyInstaller backend discovery failure
**What goes wrong:** App bundles fine, but at runtime `keyring.get_password()` raises `RuntimeError: No recommended backend was available`. The app crashes silently on first credential access.
**Why it happens:** keyring switched to entry-point-based backend discovery in v12+. PyInstaller does not preserve entry point metadata files from `dist-info/` directories, so the auto-detection mechanism fails.
**How to avoid:** In `remote_auth.py`, call `_ensure_backend()` at module import time. Explicitly import and set the OS-appropriate backend when `sys.frozen` is True. Add `keyring.backends.Windows` and `keyring.backends.macOS` to `hiddenimports` in `app.spec`.
**Warning signs:** Works fine in dev (`uv run`), fails only in `.exe` / frozen build.

### Pitfall 2: Device flow `slow_down` error causes infinite fast loop
**What goes wrong:** Polling loop ignores `slow_down` error, retries immediately, triggering rate-limit loop.
**Why it happens:** `slow_down` means GitHub detected polling faster than `interval`; it adds 5 seconds to the required wait period. The spec says "continue polling" but at the *new increased interval*.
**How to avoid:** On `slow_down`, add 5 to the current `interval` value before sleeping. Maintain a mutable `interval` variable that can grow during the polling loop.
**Warning signs:** Rapid 429/error responses from GitHub during device flow polling.

### Pitfall 3: Token stored in git remote URL survives in `.git/config`
**What goes wrong:** After push, `cat .git/config` reveals the token in `[remote "origin"] url = https://token@github.com/...`. Token leaks if config file is shared or inspected.
**Why it happens:** The simplest "authenticated push" implementation embeds the token in the HTTPS remote URL.
**How to avoid:** Use `GIT_ASKPASS` helper pattern — set clean remote URL (`https://github.com/owner/repo.git`) and pass credentials only via environment variable. The temp askpass script is deleted after push.
**Warning signs:** `.git/config` shows `oauth2:` or a token in the remote URL after push.

### Pitfall 4: `git push` blocks event loop if called from async handler
**What goes wrong:** Push takes several seconds. Calling `subprocess.run()` from an `async def` FastAPI route blocks the entire uvicorn event loop during push, freezing all other requests.
**Why it happens:** `subprocess.run()` is synchronous. FastAPI `async def` routes run in the event loop — blocking calls freeze it.
**How to avoid:** Either: (a) define the push endpoint as `def` (not `async def`) — FastAPI runs sync routes in a threadpool automatically, OR (b) use `asyncio.to_thread(git_push, ...)` if async context is needed. Pattern (a) matches existing project routers.
**Warning signs:** UI freezes during push; other API calls time out during push.

### Pitfall 5: Ahead/behind count is stale without fetch
**What goes wrong:** `↑ 0 ahead · ↓ 0 behind` always, even after remote has new commits.
**Why it happens:** `git rev-list` counts based on *cached* remote refs. These only update on `git fetch`.
**How to avoid:** Always call `git fetch` (with credentials) before computing ahead/behind. The CONTEXT.md decision to refresh "on panel open and after each push" means fetch on both of those events.
**Warning signs:** Ahead/behind never updates despite pushes from another machine.

### Pitfall 6: asyncio.create_task called outside running event loop
**What goes wrong:** `RuntimeError: no running event loop` when starting device flow background task.
**Why it happens:** `asyncio.create_task()` requires a running loop. Must be called from within an `async def` handler, not from a sync context.
**How to avoid:** Device flow start endpoint must be `async def`. The polling coroutine uses `asyncio.sleep()`, not `time.sleep()`.
**Warning signs:** Device flow start endpoint crashes on first request.

---

## Code Examples

### Repo name slugification

```python
# Source: inline — no external dependency needed
import re

def slugify_folder_name(name: str) -> str:
    """Convert folder name to valid GitHub/GitLab repo slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    return slug.strip('-') or 'my-workflows'
```

### Name collision resolution

```python
def find_available_repo_name(token: str, owner: str, base_slug: str) -> str:
    """Find a non-colliding repo name by appending suffix if needed."""
    candidate = base_slug
    suffix = 2
    while github_repo_exists(token, owner, candidate):
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate
```

### GitLab PAT validation (minimal call)

```python
# Source: https://docs.gitlab.com/api/rest/authentication/
def validate_and_store_gitlab_token(token: str) -> bool:
    """Validate token via GET /user, store in keyring if valid."""
    user = validate_gitlab_token(token)
    if user:
        store_gitlab_token(token)
        return True
    return False
```

### app.spec hiddenimports additions for keyring

```python
# Add to hiddenimports list in app.spec:
# Source: https://github.com/jaraco/keyring/issues/324
'keyring',
'keyring.backends',
'keyring.backends.Windows',
'keyring.backends.macOS',
'keyring.credentials',
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitHub PAT (password field) | GitHub OAuth Device Flow | GitHub deprecated password auth 2021 | Device flow is the required no-browser flow for desktop apps |
| Plaintext credential files | OS keyring (keyring lib) | Security standard for desktop apps | keyring v25 is the Python standard; entry-point discovery requires PyInstaller workaround |
| `git push` with embedded URL token | `GIT_ASKPASS` credential injection | Security best practice | Prevents token leaking into `.git/config` |
| `requests` library | `httpx` | FastAPI ecosystem shift ~2022 | `httpx` is async-native; matches FastAPI's async architecture |

**Deprecated/outdated:**
- GitHub password auth over HTTPS: removed August 2021 — do not offer as fallback
- `keyrings.alt`: flatfile/plaintext alternative backend — must NOT be installed or used; defeats the security guarantee

---

## Open Questions

1. **GitHub OAuth App `client_id`**
   - What we know: Must be registered at GitHub → Settings → Developer settings → OAuth Apps; `client_id` is baked into the app binary
   - What's unclear: Whether the project owner has already registered this OAuth App; whether `client_id` should be in a constants file or an environment variable at build time
   - Recommendation: Planner should include a task for "Register GitHub OAuth App" with a note that `client_id` must be set before the plan executes; use a constant in `remote_auth.py` with a `TODO: replace with registered client_id` comment

2. **GitLab self-hosted support**
   - What we know: `CONTEXT.md` says GitLab PAT — doesn't specify gitlab.com vs. self-hosted
   - What's unclear: Does Phase 16 target only gitlab.com, or also self-hosted instances?
   - Recommendation: Default to `gitlab.com`; make base URL a constant in `gitlab_api.py` that can be overridden. The planner can default to gitlab.com for v1 without hardcoding constraints.

3. **Per-project remote repo mapping storage**
   - What we know: "Each project folder maps to its own remote repo" — requires storing the repo URL alongside the project record
   - What's unclear: Where to store `{project_id: remote_url}` — `config_store.py` (non-credential metadata is fine there) or a separate file
   - Recommendation: Add a `remote_repos` dict to `config_store`'s config JSON: `{"remote_repos": {"proj-id": {"github_url": "...", "gitlab_url": "..."}}}`. Credentials stay in keyring; URLs are non-sensitive metadata.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_remote.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REMOTE-01 | GitHub device flow: `request_device_code()` returns `user_code` and `device_code` | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_request_device_code -x` | ❌ Wave 0 |
| REMOTE-01 | Polling loop: `authorization_pending` continues, `access_denied` aborts | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_poll_authorization_pending -x` | ❌ Wave 0 |
| REMOTE-01 | Polling loop: `slow_down` adds 5s to interval | unit (mock httpx, mock sleep) | `uv run pytest tests/test_remote.py::test_poll_slow_down_increases_interval -x` | ❌ Wave 0 |
| REMOTE-01 | `POST /api/remote/github/start` returns `{user_code, verification_uri}` | integration (TestClient) | `uv run pytest tests/test_remote.py::test_post_github_start -x` | ❌ Wave 0 |
| REMOTE-01 | `GET /api/remote/github/status` returns `{connected: True}` after token stored | integration (TestClient + mock keyring) | `uv run pytest tests/test_remote.py::test_get_github_status_connected -x` | ❌ Wave 0 |
| REMOTE-02 | GitLab PAT validation: valid token returns user dict | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_validate_gitlab_token_valid -x` | ❌ Wave 0 |
| REMOTE-02 | GitLab PAT validation: invalid token returns None | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_validate_gitlab_token_invalid -x` | ❌ Wave 0 |
| REMOTE-02 | `POST /api/remote/gitlab/connect` stores token on valid PAT | integration (TestClient + mock keyring) | `uv run pytest tests/test_remote.py::test_post_gitlab_connect_valid -x` | ❌ Wave 0 |
| REMOTE-03 | `store_github_token` / `get_github_token` use keyring service name | unit (mock keyring) | `uv run pytest tests/test_remote.py::test_store_and_get_github_token -x` | ❌ Wave 0 |
| REMOTE-03 | No credential stored in config_store / no plaintext on disk | unit (assert keyring called, config_store not called) | `uv run pytest tests/test_remote.py::test_credentials_not_in_config_store -x` | ❌ Wave 0 |
| REMOTE-04 | `git_push` sets remote URL and pushes via subprocess | unit (mock subprocess) | `uv run pytest tests/test_remote.py::test_git_push_calls_subprocess -x` | ❌ Wave 0 |
| REMOTE-04 | `git_push` uses GIT_ASKPASS env var, not token in URL | unit (capture env passed to subprocess) | `uv run pytest tests/test_remote.py::test_git_push_uses_askpass_not_url_token -x` | ❌ Wave 0 |
| REMOTE-04 | `POST /api/remote/push` returns 200 on successful push | integration (TestClient + mock git_push) | `uv run pytest tests/test_remote.py::test_post_push_success -x` | ❌ Wave 0 |
| REMOTE-05 | `create_github_repo` calls `POST /user/repos` with `private: true` | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_create_github_repo_private -x` | ❌ Wave 0 |
| REMOTE-05 | Name collision: `find_available_repo_name` appends `-2` suffix | unit (mock github_repo_exists) | `uv run pytest tests/test_remote.py::test_find_available_repo_name_collision -x` | ❌ Wave 0 |
| REMOTE-05 | `create_gitlab_project` calls `POST /projects` with `visibility: private` | unit (mock httpx) | `uv run pytest tests/test_remote.py::test_create_gitlab_project_private -x` | ❌ Wave 0 |
| REMOTE-06 | `git_ahead_behind` returns `(ahead, behind)` tuple from `rev-list --count` output | unit (mock subprocess) | `uv run pytest tests/test_remote.py::test_git_ahead_behind -x` | ❌ Wave 0 |
| REMOTE-06 | `git_ahead_behind` returns `(0, 0)` when no upstream set | unit (mock subprocess returncode=1) | `uv run pytest tests/test_remote.py::test_git_ahead_behind_no_upstream -x` | ❌ Wave 0 |
| REMOTE-06 | `GET /api/remote/status` returns `ahead` and `behind` fields | integration (TestClient + mock git ops) | `uv run pytest tests/test_remote.py::test_get_remote_status_ahead_behind -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_remote.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_remote.py` — covers all REMOTE-01 through REMOTE-06 tests (entire file is new)
- [ ] `app/routers/remote.py` — router stub (empty module) needed before test imports can succeed
- [ ] `app/services/remote_auth.py` — service stub needed for graceful RED pattern
- [ ] `app/services/github_api.py` — service stub needed
- [ ] `app/services/gitlab_api.py` — service stub needed

---

## Sources

### Primary (HIGH confidence)
- [GitHub OAuth Device Flow official docs](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps) — device flow endpoints, polling error codes, response format
- [keyring PyPI page](https://pypi.org/project/keyring/) — version 25.7.0, API (set_password, get_password, delete_password), platform support
- [shadcn Tabs docs](https://ui.shadcn.com/docs/components/radix/tabs) — import, component structure, installation command

### Secondary (MEDIUM confidence)
- [GitLab REST API auth docs](https://docs.gitlab.com/api/rest/authentication/) — PRIVATE-TOKEN header format, Bearer alternative
- [GitLab Projects API](https://docs.gitlab.com/api/projects/) — POST /projects with visibility=private pattern (verified via DZone article + official docs structure)
- [GitHub jaraco/keyring issue #324](https://github.com/jaraco/keyring/issues/324) — confirmed PyInstaller fix: explicit backend import + set_keyring
- [GIT_ASKPASS pattern article](https://blog.devops.dev/using-git-askpass-to-wire-in-token-authentication-minimal-changes-maximum-ease-609d007dfdad) — credential injection via env variable
- [git ahead/behind via rev-list](https://brandonrozek.com/blog/ahead-behind-git/) — `git rev-list --count A..B` pattern

### Tertiary (LOW confidence — flag for validation)
- GitHub OAuth App registration flow details — validated against GitHub docs structure but full registration UI walkthrough not verified

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — keyring 25.7 confirmed from PyPI; shadcn Tabs confirmed from official docs; httpx is well-established FastAPI ecosystem library
- GitHub Device Flow: HIGH — endpoints, error codes, and polling mechanics confirmed from official GitHub docs
- GitLab PAT auth: HIGH — PRIVATE-TOKEN header confirmed from official GitLab docs; POST /projects visibility=private confirmed from multiple sources
- keyring PyInstaller fix: HIGH — explicit backend registration workaround confirmed from jaraco/keyring issue tracker with working solution
- GIT_ASKPASS credential injection: MEDIUM — pattern confirmed from multiple sources; project-specific temp file approach needs validation in Windows PyInstaller context
- Architecture patterns: HIGH — follows established Phase 11–15 patterns verified in codebase

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (GitHub/GitLab APIs are stable; keyring version may update but API is stable)
