---
phase: 11-onboarding-and-project-management
verified: 2026-03-14T00:00:00Z
status: human_needed
score: 14/14 must-haves verified
re_verification: false
human_verification:
  - test: "First-run: open app with no config.json — confirm WelcomeScreen renders (not AppShell)"
    expected: "Centered card with Alteryx Git Companion title, 4 feature bullets, and 'Add Your First Folder' button"
    why_human: "Conditional rendering based on network response — automated checks confirm logic is correct but can't run the live app"
  - test: "Click 'Add Your First Folder' on WelcomeScreen — OS folder picker must appear"
    expected: "Native OS folder selection dialog opens"
    why_human: "Requires live app with tkinter subprocess; automated verification confirmed the subprocess pattern exists but cannot trigger the dialog"
  - test: "Select a folder with NO .git directory — confirm pre-confirmation dialog appears BEFORE any git operation"
    expected: "AlertDialog 'Set up version control?' with Cancel and Set Up buttons. Clicking Cancel returns to WelcomeScreen with zero side effects."
    why_human: "UI dialog timing and cancel abort path require live interaction; human confirmed this in Plan 05 but this verification documents the requirement"
  - test: "Select a folder that already has git history — confirm project is added silently"
    expected: "No dialog of any kind. Project immediately appears in sidebar. App transitions to AppShell."
    why_human: "Requires live environment with an actual git repo folder"
  - test: "After adding a folder when git user.name/email not configured — GitIdentityCard appears in main content"
    expected: "Inline card titled 'Almost done' with Name + Email inputs and Save button. Filling in and saving dismisses the card and shows EmptyState."
    why_human: "Depends on live git config state on the test machine"
  - test: "Sidebar multi-project: add two projects, switch between them, remove one via right-click"
    expected: "Both basenames appear in sidebar. Click switches active (highlighted). Right-click shows 'Remove project'. Confirm removes from list; files untouched on disk."
    why_human: "Requires live UI interaction for ContextMenu and AlertDialog confirm"
---

# Phase 11: Onboarding and Project Management — Verification Report

**Phase Goal:** Implement onboarding and project management — WelcomeScreen for first-run, pre-confirmation git-init dialog, git identity prompt, multi-project sidebar with add/remove.
**Verified:** 2026-03-14
**Status:** human_needed — all automated checks pass; 6 UX behaviors require human confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WelcomeScreen renders when projects list is empty | VERIFIED | App.tsx: `projects.length === 0 ? <WelcomeScreen ...> : <AppShell ...>` with fetch-on-mount hydration |
| 2 | AppShell (sidebar + main) renders when projects exist | VERIFIED | Same conditional; `isLoading` guard prevents flash |
| 3 | OS native folder picker is invoked via backend | VERIFIED | App.tsx `handleAddFolder` calls `POST /api/folder-picker`; folder_picker.py uses subprocess to spawn tkinter in isolated process |
| 4 | Pre-confirmation dialog appears for non-git folders BEFORE any git operation | VERIFIED | App.tsx: GET /api/projects/check → if `!is_git_repo` sets `showGitInitConfirm=true` and returns; `doAddProject` only called after user clicks Set Up or folder is already a git repo |
| 5 | Git repos are added silently (no dialog) | VERIFIED | App.tsx: `if (!is_git_repo) { setPendingPath; setShowGitInitConfirm(true); return }` — else branch calls `doAddProject` immediately |
| 6 | GitIdentityCard appears after project add when name/email missing | VERIFIED | `doAddProject` calls `GET /api/git/identity`; `if (!identity.name \|\| !identity.email) setShowIdentityCard(true)` |
| 7 | GitIdentityCard dismisses and EmptyState appears after Save | VERIFIED | `onIdentitySaved={() => setShowIdentityCard(false)}` passed to AppShell; AppShell shows GitIdentityCard only when `showIdentityCard && onIdentitySaved` |
| 8 | Sidebar lists all registered projects by basename | VERIFIED | Sidebar.tsx maps over `projects` from Zustand store, renders `{project.name}` (basename field, not path) |
| 9 | Clicking sidebar project sets it as active with visual highlight | VERIFIED | `onClick={() => setActiveProject(project.id)}`; `activeProjectId === project.id && 'bg-accent font-medium'` conditional class |
| 10 | Right-click context menu with Remove project + confirmation | VERIFIED | Sidebar.tsx wraps each project in `ContextMenu`; confirmation AlertDialog with reassuring copy; calls DELETE /api/projects/{id} then `removeProject(id)` |
| 11 | All 10 backend tests GREEN | VERIFIED | `pytest tests/test_projects.py tests/test_git_identity.py` — 10 passed, 0 failed |
| 12 | Full backend test suite has no regressions | VERIFIED | `pytest tests/ -q` (excluding pre-existing test_port_probe failure from Phase 10) — 119 passed, 1 xfailed |
| 13 | TypeScript compiles with 0 errors | VERIFIED | `npx tsc --noEmit` exits 0 with no output |
| 14 | Frontend builds successfully | VERIFIED | `npm run build` — 1820 modules transformed, dist output produced |

**Score:** 14/14 truths verified (automated)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/config_store.py` | load_config/save_config using platformdirs + JSON | VERIFIED | Fully implemented; `_config_path()` uses `platformdirs.user_data_dir`; both functions complete |
| `app/services/git_ops.py` | is_git_repo/git_init/get_git_identity/set_git_identity via subprocess | VERIFIED | All 4 functions implemented; `check=False` for optional git config reads |
| `app/routers/projects.py` | GET/POST/DELETE + GET /check — validation, git init logic, uuid IDs | VERIFIED | `/check` defined before `/{project_id}`; 400/409/404 error handling; no `git_initialized` field |
| `app/routers/git_identity.py` | GET/POST /api/git/identity | VERIFIED | Module-level import pattern (`import app.services.git_ops as git_ops_svc`) for correct mock patching |
| `app/routers/folder_picker.py` | POST /api/folder-picker via subprocess (tkinter isolation) | VERIFIED | Subprocess pattern used to spawn tkinter in isolated process — avoids macOS main-thread restriction |
| `app/server.py` | include_router for all 3 routers before SPAStaticFiles | VERIFIED | `app.include_router` called for projects, git_identity, folder_picker before SPA mount |
| `app/frontend/src/store/useProjectStore.ts` | Zustand store with isLoading, all CRUD actions | VERIFIED | `isLoading: true` initial state; all 4 actions (setProjects, setActiveProject, addProject, removeProject) |
| `app/frontend/src/components/WelcomeScreen.tsx` | Centered card with 4 bullets and CTA button | VERIFIED | FolderOpen icon, 4 feature bullets, "Add Your First Folder" button calling `onAddFolder` prop |
| `app/frontend/src/components/AppShell.tsx` | 220px sidebar + main content; passes showIdentityCard to GitIdentityCard | VERIFIED | `w-[220px] flex-shrink-0` sidebar; renders GitIdentityCard or EmptyState based on `showIdentityCard` |
| `app/frontend/src/components/Sidebar.tsx` | Project list, Plus button, ContextMenu, AlertDialog remove | VERIFIED | All elements present and wired |
| `app/frontend/src/components/EmptyState.tsx` | Guidance card with optional projectName | VERIFIED | "No saved versions yet" title; conditional `for {projectName}` in description |
| `app/frontend/src/components/GitIdentityCard.tsx` | Inline card with Name + Email + Save → POST /api/git/identity | VERIFIED | Fields, validation, fetch to /api/git/identity, onSaved() callback |
| `app/frontend/src/App.tsx` | fetch-on-mount, conditional render, full pre-confirmation add-folder flow | VERIFIED | Complete implementation with all 3 state variables (showIdentityCard, showGitInitConfirm, pendingPath) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/server.py` | `app/routers/projects.py` | `app.include_router(projects.router)` | WIRED | Line 21; pattern `include_router.*projects` confirmed |
| `app/server.py` | `app/routers/git_identity.py` | `app.include_router(git_identity.router)` | WIRED | Line 22 |
| `app/server.py` | `app/routers/folder_picker.py` | `app.include_router(folder_picker.router)` | WIRED | Line 23 |
| `app/routers/projects.py` | `app/services/config_store.py` | `config_store.load_config()` / `config_store.save_config()` | WIRED | Module import `from app.services import config_store, git_ops`; calls on lines 34, 45, 52, 60, 64, 67 |
| `app/routers/projects.py` | `app/services/git_ops.py` | `git_ops.is_git_repo()` / `git_ops.git_init()` | WIRED | Lines 28, 48, 49 |
| `app/routers/git_identity.py` | `app/services/git_ops.py` | `git_ops_svc.get_git_identity()` / `set_git_identity()` | WIRED | Module alias import; used in both GET and POST handlers |
| `app/frontend/src/App.tsx` | `/api/projects` | `fetch('/api/projects')` on mount | WIRED | `useEffect` hydrates Zustand store on mount |
| `app/frontend/src/App.tsx` | `/api/projects/check` | `fetch('/api/projects/check?path=...')` in handleAddFolder | WIRED | Step 2 of handleAddFolder pre-flight check |
| `app/frontend/src/App.tsx` | `/api/folder-picker` | `fetch('/api/folder-picker', { method: 'POST' })` | WIRED | Step 1 of handleAddFolder |
| `app/frontend/src/App.tsx` | `/api/git/identity` | `fetch('/api/git/identity')` in doAddProject | WIRED | Identity check after project add |
| `app/frontend/src/App.tsx` | `useProjectStore` | `useProjectStore()` hook | WIRED | Imports and uses projects, isLoading, setProjects, addProject, setActiveProject |
| `app/frontend/src/components/Sidebar.tsx` | `useProjectStore` | `useProjectStore()` for setActiveProject, removeProject | WIRED | Uses all 4 destructured values |
| `app/frontend/src/components/Sidebar.tsx` | `/api/projects/{id}` | `fetch('/api/projects/${id}', { method: 'DELETE' })` | WIRED | handleRemoveConfirm; best-effort with store update regardless |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ONBOARD-01 | 11-01, 11-02, 11-03, 11-04, 11-05 | User sees a first-run welcome screen explaining what the app does before any setup | SATISFIED | WelcomeScreen.tsx: centered card with app name, tagline, 4 feature bullets, CTA. App.tsx: `projects.length === 0 ? <WelcomeScreen>` |
| ONBOARD-02 | 11-01, 11-02, 11-03, 11-04, 11-05 | User can add a project folder; app auto-initializes git if folder is not already a repo | SATISFIED | App.tsx handleAddFolder: GET /check → AlertDialog confirmation if not git → POST /api/projects → backend calls git_init when is_git_repo=False |
| ONBOARD-03 | 11-01, 11-02, 11-03, 11-04, 11-05 | App detects missing git user identity and prompts for it on first use | SATISFIED | doAddProject: GET /api/git/identity → setShowIdentityCard if name/email null. GitIdentityCard calls POST /api/git/identity. get_git_identity uses check=False for non-error exit 1 |
| ONBOARD-04 | 11-01, 11-02, 11-03, 11-04, 11-05 | User can register and switch between multiple project folders from a left-panel project list | SATISFIED | Sidebar.tsx: maps projects from Zustand store, active highlight, onClick setActiveProject, right-click ContextMenu, AlertDialog remove confirmation, DELETE API call |

All 4 requirements claimed in REQUIREMENTS.md as "Phase 11 / Complete" are satisfied by verified code.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/frontend/src/App.tsx` | 74 | `// TODO: surface error toast in Phase 12` | Info | Deferred UX improvement — error on `POST /api/projects` silently aborts; no blocker for current phase goal |

No other stubs, placeholders, or unimplemented handlers found across all 13 verified files.

**Notable deviation (not a defect):** `folder_picker.py` uses subprocess to spawn tkinter in an isolated Python process rather than `asyncio.to_thread` as specified in Plan 02. This is a superior implementation that avoids the macOS main-thread UI restriction — it was intentionally introduced in commit `c47417a` with a fix note.

---

## Human Verification Required

The automated checks confirm all implementation logic is correct. The following 6 items require live-app verification to confirm the end-to-end UX works as intended:

### 1. WelcomeScreen First-Run

**Test:** Delete `~/Library/Application Support/AlteryxGitCompanion/config.json` (macOS), start the server, visit http://localhost:7433
**Expected:** WelcomeScreen renders — centered card with "Alteryx Git Companion" title, 4 feature bullets, "Add Your First Folder" button
**Why human:** Conditional rendering depends on live fetch response; automated code review confirms the logic is correct

### 2. Folder Picker Opens

**Test:** Click "Add Your First Folder" on WelcomeScreen
**Expected:** Native OS folder selection dialog opens
**Why human:** Requires live tkinter subprocess — cannot trigger in automated verification

### 3. Pre-Confirmation Dialog for Non-Git Folder

**Test:** Select a folder with no .git directory
**Expected:** AlertDialog appears: "Set up version control?" with Cancel and Set Up buttons. Clicking Cancel returns to WelcomeScreen with no side effects (no git init ran, no project added).
**Why human:** Requires live UI interaction to verify dialog timing and abort behavior

### 4. Silent Add for Git Repo

**Test:** Click the '+' button in the sidebar, select a folder that already has .git history
**Expected:** Project is added immediately to sidebar — no dialog of any kind appears
**Why human:** Requires a live git repo folder and live UI

### 5. GitIdentityCard Flow

**Test:** Add a folder on a machine with no global git user.name/email configured
**Expected:** "Almost done" card appears in main content area. Filling Name + Email and clicking Save dismisses the card and shows "No saved versions yet" EmptyState.
**Why human:** Depends on git config state on the specific machine; hard to reproduce in automated test without modifying global git config

### 6. Multi-Project Sidebar: Switch and Remove

**Test:** Add two projects. Click between them in sidebar. Right-click one, select "Remove project", confirm in dialog.
**Expected:** Active project highlights on click. Right-click shows context menu. Confirmation dialog: "Remove {name}?" with reassuring copy. After confirm: project disappears from sidebar; files on disk untouched.
**Why human:** ContextMenu and AlertDialog interactions require browser-based testing

---

## Summary

Phase 11 is fully implemented across all 5 plans. All 13 artifacts are substantive and correctly wired. All 10 backend tests pass GREEN. TypeScript compiles with 0 errors. Frontend builds successfully. All 4 ONBOARD requirements (ONBOARD-01 through ONBOARD-04) have verifiable implementation evidence.

The one automated test suite failure (`test_port_probe.py::test_find_available_port_returns_7433`) is pre-existing from Phase 10 — port 7433 is occupied by a running process at test time; this is an environment issue, not a Phase 11 regression.

The TODO in App.tsx line 74 ("surface error toast in Phase 12") is correctly scoped deferred work — it covers the error state of POST /api/projects which is not a Phase 11 deliverable.

**The phase goal is achieved.** All automated checks pass. Human verification of the UX flows (documented above) is the only remaining step before final sign-off.

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
