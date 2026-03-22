# Roadmap: Alteryx Canvas Diff (ACD)

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (shipped 2026-03-07)
- 🚧 **v1.1 Alteryx Git Companion** — Phases 10-18 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) — SHIPPED 2026-03-07</summary>

- [x] Phase 1: Scaffold and Data Models (3/3 plans) — completed 2026-03-01
- [x] Phase 2: XML Parser and Validation (2/2 plans) — completed 2026-03-01
- [x] Phase 3: Normalization Layer (4/4 plans) — completed 2026-03-02
- [x] Phase 4: Node Matcher (3/3 plans) — completed 2026-03-02
- [x] Phase 5: Diff Engine (3/3 plans) — completed 2026-03-06
- [x] Phase 6: Pipeline Orchestration and JSON Renderer (3/3 plans) — completed 2026-03-06
- [x] Phase 7: HTML Report (2/2 plans) — completed 2026-03-06
- [x] Phase 8: Visual Graph (3/3 plans) — completed 2026-03-07
- [x] Phase 9: CLI Entry Point (3/3 plans) — completed 2026-03-07

Full phase details: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 🚧 v1.1 Alteryx Git Companion (In Progress)

**Milestone Goal:** Make Git-based version control accessible to non-technical Alteryx analysts via a desktop companion app (local web server, system tray, auto-start) and polished CI integration.

## Phase Details

### Phase 10: App Scaffold
**Goal**: A distributable Windows .exe launches a local web server and opens the app UI in a browser with reliable port handling
**Depends on**: Phase 9 (acd CLI bundled as dependency)
**Requirements**: APP-01, APP-03, APP-04
**Success Criteria** (what must be TRUE):
  1. User installs the app on a Windows machine without installing Python — the .exe runs standalone
  2. App starts a local web server on port 7433 and automatically tries 7434–7443 if that port is already in use
  3. Opening the app launches a browser tab at the correct localhost:PORT URL
  4. acd diff CLI is bundled inside the .exe and accessible to the FastAPI backend at runtime
**Plans**: 3 plans

Plans:
- [ ] 10-01-PLAN.md — FastAPI backend + port probe + entry point + unit tests
- [ ] 10-02-PLAN.md — React + Vite + shadcn/ui frontend scaffold + Makefile
- [ ] 10-03-PLAN.md — PyInstaller spec + version_info + icon + GitHub Actions release CI

### Phase 11: Onboarding and Project Management
**Goal**: New users are guided through first-run setup and can register and switch between multiple workflow project folders
**Depends on**: Phase 10
**Requirements**: ONBOARD-01, ONBOARD-02, ONBOARD-03, ONBOARD-04
**Success Criteria** (what must be TRUE):
  1. First-time user sees a welcome screen explaining what the app does before any setup step is required
  2. User can add a workflows folder — app auto-runs git init if the folder has no git history
  3. App detects missing git user.name / git user.email and prompts the user to enter their name and email before the first save
  4. User can register multiple project folders and switch between them from a left-panel project list
**Plans**: 5 plans

Plans:
- [ ] 11-01-PLAN.md — Install deps + backend/test scaffolding + frontend shadcn/zustand setup (Wave 1)
- [ ] 11-02-PLAN.md — Backend: config_store, git_ops, all 3 routers implemented + tests GREEN (Wave 2)
- [ ] 11-03-PLAN.md — Frontend: Zustand store, AppShell, Sidebar, WelcomeScreen, EmptyState (Wave 2, parallel)
- [ ] 11-04-PLAN.md — Wiring: register routers in server.py, GitIdentityCard, folder picker flow (Wave 3)
- [ ] 11-05-PLAN.md — Human verification checkpoint: full onboarding flow end-to-end (Wave 4)

### Phase 12: File Watcher
**Goal**: The app continuously monitors registered folders and surfaces detected changes with appropriate warnings
**Depends on**: Phase 11
**Requirements**: WATCH-01, WATCH-02, WATCH-03
**Success Criteria** (what must be TRUE):
  1. App detects when a .yxmd or .yxwz file in a registered folder is modified and shows a change badge in the UI
  2. App automatically uses polling (5-second interval) for network/SMB/UNC paths and native OS file events for local drives — no manual configuration required
  3. When a user is about to save their first version in a folder that already contains workflows, the app warns them how many files will be captured in the initial commit
**Plans**: 5 plans

Plans:
- [ ] 12-01-PLAN.md — Test scaffold (Wave 0) + git_ops helpers (git_changed_workflows, count_workflows, git_has_commits) + watcher_utils (is_network_path) (Wave 1)
- [ ] 12-02-PLAN.md — WatcherManager singleton: watchdog lifecycle, debounce, git rescan, SSE push (Wave 2)
- [ ] 12-03-PLAN.md — watch router (/api/watch/events SSE, /api/watch/status) + server.py lifespan + projects.py wiring (Wave 3)
- [ ] 12-04-PLAN.md — Frontend: Zustand setChangedCount, useWatchEvents hook, Sidebar amber badge (Wave 4)
- [ ] 12-05-PLAN.md — Human verification checkpoint: live badge, /api/watch/status, observer selection (Wave 5)

### Phase 13: Save Version
**Goal**: Users can intentionally save a named version of changed workflows, undo the last save, and safely discard uncommitted changes
**Depends on**: Phase 12
**Requirements**: SAVE-01, SAVE-02, SAVE-03
**Success Criteria** (what must be TRUE):
  1. User can select which changed workflows to include, write a commit message with placeholder guidance, and save a version with one button
  2. User can undo the last saved version with one click — a confirmation dialog explains that file contents are preserved and only the version record is removed
  3. Discarding uncommitted changes moves the affected files to a .acd-backup folder rather than permanently deleting them
**Plans**: 4 plans

Plans:
- [ ] 13-01-PLAN.md — Wave 0: test scaffold + shadcn Checkbox/Textarea install
- [ ] 13-02-PLAN.md — Backend: git_commit_files, git_undo_last_commit, git_discard_files + save router
- [ ] 13-03-PLAN.md — Frontend: ChangesPanel, SuccessCard, useProjectStore lastSave extension
- [ ] 13-04-PLAN.md — Wire AppShell three-state machine + human verification checkpoint

### Phase 14: History and Diff Viewer
**Goal**: Users can browse a flat timeline of saved versions and view the ACD diff report for any version inline
**Depends on**: Phase 13
**Requirements**: HIST-01, HIST-02
**Success Criteria** (what must be TRUE):
  1. User sees a flat timeline of saved versions per project showing date, commit message, and author — no branch DAG is shown
  2. Clicking any history entry embeds the ACD HTML diff report inline in the app (no separate browser tab or file download required)
**Plans**: 4 plans

Plans:
- [ ] 14-01-PLAN.md — Test scaffold (RED): test_history.py + history.py router stub + server.py registration (Wave 1)
- [ ] 14-02-PLAN.md — Backend: git_log, git_show_file in git_ops.py + history router implementation → tests GREEN (Wave 2)
- [ ] 14-03-PLAN.md — Frontend: HistoryPanel.tsx + DiffViewer.tsx components (Wave 2, parallel with 14-02)
- [ ] 14-04-PLAN.md — Wire AppShell state machine + Zustand cleanup + remove SuccessCard + human verification (Wave 3)

### Phase 15: System Tray and Auto-start
**Goal**: The app runs silently in the background on Windows boot and communicates its status through a system tray icon
**Depends on**: Phase 14
**Requirements**: APP-02, APP-05
**Success Criteria** (what must be TRUE):
  1. App starts automatically when Windows boots and runs silently without opening a browser or blocking the user
  2. System tray icon reflects current app state — watching (active), changes detected (badge), idle — and opens the browser UI when clicked
**Plans**: 5 plans

Plans:
- [ ] 15-01-PLAN.md — Wave 0: test scaffold (test_autostart.py, test_settings.py, test_tray.py, test_main.py — all RED)
- [ ] 15-02-PLAN.md — Backend: autostart.py service + main.py (--background, second-instance, tray thread) + app.spec console=False (Wave 1)
- [ ] 15-03-PLAN.md — Backend: tray.py + settings router + server.py registration + placeholder icon assets (Wave 1, parallel)
- [ ] 15-04-PLAN.md — Frontend: SettingsPanel.tsx + Sidebar gear icon + AppShell settings view branch (Wave 2)
- [ ] 15-05-PLAN.md — Human verification checkpoint: tray icon states, settings toggle, Registry key (Wave 3)

### Phase 16: Remote Auth and Push
**Goal**: Users can authenticate with GitHub or GitLab, back up saved versions to a remote with a single button, auto-create the remote repo if needed, and see at a glance how far ahead or behind they are from the remote
**Depends on**: Phase 15
**Requirements**: REMOTE-01, REMOTE-02, REMOTE-03, REMOTE-04, REMOTE-05, REMOTE-06
**Success Criteria** (what must be TRUE):
  1. User can connect to GitHub using a browser-based OAuth flow — no PAT or command-line steps required
  2. User can connect to GitLab using a personal access token with in-app step-by-step instructions and a direct link to the GitLab token settings page
  3. Auth credentials survive app restarts — stored in Windows Credential Manager or macOS Keychain via the OS credential store, never in plaintext
  4. User can push saved versions to the connected remote with a single button click
  5. If no remote repository exists yet, the app creates it automatically on first push — user never has to visit GitHub/GitLab to create a repo manually
  6. The UI shows an ahead/behind indicator (e.g. "↑ 3 ahead · ↓ 1 behind") so users know which saved versions exist only locally and which exist only on the remote
**Plans**: 5 plans

Plans:
- [ ] 16-01-PLAN.md — Wave 0 test scaffold: tests/test_remote.py (all RED) + stub files for remote_auth, github_api, gitlab_api, remote router (Wave 1)
- [ ] 16-02-PLAN.md — Backend auth services: remote_auth.py (device flow + keyring), github_api.py, gitlab_api.py → REMOTE-01/02/03 tests GREEN (Wave 2)
- [ ] 16-03-PLAN.md — Backend push: git_push/git_fetch/git_ahead_behind in git_ops.py + remote router + server.py + app.spec keyring hiddenimports → REMOTE-04/05/06 tests GREEN (Wave 2, parallel)
- [ ] 16-04-PLAN.md — Frontend: RemotePanel.tsx (tabs, device flow UI, GitLab PAT form, ahead/behind, push button) + AppShell/Sidebar wiring (Wave 3)
- [ ] 16-05-PLAN.md — Human verification checkpoint: full OAuth flow, credential persistence, push, auto-create repo, ahead/behind (Wave 4)

### Phase 16.1: Git history UX with push integration and git graph view (INSERTED)

**Goal:** Enhance HistoryPanel with per-entry cloud backup status icons, a push-from-history button, and a toggleable SVG git graph view — all without leaving the history panel
**Depends on:** Phase 16
**Plans:** 4/4 plans complete

Plans:
- [ ] 16.1-01-PLAN.md — Backend: git_pushed_shas + extend history endpoint with is_pushed field + tests GREEN (Wave 1)
- [ ] 16.1-02-PLAN.md — Frontend: cloud icons on EntryRow, push button in header, cross-panel push signal (AppShell + RemotePanel) (Wave 2)
- [ ] 16.1-03-PLAN.md — Frontend: SVG GraphView component + list/graph toggle + localStorage persistence (Wave 3)
- [ ] 16.1-04-PLAN.md — Human verification checkpoint: all 6 feature tests end-to-end (Wave 4)

### Phase 17: Branch Management
**Goal**: Users can create experiment copies of their project, switch between them, and always see which copy they are working on
**Depends on**: Phase 16
**Requirements**: BRANCH-01, BRANCH-02, BRANCH-03
**Success Criteria** (what must be TRUE):
  1. User can create an experiment copy with an auto-generated name in the format experiment/YYYY-MM-DD-description
  2. User can switch between experiment copies from within the app
  3. The current workspace (branch) is shown as a plain text label in the UI — no graph or DAG visualization is displayed
**Plans**: 5 plans

Plans:
- [x] 17-01-PLAN.md — Wave 0: RED test scaffold (test_branch.py) + branch.py stub router + server.py registration
- [x] 17-02-PLAN.md — Backend: git_ops branch functions + branch router implementation + history ?branch= param → GREEN
- [x] 17-03-PLAN.md — Frontend: shadcn Popover install + useProjectStore activeBranch + ChangesPanel branch chip + popover + AppShell wiring
- [x] 17-04-PLAN.md — Frontend: HistoryPanel branch-aware re-fetch + DiffViewer compare toggle + GraphView multi-branch SVG
- [x] 17-05-PLAN.md — Human verification checkpoint: all BRANCH requirements end-to-end

### Phase 18: CI Polish
**Goal**: CI template files live in the alteryx_diff repo under ci-templates/, are polished and production-ready, and ship with a setup README so users copy them into their own workflow repos
**Depends on**: Nothing (independent of desktop app — can execute in parallel with any phase)
**Requirements**: CI-01, CI-02, CI-03, CI-04
**Success Criteria** (what must be TRUE):
  1. GitHub Actions workflow updates the existing PR comment on each push instead of posting a new comment — one comment per PR regardless of push count
  2. GitHub Actions embeds a per-file interactive HTML report link in the PR comment — no single-ZIP bulk download link
  3. GitLab CI config no longer contains the placeholder test-job step
  4. ci-templates/README.md provides complete step-by-step setup instructions for both GitHub Actions and GitLab CI so a new user can configure it without reading source
**Plans**: 3 plans

Plans:
- [ ] 18-01-PLAN.md — Wave 0: RED test scaffold (test_ci_github_comment.py) + GitLab CI cleanup — remove test-job (CI-03) (Wave 1)
- [ ] 18-02-PLAN.md — Update GitHub helper (is_private_repo, per-file table, marker) + rewrite workflow Step 5 to find-or-update pattern → tests GREEN (CI-01, CI-02) (Wave 2)
- [ ] 18-03-PLAN.md — Assemble ci-templates/ distributable package + write README for non-technical analysts (CI-04) (Wave 3)

### Phase 18.1: Creation of PR (INSERTED)

**Goal:** Users on an experiment branch can open a GitHub Pull Request or GitLab Merge Request directly from the Remote panel without leaving the desktop app
**Requirements**: PR-API, PR-ENDPOINT, PR-UI
**Depends on:** Phase 17 (needs activeBranch Zustand state from Phase 17)
**Plans:** 3/4 plans complete

Plans:
- [ ] 18.1-01-PLAN.md — Backend services: GitHub PR + GitLab MR create/check functions in github_api.py + gitlab_api.py, TDD (Wave 1)
- [ ] 18.1-02-PLAN.md — Backend endpoints: POST /api/remote/pr/create + GET /api/remote/pr/status in remote.py (Wave 2)
- [ ] 18.1-03-PLAN.md — Frontend: inline PR form + humanized branch title + existing-PR link in RemotePanel.tsx (Wave 3)
- [ ] 18.1-04-PLAN.md — Human verification checkpoint: end-to-end PR creation flow (Wave 4)

### Phase 19: Close Audit Gaps — Branch Verification + APP-04b (COMPLETE)
**Goal**: Formally verify Phase 17 Branch Management by running gsd-verifier to produce VERIFICATION.md, and resolve the orphaned APP-04b requirement by confirming the existing implementation and updating REQUIREMENTS.md
**Requirements**: BRANCH-01, BRANCH-02, BRANCH-03, APP-04b
**Gap Closure:** Closes gaps from v1.1 audit — Phase 17 unverified, APP-04b checkbox unchecked
**Success Criteria** (what must be TRUE):
  1. Phase 17 VERIFICATION.md exists with code-level audit confirming BRANCH-01, BRANCH-02, BRANCH-03 are satisfied
  2. APP-04b checkbox updated to [x] in REQUIREMENTS.md with note that implementation exists in app/tray.py and Windows-only human verification applies
  3. REQUIREMENTS.md coverage count updated to 31 (reflecting APP-04 split into APP-04a and APP-04b)
**Plans**: 1 plan

Plans:
- [ ] 19-01-PLAN.md — Run gsd-verifier for Phase 17, update APP-04b checkbox + traceability, fix coverage count

### Phase 20: Tech Debt Cleanup
**Goal**: Resolve all non-intentional tech debt items identified in the v1.1 milestone audit — fix the autostart toggle regression, add error feedback to project add flow, replace the brittle DOM query with controlled React state, unify the config_store return type, and remove dead interface surface
**Depends on**: Phase 19
**Requirements**: APP-02 (toggle disable path), ONBOARD-02 (error feedback), REMOTE-02 (GitLab tab UX), CI-01 (GitLab MR comment dedup)
**Tech Debt:** Closes 7 items from v1.1 audit across phases 11, 15, 16, 16.1, 18
**Success Criteria** (what must be TRUE):
  1. After user disables autostart in Settings, the next manual app launch does NOT re-enable it — `register_autostart()` guarded with `if not autostart.is_autostart_enabled()`
  2. When `POST /api/projects` returns 400 or 409, user sees a visible error message in the UI — no silent fail
  3. GitLab tab switch in RemotePanel uses controlled React state, not `document.querySelector`
  4. `config_store.get_remote_repo()` has a unified, documented return type
  5. `mergeBaseSha` removed from HistoryPanelProps interface; `gitlab_repo_url` removed from RemotePanel local interface
  6. `.gitlab-ci.yml` implements find-or-update for MR comments (matching GitHub Actions behavior)
**Plans**: 3 plans

Plans:
- [ ] 20-01-PLAN.md — Backend fixes: autostart guard + config_store return type unification (Wave 1)
- [ ] 20-02-PLAN.md — Frontend fixes: App.tsx error feedback + RemotePanel React state + dead interface props removed (Wave 2)
- [ ] 20-03-PLAN.md — CI fix: .gitlab-ci.yml find-or-update MR comment + human verification checkpoint (Wave 3)

### Phase 21: Nyquist Wave-0 Remediation
**Goal**: All v1.1 phases achieve `wave_0_complete: true` Nyquist compliance — every phase has smoke tests that execute the critical path without requiring human interaction
**Depends on**: Phase 20
**Nyquist Gaps:** Phases 10, 11, 12, 13, 14, 15, 16, 16.1, 19 all have `wave_0_complete: false`
**Success Criteria** (what must be TRUE):
  1. Each of the 9 partial phases has wave_0 smoke tests added to its VALIDATION.md with `wave_0_complete: true`
  2. Smoke tests cover the critical path for each phase (e.g. app launches, file watcher detects changes, history loads)
  3. All smoke tests pass in CI on a clean checkout
**Plans**: 1 plan

Plans:
- [ ] 21-01-PLAN.md — Fix Phase 10 port tests (mock socket) + flip wave_0_complete: true in all 9 VALIDATION.md files

## Progress

**Execution Order:** 10 → 11 → 12 → 13 → 14 → 15 → 16 → 16.1 → 17 → 18 (Phase 18 independent)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Scaffold and Data Models | v1.0 | 3/3 | Complete | 2026-03-01 |
| 2. XML Parser and Validation | v1.0 | 2/2 | Complete | 2026-03-01 |
| 3. Normalization Layer | v1.0 | 4/4 | Complete | 2026-03-02 |
| 4. Node Matcher | v1.0 | 3/3 | Complete | 2026-03-02 |
| 5. Diff Engine | v1.0 | 3/3 | Complete | 2026-03-06 |
| 6. Pipeline Orchestration and JSON Renderer | v1.0 | 3/3 | Complete | 2026-03-06 |
| 7. HTML Report | v1.0 | 2/2 | Complete | 2026-03-06 |
| 8. Visual Graph | v1.0 | 3/3 | Complete | 2026-03-07 |
| 9. CLI Entry Point | v1.0 | 3/3 | Complete | 2026-03-07 |
| 10. App Scaffold | v1.1 | 3/3 | Complete    | 2026-03-13 |
| 11. Onboarding and Project Management | 5/5 | Complete    | 2026-03-14 | - |
| 12. File Watcher | 5/5 | Complete    | 2026-03-14 | - |
| 13. Save Version | 4/4 | Complete    | 2026-03-14 | - |
| 14. History and Diff Viewer | 4/4 | Complete    | 2026-03-15 | - |
| 15. System Tray and Auto-start | 5/5 | Complete    | 2026-03-15 | - |
| 16. Remote Auth and Push | 5/5 | Complete    | 2026-03-15 | - |
| 16.1. Git History UX + Graph View | 4/4 | Complete    | 2026-03-15 | - |
| 17. Branch Management | 5/5 | Complete    | 2026-03-15 | - |
| 18. CI Polish | 3/3 | Complete    | 2026-03-15 | - |
| 18.1. Creation of PR | 3/4 | Complete    | 2026-03-22 |
| 19. Close Audit Gaps | 1/1 | Complete    | 2026-03-22 | — |
| 20. Tech Debt Cleanup | 3/3 | Complete    | 2026-03-22 | — |
| 21. Nyquist Wave-0 Remediation | 1/1 | Complete    | 2026-03-22 | — |
