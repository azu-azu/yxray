---
phase: 14-history-and-diff-viewer
verified: 2026-03-14T12:00:00Z
status: human_needed
score: 11/12 must-haves verified
human_verification:
  - test: "Open a project with prior commits and confirm HistoryPanel renders the timeline"
    expected: "List of saved versions with commit messages, author names, relative timestamps, and 'Latest' badge on the first entry"
    why_human: "Visual rendering and relative timestamp formatting cannot be confirmed programmatically"
  - test: "Click a non-first history entry and confirm DiffViewer shows ACD diff report inline"
    expected: "Loading spinner appears briefly, then ACD HTML diff report renders inside an iframe — full height, no new tab, with '← History | [commit message]' header"
    why_human: "iframe rendering, vis.js graph visibility, and blob URL behaviour require a live browser"
  - test: "Click the oldest history entry (has_parent=false) and confirm friendly message appears"
    expected: "Message 'This is the first saved version — no previous version to compare.' is displayed — no iframe or error state"
    why_human: "UI state branch for first-commit case requires browser verification"
  - test: "Save a version from ChangesPanel and confirm transition to HistoryPanel"
    expected: "After save, app shows HistoryPanel (not SuccessCard). New entry appears at top with 'just now' timestamp and 'Latest' badge"
    why_human: "State-machine transition after save requires end-to-end live flow"
  - test: "Switch between two projects and confirm history list resets correctly"
    expected: "Switching projects immediately shows the new project's history with no stale entries; projects with no commits show EmptyState"
    why_human: "Project-switch state reset requires live interaction to confirm absence of stale renders"
---

# Phase 14: History and Diff Viewer — Verification Report

**Phase Goal:** Users can browse a flat timeline of saved versions and view the ACD diff report for any version inline
**Verified:** 2026-03-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `git_log(folder)` returns flat commit list newest-first with sha, message, author, timestamp, files_changed (workflow files only), has_parent | VERIFIED | `app/services/git_ops.py` lines 214-291: two-pass subprocess implementation; 4 unit tests pass (test_git_log, test_git_log_empty, test_git_log_filters_non_workflow_files, test_git_show_file) |
| 2  | `git_show_file(folder, sha, filepath)` returns bytes at commit or raises FileNotFoundError | VERIFIED | `app/services/git_ops.py` lines 294-305: raw bytes returned; FileNotFoundError raised on non-zero returncode; tests pass |
| 3  | GET /api/history/{project_id}?folder= returns 200 with commit list | VERIFIED | `app/routers/history.py` lines 46-55: `list_history` endpoint implemented and registered; test_list_history_endpoint passes |
| 4  | GET /api/history/{sha}/diff?folder=&file= returns HTML diff report for a non-first commit | VERIFIED | `app/routers/history.py` lines 58-87: `get_diff` with `_run_diff` helper using mkstemp + pipeline_run + HTMLRenderer; test_diff_endpoint passes |
| 5  | GET /api/history/{sha}/diff for first commit returns 200 JSON {is_first_commit: true} | VERIFIED | `app/routers/history.py` line 80: `JSONResponse({"is_first_commit": True})`; test_diff_endpoint_first_commit passes |
| 6  | All 9 tests in test_history.py pass GREEN | VERIFIED | `pytest tests/test_history.py` — 9 passed in 1.60s |
| 7  | HistoryPanel renders scrollable commit list with message, author, relative timestamp, "Latest" pill on first entry | VERIFIED (code) / NEEDS HUMAN (visual) | `app/frontend/src/components/HistoryPanel.tsx`: `formatRelativeTime`, Badge with `isLatest={index === 0}`, truncated message, author display — all present and TypeScript-valid |
| 8  | HistoryPanel entries are clickable; multi-file entries offer inline file selector before calling onSelectEntry | VERIFIED (code) / NEEDS HUMAN (visual) | Lines 46-65: single-file direct call; lines 105-142: tab buttons for 2-4 files, native select for 5+; all paths call `onSelectEntry` |
| 9  | DiffViewer renders header with back navigation and commit message, shows spinner while loading, friendly message for first commits, iframe with ACD HTML via blob URL | VERIFIED (code) / NEEDS HUMAN (visual) | `DiffViewer.tsx`: header at lines 107-116, spinner at lines 120-123, first-commit message at lines 126-131, iframe at lines 146-163, blob URL at line 81 |
| 10 | When changedCount=0 and hasCommits=true, main content shows HistoryPanel not SuccessCard | VERIFIED | `AppShell.tsx` lines 122-131: `if (hasCommits)` renders `HistoryPanel`; SuccessCard.tsx deleted; no SuccessCard import remains |
| 11 | Switching projects resets history list and selectedDiff immediately | VERIFIED (code) / NEEDS HUMAN (interaction) | `AppShell.tsx` lines 59-66: useEffect on `activeProjectId` calls `setHistory([])`, `setSelectedDiff(null)`, `fetchHistory()`, `fetchWatchStatus()` |
| 12 | After save, UI transitions to HistoryPanel with new entry at top | VERIFIED (code) / NEEDS HUMAN (end-to-end) | `AppShell.tsx` lines 68-71: `handleSaved` calls `fetchWatchStatus()` then `fetchHistory()`; state machine shows HistoryPanel when changedFiles is empty |

**Score:** 12/12 truths verified in code; 5 require human confirmation for live browser behaviour

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_history.py` | 9 RED-to-GREEN tests for HIST-01 and HIST-02 | VERIFIED | 9 tests collected, all PASS |
| `app/routers/history.py` | Full history router — list_history and get_diff implemented | VERIFIED | 88 lines; both endpoints fully implemented with `_run_diff` helper |
| `app/services/git_ops.py` | `git_log()` and `git_show_file()` added | VERIFIED | Lines 214-305: both functions present with full implementation |
| `app/server.py` | history router imported and registered | VERIFIED | Line 17: `from app.routers import ... history`; line 51: `app.include_router(history.router)` |
| `app/frontend/src/components/HistoryPanel.tsx` | CommitEntry interface exported; HistoryPanel component | VERIFIED | 185 lines; `export interface CommitEntry` at line 6; `export function HistoryPanel` at line 147 |
| `app/frontend/src/components/DiffViewer.tsx` | DiffViewer component with blob URL iframe | VERIFIED | 167 lines; `export function DiffViewer` at line 11; blob URL at line 81 |
| `app/frontend/src/components/AppShell.tsx` | 4-state machine with HistoryPanel + DiffViewer | VERIFIED | Lines 99-133: 4-branch renderMainContent; HistoryPanel and DiffViewer wired |
| `app/frontend/src/store/useProjectStore.ts` | LastSave / lastSave / setLastSave removed | VERIFIED | No `LastSave`, `lastSave`, or `setLastSave` present in file |
| `app/frontend/src/components/SuccessCard.tsx` | Deleted — no broken imports | VERIFIED | File does not exist; no SuccessCard reference in any src/ file |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/server.py` | `app/routers/history.py` | `app.include_router(history.router)` | WIRED | Lines 17 and 51 of server.py confirmed |
| `app/routers/history.py` | `app/services/git_ops.py` | `from app.services import git_ops` (module-level) | WIRED | Line 16: `from app.services import git_ops  # noqa: F401` |
| `app/routers/history.py get_diff` | `alteryx_diff.pipeline.run` | `_run_diff()` helper using `pipeline_run(DiffRequest(...))` | WIRED | Lines 21-43: `_run_diff` writes bytes to mkstemp files and calls `pipeline_run(DiffRequest(...))` |
| `DiffViewer.tsx` | `/api/history/{sha}/diff` | `fetch` in `useEffect`, blob URL assigned to iframe src | WIRED | Lines 35-37: fetch call; line 81: `URL.createObjectURL(new Blob([html], {type: 'text/html'}))`; line 148: `src={iframeSrc}` on iframe |
| `AppShell.tsx fetchHistory` | `/api/history/{project_id}` | `fetch` in `useCallback`, populates `history` state | WIRED | Lines 45-56: `fetchHistory` callback confirmed; called on project switch (line 65) and after save (line 70) |
| `AppShell.tsx handleSaved` | `fetchHistory` | called after successful save instead of setLastSave | WIRED | Lines 68-71: `handleSaved` calls `await fetchHistory()` |
| `AppShell.tsx renderMainContent` | `HistoryPanel` + `DiffViewer` | `hasCommits` + `selectedDiff` state machine branches | WIRED | Lines 111-131: `if (hasCommits && selectedDiff)` renders DiffViewer; `if (hasCommits)` renders HistoryPanel |
| `tests/test_history.py` | `app.routers.history.git_ops` | `unittest.mock.patch` at module level | WIRED | mock.patch targets confirmed by passing tests |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HIST-01 | 14-01, 14-02, 14-03, 14-04 | User can view a flat timeline of saved versions (date, message, author) per project — no branch DAG | SATISFIED | GET /api/history/{project_id} returns flat list; HistoryPanel renders flat timeline; AppShell state machine shows HistoryPanel when hasCommits=true |
| HIST-02 | 14-01, 14-02, 14-03, 14-04 | User can click any history entry to view the ACD diff report for that version embedded inline | SATISFIED (code) / NEEDS HUMAN | GET /api/history/{sha}/diff returns ACD HTMLResponse; DiffViewer fetches and renders via iframe+blob URL; AppShell wires onSelectEntry to setSelectedDiff which triggers DiffViewer render |

No orphaned requirements — both HIST-01 and HIST-02 are claimed by all four plans and covered by implementation evidence.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TODOs, stubs, or empty implementations found in phase 14 artifacts | — | — |

Scan covered:
- `app/routers/history.py` — no NotImplementedError, no TODO
- `app/services/git_ops.py` (git_log, git_show_file additions) — no stubs
- `app/frontend/src/components/HistoryPanel.tsx` — no placeholder returns
- `app/frontend/src/components/DiffViewer.tsx` — no placeholder returns
- `app/frontend/src/components/AppShell.tsx` — no SuccessCard references, no stale lastSave calls

---

### Pre-existing Test Failure (Not Phase 14)

`tests/test_port_probe.py::test_find_available_port_returns_7433` fails when port 7433 is already in use on the host machine. This failure is documented in the Plan 01 summary as a known pre-existing flaky test unrelated to Phase 14. All 117 other tests pass.

---

### Human Verification Required

#### 1. History timeline rendering

**Test:** Open a project folder that has prior saves (commits). Observe the main content area when no files are changed.
**Expected:** Scrollable list of saved versions — each row shows commit message (truncated at ~60 chars), author name, relative timestamp ("just now" / "X min ago" / "Mar 14"), and a "Latest" badge on the topmost entry. "Undo last save" button visible at top-right.
**Why human:** Visual layout, badge rendering, and relative time arithmetic require a live browser to confirm.

#### 2. Diff viewer with ACD report inline

**Test:** Click any non-first history entry with a `.yxmd` file in its `files_changed` list.
**Expected:** A brief loading spinner, then the full ACD HTML diff report renders inside an iframe filling the right panel. Header shows "← History | [commit message]". vis.js graph view is visible (not blank). No new browser tab opens.
**Why human:** iframe rendering, blob URL security, localStorage shim, and vis.js graph dimensions all require a live browser.

#### 3. First-commit friendly message

**Test:** Click the oldest history entry (bottom of list, no "Latest" badge).
**Expected:** Friendly message: "This is the first saved version — no previous version to compare." No iframe, no error, no spinner.
**Why human:** UI state branch for `is_first_commit` response requires browser verification.

#### 4. Save-to-history transition

**Test:** Make a change to a tracked workflow, save from ChangesPanel. Observe what appears after the save completes.
**Expected:** HistoryPanel appears (not SuccessCard). New entry at top shows "just now" and "Latest" badge.
**Why human:** Full save-to-history state transition requires end-to-end live flow.

#### 5. Project-switch resets history

**Test:** View history for project A, then switch to project B.
**Expected:** History list immediately shows project B's history — no stale entries from project A. If project B has no commits, EmptyState shows.
**Why human:** Stale-render detection requires interactive project switching in a running app.

---

## Gaps Summary

No automated gaps. All code-verifiable must-haves are satisfied:

- Backend endpoints exist, are fully implemented, and all 9 tests pass GREEN.
- Frontend components exist, are substantive (not stubs), compile with no TypeScript errors, and are wired into AppShell.
- SuccessCard is removed with no broken imports.
- Zustand store has no LastSave/lastSave/setLastSave remnants.
- Key links (server.py router registration, git_ops import for mock.patch, blob URL pattern, AppShell state machine branches) are all present and connected.

The 5 human verification items above are the only remaining gate — they cover live browser behaviour that cannot be confirmed programmatically.

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
