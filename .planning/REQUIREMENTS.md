# Requirements: Alteryx Git Companion

**Defined:** 2026-03-13
**Core Value:** Accurate detection of functional changes — zero false positives from layout noise, zero missed configuration changes.

## v1.1 Requirements

### APP — Application Infrastructure

- [x] **APP-01**: User can install the app on Windows without installing Python (.exe installer, PyInstaller bundle)
- [x] **APP-02**: App starts automatically when Windows boots, running silently in the background
- [x] **APP-03**: App runs on port 7433 with automatic fallback to ports 7434–7443 if already in use
- [x] **APP-04a**: Browser opens automatically at localhost:PORT when the exe starts (webbrowser.open on startup)
- [ ] **APP-04b**: User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT)
- [x] **APP-05**: System tray icon shows app status (watching / changes detected / idle)

### ONBOARD — Onboarding

- [x] **ONBOARD-01**: User sees a first-run welcome screen explaining what the app does before any setup
- [x] **ONBOARD-02**: User can add a project folder — app auto-initializes git if folder is not already a repo
- [x] **ONBOARD-03**: App detects missing git user identity (name/email) and prompts for it on first use
- [x] **ONBOARD-04**: User can register and switch between multiple project folders from a left-panel project list

### WATCH — File Watching

- [x] **WATCH-01**: App auto-detects changed .yxmd and .yxwz files in registered folders and shows a change badge
- [x] **WATCH-02**: App auto-switches to polling observer (5-second interval) for network/SMB/UNC paths, native observer for local drives
- [x] **WATCH-03**: App warns user when first version save will capture all N existing workflows in a folder

### SAVE — Save Version

- [x] **SAVE-01**: User can select changed workflows, write a commit message with placeholder guidance, and save a version
- [x] **SAVE-02**: User can undo the last saved version with one click, with confirmation copy explaining file changes are preserved
- [x] **SAVE-03**: Discarding uncommitted changes moves files to a `.acd-backup` folder rather than permanent deletion

### HIST — History

- [x] **HIST-01**: User can view a flat timeline of saved versions (date, message, author) per project — no branch DAG
- [x] **HIST-02**: User can click any history entry to view the ACD diff report for that version embedded inline

### REMOTE — Remote & Backup

- [x] **REMOTE-01**: User can connect to GitHub using browser-based OAuth (no PAT required)
- [x] **REMOTE-02**: User can connect to GitLab using a personal access token with in-app step-by-step instructions and direct link to GitLab settings
- [x] **REMOTE-03**: Auth credentials stored in OS credential store (Windows Credential Manager / macOS Keychain via keyring)
- [x] **REMOTE-04**: User can back up (push) saved versions to GitHub or GitLab with a single button
- [x] **REMOTE-05**: If no remote repository exists yet, the app creates one automatically on GitHub or GitLab when the user first pushes, without requiring the user to leave the app
- [x] **REMOTE-06**: User can see how many saved versions are ahead of the remote (local-only) and how many are behind (remote-only not yet pulled), shown as a simple ahead/behind indicator in the UI

### BRANCH — Experiment Copies

- [ ] **BRANCH-01**: User can create an experiment copy (branch) with auto-generated name (experiment/YYYY-MM-DD-description)
- [ ] **BRANCH-02**: User can switch between experiment copies
- [ ] **BRANCH-03**: Current workspace shown as a label in the UI (no DAG visualization)

### CI — CI Integration Polish

- [x] **CI-01**: GitHub Actions workflow updates the existing PR comment on each push instead of creating a new one
- [x] **CI-02**: GitHub Actions embeds the workflow graph diff as an inline PNG image in the PR comment body (no ZIP download required)
- [x] **CI-03**: GitLab CI removes the placeholder test-job step that serves no purpose
- [x] **CI-04**: CI repo has a proper README with step-by-step setup instructions for both GitHub Actions and GitLab CI

## v2 Requirements

Deferred — validate core commit/history/diff loop with real users first.

### UX Enhancements

- **UX-01**: Auto-suggested commit message pre-populated from ACD diff summary ("Modified 2 tools, added 1 connection")
- **UX-02**: Scheduled version reminders: "You have unsaved changes from today. Save a version before closing?"
- **UX-03**: "Open in Alteryx Designer" button from any workflow in the app

### Collaboration

- **COLLAB-01**: Conflict resolution UX — show both versions via ACD diff when push fails due to remote changes
- **COLLAB-02**: Per-workflow blame view showing who last modified each file and when
- **COLLAB-03**: CI integration link in app — show when a diff report was posted on a PR

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-commit on file save | Creates useless history with no messages; analysts need intentional named saves (Figma/Google Docs model) |
| Branch DAG visualization | Incomprehensible to non-technical users; flat timeline is the right model |
| Three-way merge editor | XML merge is meaningless to Alteryx analysts; binary choice (my version / their version) is sufficient |
| In-app .yxmd XML editor | Risk of file corruption; Alteryx Designer is the only safe editor |
| Full GitHub/GitLab PR review UI | Alteryx analysts don't use GitHub for issue tracking; scope creep with no value for this persona |
| Git LFS | Unnecessary for typical .yxmd sizes (<1MB); add only if consistently >50MB files observed |
| Real-time Alteryx Designer plugin | Requires Designer plugin API; explicitly deferred in v1.0 out of scope |
| Three-way semantic workflow merge | 10x v1 scope; deferred from v1.0, still deferred |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| APP-01 | Phase 10 | Complete |
| APP-02 | Phase 15 | Complete |
| APP-03 | Phase 10 | Complete |
| APP-04a | Phase 10 | Complete |
| APP-04b | Phase 19 | Pending |
| APP-05 | Phase 15 | Complete |
| ONBOARD-01 | Phase 11 | Complete |
| ONBOARD-02 | Phase 11 | Complete |
| ONBOARD-03 | Phase 11 | Complete |
| ONBOARD-04 | Phase 11 | Complete |
| WATCH-01 | Phase 12 | Complete |
| WATCH-02 | Phase 12 | Complete |
| WATCH-03 | Phase 12 | Complete |
| SAVE-01 | Phase 13 | Complete |
| SAVE-02 | Phase 13 | Complete |
| SAVE-03 | Phase 13 | Complete |
| HIST-01 | Phase 14 | Complete |
| HIST-02 | Phase 14 | Complete |
| REMOTE-01 | Phase 16 | Complete |
| REMOTE-02 | Phase 16 | Complete |
| REMOTE-03 | Phase 16 | Complete |
| REMOTE-04 | Phase 16 | Complete |
| REMOTE-05 | Phase 16 | Complete |
| REMOTE-06 | Phase 16 | Complete |
| BRANCH-01 | Phase 19 | Pending |
| BRANCH-02 | Phase 19 | Pending |
| BRANCH-03 | Phase 19 | Pending |
| CI-01 | Phase 18 | Complete |
| CI-02 | Phase 18 | Complete |
| CI-03 | Phase 18 | Complete |
| CI-04 | Phase 18 | Complete |

**Coverage:**
- v1.1 requirements: 31 total (APP-04 split into APP-04a + APP-04b)
- Mapped to phases: 31
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 — APP-04 split into APP-04a (Phase 10, browser auto-open on startup) and APP-04b (Phase 15, tray icon click opens browser)*
