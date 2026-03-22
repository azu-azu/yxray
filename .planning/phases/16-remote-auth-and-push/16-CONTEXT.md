# Phase 16: Remote Auth and Push - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can authenticate with GitHub (OAuth device flow + PAT fallback) or GitLab (PAT), back up saved versions to a remote with a single button, auto-create the remote repo on first push (private, no manual GitHub/GitLab visit needed), and see an ahead/behind indicator in the Remote panel. Branch management, pull, and conflict resolution are separate phases.

</domain>

<decisions>
## Implementation Decisions

### GitHub OAuth mechanism
- Device flow (OAuth Device Authorization Grant): app shows a code + `github.com/login/device` URL; user opens browser, enters code, clicks Authorize
- PAT fallback also supported — for environments where device flow is blocked, user can paste a personal access token manually
- Scopes: `repo` only (create and push to private repos; minimal footprint)
- After successful connect: green "Connected" status badge shown inline in the Remote panel; no username display needed in v1
- GitHub OAuth App must be registered (client_id baked into the app)

### GitLab auth
- PAT only (no OAuth for GitLab in this phase) — consistent with REMOTE-02 requirement
- Inline step-by-step instructions in the GitLab tab of the Remote panel: numbered steps + "Open GitLab Settings" button linking directly to the token settings page
- User pastes PAT into an input field; app validates and stores it

### Credential storage
- OS credential store via `keyring` (Windows Credential Manager / macOS Keychain)
- Never stored in plaintext on disk
- Global credentials: user connects one GitHub account and/or one GitLab account — applies to all projects

### Remote connection UI
- New "Remote" panel added to the sidebar nav (cloud icon), between History and Settings
- Remote panel has two tabs: **GitHub** | **GitLab** — each tab handles its own connection flow independently
- Global credentials + per-project repo: one GitHub/GitLab login covers all projects; each project folder maps to its own remote repo
- AppShell `activeView` state gains a new `'remote'` branch — consistent with Phase 15 `'settings'` pattern

### Auto-repo creation on first push
- Repo name: folder name slugified (e.g., "My Workflows" → `my-workflows`)
- Always private — no user choice; workflow files are business logic
- Brief inline confirmation before creating: "No remote repo found. We'll create **my-workflows** (private) on GitHub." with a [Push and Create Repo] button — transparent, no surprise creation
- Name collision: auto-append suffix (`my-workflows-2`, `my-workflows-3`, etc.); shown in confirmation notice

### Ahead/behind indicator
- Displayed in the Remote panel (active tab), above the Push button: `↑ 3 ahead · ↓ 0 behind`
- Refreshes on two events only: when user opens the Remote panel, and after each push — no background polling
- When remote is not connected: empty state with CTA copy ("Back up your workflows. Connect GitHub or GitLab to push saved versions to the cloud.") + [Connect GitHub] and [Connect GitLab] buttons

### Claude's Discretion
- Exact copy/phrasing for GitLab PAT step-by-step instructions
- Loading/spinner states during OAuth polling and push operations
- Error message copy for push failures (network error, auth expired, etc.)
- How to surface push progress for large repos (progress indicator vs. simple spinner)

</decisions>

<specifics>
## Specific Ideas

- Device flow UX should feel self-contained in the app — show the code inline with a [Copy Code] button and a [Open github.com/login/device] button so user never has to manually type a URL
- The PAT fallback for GitHub should be a secondary "Use a token instead" link below the device flow — not the primary path
- GitLab instructions: numbered 1-2-3 steps, not a wall of text

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/frontend/src/components/AppShell.tsx`: `activeView` state — add `'remote'` alongside `'default'`, `'history'`, `'settings'`; `renderMainContent()` gains a `RemotePanel` branch
- `app/frontend/src/components/Sidebar.tsx`: sidebar nav pattern — add Remote cloud icon between History and Settings; follows existing icon-nav structure
- `app/frontend/src/components/SettingsPanel.tsx`: self-fetching panel pattern — `RemotePanel` should follow same pattern (fetches `/api/remote/status` on mount)
- `app/services/git_ops.py`: `git_push` will be a new function here alongside existing git operations
- `app/routers/` pattern: new `remote.py` router for all `/api/remote/*` endpoints; module-level service import for `unittest.mock.patch` compatibility

### Established Patterns
- shadcn/ui + Tailwind for all UI — `Tabs` component available in shadcn for the GitHub/GitLab tab switcher
- Self-fetching panels (SettingsPanel) — RemotePanel fetches its own state on mount
- Module-level imports in routers for mock.patch (Phases 11–15)
- AppShell owns view switching; panels are self-contained
- `app/services/config_store.py`: existing config storage — credential storage goes through `keyring`, NOT config_store (credentials must not hit disk)

### Integration Points
- `app/server.py`: register `remote.router` after `settings.router`
- `app/services/git_ops.py`: add `git_push(project_path, remote_url)` function
- New `app/services/remote_auth.py`: handles GitHub device flow polling, PAT validation, GitLab PAT, and `keyring` read/write
- New `app/services/github_api.py` or similar: GitHub REST API calls for repo creation and ahead/behind count via `GET /repos/{owner}/{repo}` and `git rev-list` count

</code_context>

<deferred>
## Deferred Ideas

- Pull / sync from remote — own phase (would require conflict UX)
- Disconnect / revoke token flow — could be added as a small follow-up in Phase 16 or Phase 17 if time allows; noted for consideration
- Multiple GitHub accounts — not needed for target persona (one analyst, one GitHub account)

</deferred>

---

*Phase: 16-remote-auth-and-push*
*Context gathered: 2026-03-14*
