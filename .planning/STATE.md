---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Alteryx Git Companion
status: planning
stopped_at: Completed 18.1-01-PLAN.md
last_updated: "2026-03-21T23:44:03.302Z"
last_activity: 2026-03-13 — Roadmap created for v1.1 (9 phases, 28 requirements mapped)
progress:
  total_phases: 11
  completed_phases: 10
  total_plans: 47
  completed_plans: 44
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Accurate detection of functional changes — zero false positives from layout noise, zero missed configuration changes.
**Current focus:** v1.1 Phase 10 — App Scaffold (ready to plan)

## Current Position

Phase: 10 of 18 (App Scaffold)
Plan: — of — in current phase
Status: Ready to plan
Last activity: 2026-03-13 — Roadmap created for v1.1 (9 phases, 28 requirements mapped)

Progress: [░░░░░░░░░░] 0% (v1.1)

## Performance Metrics

**Velocity (v1.0 reference):**
- Total plans completed: 27
- Average duration: 4 min
- Total execution time: ~108 min

**By Phase (v1.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v1.0 phases 1-9 | 27 | ~108 min | 4 min |

**Recent Trend:**
- v1.1 not started
- Trend: —

*Updated after each plan completion*
| Phase 10-app-scaffold P01 | 11 | 2 tasks | 8 files |
| Phase 10-app-scaffold P02 | 4 | 2 tasks | 14 files |
| Phase 10-app-scaffold P03 | 1 | 2 tasks | 5 files |
| Phase 11-onboarding-and-project-management P01 | 5 | 3 tasks | 14 files |
| Phase 11-onboarding-and-project-management P02 | 4 | 2 tasks | 5 files |
| Phase 11-onboarding-and-project-management P03 | 2 | 2 tasks | 6 files |
| Phase 11-onboarding-and-project-management P04 | 525722 | 2 tasks | 3 files |
| Phase 11-onboarding-and-project-management P05 | 5 | 2 tasks | 0 files |
| Phase 12-file-watcher P01 | 2 | 2 tasks | 3 files |
| Phase 12-file-watcher P02 | 4 | 2 tasks | 2 files |
| Phase 12-file-watcher P03 | 25 | 2 tasks | 4 files |
| Phase 12-file-watcher P04 | 2 | 2 tasks | 4 files |
| Phase 12-file-watcher P05 | 30 | 1 tasks | 4 files |
| Phase 13-save-version P01 | 2 | 2 tasks | 3 files |
| Phase 13-save-version P02 | 3 | 2 tasks | 4 files |
| Phase 13-save-version P03 | 1 | 2 tasks | 3 files |
| Phase 13-save-version P04 | 10 | 2 tasks | 2 files |
| Phase 14-history-and-diff-viewer P01 | 2 | 2 tasks | 3 files |
| Phase 14-history-and-diff-viewer P02 | 5 | 2 tasks | 2 files |
| Phase 14-history-and-diff-viewer P03 | 15 | 2 tasks | 2 files |
| Phase 14-history-and-diff-viewer P04 | 25 | 3 tasks | 3 files |
| Phase 15-system-tray-and-auto-start P01 | 4 | 2 tasks | 4 files |
| Phase 15-system-tray-and-auto-start P02 | 4 | 2 tasks | 4 files |
| Phase 15-system-tray-and-auto-start P03 | 6 | 2 tasks | 5 files |
| Phase 15-system-tray-and-auto-start P04 | 8 | 2 tasks | 5 files |
| Phase 15-system-tray-and-auto-start P05 | 2 | 1 tasks | 1 files |
| Phase 15-system-tray-and-auto-start P05 | 2 | 2 tasks | 0 files |
| Phase 16-remote-auth-and-push P01 | 5 | 1 tasks | 6 files |
| Phase 16-remote-auth-and-push P02 | 15 | 2 tasks | 7 files |
| Phase 16-remote-auth-and-push P03 | 4 | 2 tasks | 5 files |
| Phase 16-remote-auth-and-push P04 | 3 | 2 tasks | 4 files |
| Phase 16-remote-auth-and-push P05 | checkpoint | 2 tasks | 0 files |
| Phase 16.1 P01 | 2 | 2 tasks | 3 files |
| Phase 16.1 P02 | 2 | 2 tasks | 3 files |
| Phase 16.1 P03 | 2 | 1 tasks | 1 files |
| Phase 16.1-git-history-ux-with-push-integration-and-git-graph-view P04 | 5 | 2 tasks | 0 files |
| Phase 17-branch-management P01 | 147 | 2 tasks | 3 files |
| Phase 17-branch-management P02 | 177 | 2 tasks | 3 files |
| Phase 17-branch-management P03 | 3 | 2 tasks | 6 files |
| Phase 17-branch-management P04 | 5 | 2 tasks | 3 files |
| Phase 18-ci-polish P01 | 2 | 2 tasks | 2 files |
| Phase 18-ci-polish P02 | 2 | 2 tasks | 2 files |
| Phase 18-ci-polish P03 | 4 | 2 tasks | 5 files |
| Phase 18.1-creation-of-pr P01 | 2 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap v1.1]: Phase numbering starts at 10 — continuous from v1.0 (ended at 9)
- [Roadmap v1.1]: acd CLI (v1.0) bundled into .exe via PyInstaller — NOT rebuilt; consumed as dependency
- [Roadmap v1.1]: Phase 18 (CI Polish) targets separate repo (/Users/laxmikantmukkawar/alteryx/) — independent of desktop app phases
- [Roadmap v1.1]: System tray / auto-start (Phase 15) placed after core save/history loop (Phases 13-14) — core value validated before deployment UX
- [Roadmap v1.1]: Branch features (Phase 17) depend on Remote (Phase 16) — need a remote to push branches to
- [Phase 10-app-scaffold]: SPAStaticFiles subclass required for SPA routing — Starlette StaticFiles(html=True) doesn't fall back to index.html for unknown paths
- [Phase 10-app-scaffold]: pytest pythonpath=['.'] added so app/ package at repo root is importable alongside src/ layout
- [Phase 10-app-scaffold]: shadcn@latest init --defaults incompatible with Vite 8 — manual setup of components.json, lib/utils.ts, and CSS required
- [Phase 10-app-scaffold]: Tailwind v4 uses @theme CSS block instead of tailwind.config.js — color tokens defined as --color-* for shadcn compatibility
- [Phase 10-app-scaffold]: upx=False in app.spec — UPX not pre-installed on windows-latest runners; avoids silent skip or CI failure
- [Phase 10-app-scaffold]: console=True in Phase 10 spec — debug visibility; Phase 15 will flip to False when system tray/background mode is added
- [Phase 10-app-scaffold]: Quoted 'on': key in release.yml — PyYAML 1.1 parses bare 'on' as boolean True; quoting makes it string-key for programmatic validation while GitHub Actions handles both forms
- [Phase 11-01]: Routers registered in server.py in Plan 01 (not Plan 04 as noted) — required for TestClient to reach endpoints in RED tests
- [Phase 11-01]: shadcn CLI resolves @/ alias literally — components must be moved from @/components/ui/ to src/components/ui/ per vite.config.ts alias
- [Phase 11-01]: npm legacy-peer-deps=true set globally to resolve vite@8 peer conflict with @tailwindcss/vite@4.2.1
- [Phase 11-02]: Routers use module-level imports (from app.services import svc) so unittest.mock.patch targets work correctly
- [Phase 11-02]: Path not resolved via Path.resolve() in add_project — macOS /var symlinks to /private/var causing test assertion failures with tmp_path
- [Phase 11-03]: isLoading: true initial Zustand state prevents WelcomeScreen flash before first API response arrives
- [Phase 11-03]: onAddFolder prop passed as no-op from App.tsx; wired to real folder-picker dialog in Plan 04
- [Phase 11-03]: Sidebar DELETE /api/projects/{id} is best-effort — removeProject called regardless of network error
- [Phase 11-04]: server.py router registration was completed in Plan 01 (not Plan 04); Task 1 verified all routes present with no changes needed
- [Phase 11-04]: Pre-confirmation pattern: GET /api/projects/check BEFORE any git operation; AlertDialog only shown when folder has no git history; Cancel aborts entirely
- [Phase 11-04]: GitIdentityCard rendered inline in AppShell main content area (not modal) for UX consistency with EmptyState
- [Phase 11-onboarding-and-project-management]: Plan 05 is verification-only — all implementation landed in 11-01 through 11-04; human confirmed all ONBOARD requirements working end-to-end
- [Phase 12-file-watcher]: git_changed_workflows uses git status --porcelain (not diff) to catch both staged and untracked new files
- [Phase 12-file-watcher]: is_network_path normalizes backslashes to forward slashes before UNC check for platform-independent detection
- [Phase 12-file-watcher]: WORKFLOW_SUFFIXES frozenset defined at module level in git_ops.py — shared constant for both git_changed_workflows and count_workflows
- [Phase 12-file-watcher]: WatcherManager uses loop.call_soon_threadsafe for all asyncio queue pushes from watchdog daemon threads — asyncio.Queue is not thread-safe
- [Phase 12-file-watcher]: _WorkflowEventHandler.on_any_event used instead of on_modified to catch Alteryx temp-file-rename save pattern
- [Phase 12-file-watcher]: SSE generator uses asyncio.wait_for + request.is_disconnected() instead of bare await q.get() — allows clean disconnect detection and makes generator testable
- [Phase 12-file-watcher]: test_sse_endpoint_headers calls route handler directly with AsyncMock for is_disconnected — TestClient.stream() hangs on infinite SSE generators
- [Phase 12-file-watcher]: useWatchEvents called at App.tsx top level so badge updates arrive regardless of active view
- [Phase 12-file-watcher]: Amber badge hidden entirely when changedCount is 0 or undefined — no '0' badge noise
- [Phase 12-file-watcher]: WORKFLOW_SUFFIXES extended to .yxmc, .yxzp, .yxapp — all five Alteryx file types now watched and counted
- [Phase 12-file-watcher]: watchdog recursive=True — subdirectory workflows trigger events; Alteryx projects nest workflows in subfolders
- [Phase 12-file-watcher]: SSE seed on connect: new subscribers receive current badge state immediately — prevents stale UI on page reload
- [Phase 13-save-version]: shadcn CLI resolves @/ alias literally — checkbox.tsx and textarea.tsx moved from @/components/ui/ to src/components/ui/ per vite alias (same pattern as Phase 11)
- [Phase 13-save-version]: git_discard_files copies to .acd-backup BEFORE removing — backup-first safety guarantee for v1
- [Phase 13-save-version]: git_undo_last_commit uses --soft not --hard — file content preserved in working tree
- [Phase 13-save-version]: save router uses module-level import of git_ops so unittest.mock.patch targets work correctly
- [Phase 13-save-version]: ChangesPanel accepts changedFiles as prop — AppShell owns fetch in Plan 04
- [Phase 13-save-version]: AppShell owns fetchWatchStatus — ChangesPanel receives changedFiles as prop (not self-fetching)
- [Phase 13-save-version]: lastSave !== null (not hasCommits) is primary SuccessCard condition — only show after explicit save in this session
- [Phase 13-save-version]: fetchWatchStatus called after undo and discard for immediate UI sync alongside SSE updates
- [Phase 14-01]: history router uses module-level git_ops import (noqa: F401) so mock.patch targeting app.routers.history.git_ops works correctly — matches save.py convention
- [Phase 14-history-and-diff-viewer]: Two-pass git log approach (headers + diff-tree per SHA) avoids fragile blank-line parsing from --name-only single-pass
- [Phase 14-history-and-diff-viewer]: mkstemp pattern used for temp files in _run_diff — Windows-safe alternative to NamedTemporaryFile
- [Phase 14-history-and-diff-viewer]: DiffViewer uses iframe + blob URL for HTML isolation — ACD diff reports contain style/script tags that collide if injected into the React DOM directly
- [Phase 14-history-and-diff-viewer]: HistoryPanel inline file selector uses tab buttons for 2-4 files, shadcn Select for 5+ — avoids modal overhead for small file sets
- [Phase 14-history-and-diff-viewer]: localStorage shim injected into blob HTML — blob: URLs have null origin causing SecurityError on localStorage access which aborts vis.js graph init
- [Phase 14-history-and-diff-viewer]: onLoad calls switchView('split') on iframe contentWindow to force vis.js Networks init after iframe is fully painted with correct container dimensions
- [Phase 15-01]: Graceful RED pattern: try/except ImportError + _require() so stubs report FAILED not collection ERROR
- [Phase 15-01]: winreg mocked via sys.modules injection (patch.dict) for cross-platform testing of Windows-registry functions
- [Phase 15-01]: _compute_state designed as pure function (dict -> tuple) so tray tests need no pystray or OS dependency
- [Phase 15-02]: is_instance_running delegates to find_available_port(start=7433, count=1) so test patches propagate correctly in test environment where port 7433 is occupied
- [Phase 15-02]: app/tray.py stub created before Plan 03 pystray implementation so main() tray import succeeds during test_main.py runs
- [Phase 15-02]: PIL removed from app.spec excludes — pystray requires Pillow; console=True flipped to console=False for background-mode deployment
- [Phase 15-system-tray-and-auto-start]: pystray import guarded by try/except at module level -- PYSTRAY_AVAILABLE flag controls run() path; CI/macOS tests never need pystray
- [Phase 15-system-tray-and-auto-start]: settings.router registered in server.py after history.router; module-level autostart import enables unittest.mock.patch targeting
- [Phase 15-04]: shadcn CLI resolves @/ alias literally — switch.tsx and label.tsx moved from @/components/ui/ to src/components/ui/ per vite alias (same pattern as Phase 11/13)
- [Phase 15-04]: activeView state ('default' | 'settings') in AppShell — simplest routing for single settings branch without router library
- [Phase 15-04]: SettingsPanel is self-fetching (no props) — fetches /api/settings on mount, isolated concern
- [Phase 15-04]: handleUndo signature aligned to () => void matching HistoryPanel.onUndo contract — fetchHistory re-derives hasCommits state
- [Phase 15-system-tray-and-auto-start]: test_port_probe::test_find_available_port_returns_7433 is a pre-existing environment-specific failure (Phase 10) — not Phase 15 regression; deferred to deferred-items.md
- [Phase 15-system-tray-and-auto-start]: Windows-specific behaviors (tray icon display, Registry key write/delete) verified by design review and automated tests; interactive Windows hardware session deferred — does not block Phase 16
- [Phase 16-remote-auth-and-push]: git_push and git_ahead_behind stubs added to git_ops.py (not a new module) — consistent with existing git operation grouping
- [Phase 16-remote-auth-and-push]: Router stub imports all three service modules at module level so patch targets work in test_remote.py
- [Phase 16-remote-auth-and-push]: poll_and_store implemented as synchronous function (time.sleep) — tests patch app.services.remote_auth.time; router github/start returns immediately without waiting for poll
- [Phase 16-remote-auth-and-push]: remote.router registered in server.py — router tests use TestClient on app; missing registration caused 405 Method Not Allowed
- [Phase 16-remote-auth-and-push]: GIT_ASKPASS pattern for git_push: write temp .sh/.bat echoing token, chmod 700, set GIT_ASKPASS env var; token never in URL or subprocess args
- [Phase 16-remote-auth-and-push]: git_fetch uses GIT_ASKPASS temp-script pattern; non-zero returncode silently ignored for unreachable remote
- [Phase 16-remote-auth-and-push]: POST /github/connect stores PAT without API validation — user trusted, consistent with device-flow path
- [Phase 16-remote-auth-and-push]: config_store remote_repos stored as dict keyed by project_id then provider_url — not in keyring
- [Phase 16-remote-auth-and-push]: shadcn Tabs moved from @/components/ui/ to src/components/ui/ (Phase 11 alias pattern)
- [Phase 16-remote-auth-and-push]: GitHub PAT fallback calls POST /api/remote/github/connect (SERVICE_GITHUB keyring), separate from GitLab endpoint
- [Phase 16-remote-auth-and-push]: Plan 05 is verification-only — all implementation landed in 16-01 through 16-04; human confirmed all REMOTE requirements working end-to-end
- [Phase 16.1]: git_pushed_shas placed after git_ahead_behind in git_ops.py — both use @{u} pattern; is_pushed annotated in router (list_history) not in git_log service — router owns response shape
- [Phase 16.1]: RemoteStatus interface copied into HistoryPanel.tsx (not imported) to avoid circular dependencies between sibling components
- [Phase 16.1]: lastPushTimestamp = Date.now() used as signal dependency for useEffect without extra boolean state (timestamp-as-signal pattern)
- [Phase 16.1]: Back-nav from DiffViewer requires no change — setSelectedDiff(null) already returns to HistoryPanel with localStorage-restored view mode
- [Phase 16.1]: HTML entity codes used for toggle button symbols to avoid unicode build issues; SVG_COL_WIDTH=36px; GraphView defined in same file as HistoryPanel to avoid circular imports
- [Phase 16.1]: Plan 04 is verification-only — all Phase 16.1 implementation confirmed working end-to-end by human verification; 203 backend tests passed
- [Phase 17-branch-management]: branch.router registered after remote.router; branch name inputs in body/query params not path segments (experiment/ contains /)
- [Phase 17-01]: Module-level subprocess import in branch.py enables mock.patch for merge-base tests
- [Phase 17-02]: None-guard in checkout/delete router endpoints: mock.return_value=None in tests but router expects dict — normalize to {success: True} when git_ops returns None
- [Phase 17-02]: git_log branch param appended as final positional arg to git log command — filters log to ancestry of named branch ref
- [Phase 17-branch-management]: lastBranchSwitchTimestamp removed — AppShell.handleBranchSwitch calls fetchHistory() directly; no behavioral loss, eliminates TS unused-variable error
- [Phase 17-branch-management]: shadcn Popover moved from @/components/ui/ to src/components/ui/ per established Phase 11 alias pattern
- [Phase 17-branch-management]: mergeBaseSha fetched in fetchBranch (branch property); allBranchEntries fetched in fetchHistory (history data)
- [Phase 17-branch-management]: Multi-branch GraphView uses allBranchEntries as row index Map — both columns share vertical timeline
- [Phase 17-branch-management]: compare toggle: isExperimentBranch + compareTo controls visibility; compareMode drives compare_to URL param
- [Phase 18-ci-polish]: Marker constant defined as module-level MARKER var in test file — single source of truth for expected first-line value
- [Phase 18-ci-polish]: Tests use sys.path.insert to import non-package helper from alteryx repo — no install required
- [Phase 18-ci-polish]: Task 2 committed in /alteryx repo (separate git repo) — correct git context for .gitlab-ci.yml change
- [Phase 18-ci-polish]: Python owns the marker: both comment builders prepend <!-- acd-diff-report -->; JS reads file as-is to prevent double-marker
- [Phase 18-ci-polish]: run_url promoted to explicit param on build_comment() — enables unit testing without env vars
- [Phase 18-ci-polish]: is_private_repo() defaults to True conservatively on missing env or any exception
- [Phase 18-ci-polish]: per_page:100 in listComments — avoids first-page miss on busy PRs (GitHub default is 30)
- [Phase 18-ci-polish]: ruff noqa E501 on Markdown string literals in ci-templates Python helpers — Markdown output can't be line-wrapped; noqa is the correct fix
- [Phase 18-ci-polish]: ci-templates/ mirrored directory structure — users copy entire directory without path surgery; README is the canonical setup guide
- [Phase 18.1-01]: parse_github_owner_repo regex handles both .git and non-.git URLs; ValueError on no match
- [Phase 18.1-01]: get_gitlab_project_id encodes namespace slash as %2F via direct string replace (not urllib.parse.quote) per RESEARCH.md

### Roadmap Evolution

- Phase 16.1 inserted after Phase 16: Git history UX with push integration and git graph view (URGENT)
- Phase 18.1 inserted after Phase 18: Creation of PR (URGENT)

### Pending Todos

- Validate GUID_VALUE_KEYS against real .yxmd files (tech debt from v1.0)
- Wire JSONRenderer into CLI --json path or document _cli_json_output() schema as stable (tech debt from v1.0)

### Blockers/Concerns

- PyInstaller .exe may trigger Windows Defender SmartScreen — plan for code signing or user-facing bypass instructions in Phase 10
- watchdog has known issues with SMB/network drives — Phase 12 must explicitly test or document fallback behavior

## Session Continuity

Last session: 2026-03-21T23:44:03.300Z
Stopped at: Completed 18.1-01-PLAN.md
Resume file: None
