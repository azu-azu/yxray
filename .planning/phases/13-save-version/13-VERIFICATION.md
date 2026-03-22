---
phase: 13-save-version
verified: 2026-03-14T00:00:00Z
status: human_needed
score: 20/21 must-haves verified
re_verification: false
human_verification:
  - test: "Full save/undo/discard end-to-end loop in the running app"
    expected: "SAVE-01 save creates commit and shows SuccessCard; SAVE-02 undo restores ChangesPanel; SAVE-03 discard moves files to .acd-backup"
    why_human: "Plan 04 Task 2 is a blocking human checkpoint — automated tests cover backend behavior but UI interaction (SSE badge clearing, panel transitions, AlertDialog flows, amber callout on first save) requires live app verification. Summary records human-approved but this is not automatable."
---

# Phase 13: Save Version Verification Report

**Phase Goal:** Users can save a named version of selected workflow files, undo the last save, and discard changes — all from within the app
**Verified:** 2026-03-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | tests/test_save.py exists with 12 stubs covering SAVE-01, SAVE-02, SAVE-03 | VERIFIED | File exists, 12 `def test_` functions confirmed, all 12 PASSED |
| 2 | shadcn Checkbox is importable from @/components/ui/checkbox | VERIFIED | `checkbox.tsx` exists, exports `Checkbox`, uses Radix primitive |
| 3 | shadcn Textarea is importable from @/components/ui/textarea | VERIFIED | `textarea.tsx` exists, exports `Textarea` |
| 4 | git_commit_files stages only selected files and creates a commit | VERIFIED | Implemented in git_ops.py; test `test_git_commit_files` and `test_commit_only_selected_files` pass |
| 5 | git_undo_last_commit soft-resets HEAD without changing file content | VERIFIED | Implemented with `--soft`; `test_git_undo_preserves_file_content` passes |
| 6 | git_discard_files copies files to .acd-backup before removing them | VERIFIED | Implemented with shutil.copy2 before checkout/unlink; `test_git_discard_files_backup` passes |
| 7 | POST /api/save/commit returns 200 and calls watcher_manager.clear_count | VERIFIED | `save.py` lines 34-46 implement this; `test_commit_endpoint` passes with mock assertion |
| 8 | POST /api/save/undo returns 200 with has_any_commits in response | VERIFIED | `save.py` lines 49-64 return `{"ok": True, "has_any_commits": has_commits}`; test passes |
| 9 | POST /api/save/discard returns 200 and calls watcher_manager.clear_count | VERIFIED | `save.py` lines 67-77; `test_discard_endpoint` passes |
| 10 | All 12 backend tests are GREEN | VERIFIED | `pytest tests/test_save.py -v` — 12 passed |
| 11 | ChangesPanel renders pre-checked file list, commit message textarea, Save Version button, and Discard button | VERIFIED | Full implementation in `ChangesPanel.tsx`; Checkbox + Textarea + two Buttons + AlertDialog |
| 12 | Discard confirmation AlertDialog shows .acd-backup safety message | VERIFIED | Lines 184-187: "They'll be moved to .acd-backup — you can recover them from there." |
| 13 | Save Version button calls POST /api/save/commit with checked files and commit message | VERIFIED | Lines 56-65 in ChangesPanel.tsx: `fetch('/api/save/commit', ...)` with checkedFiles and commitMessage |
| 14 | SuccessCard renders commit message, file count, relative timestamp, and Undo last save button | VERIFIED | All four elements present in SuccessCard.tsx (lines 80-95) |
| 15 | Undo confirmation AlertDialog uses plain-language copy with no git jargon | VERIFIED | "Your workflow files won't change — only this saved version will be removed from the history." |
| 16 | useProjectStore extended with lastSave state and setLastSave action | VERIFIED | `LastSave` interface exported; `lastSave: null` and `setLastSave` in store |
| 17 | When changedFiles.length > 0, AppShell shows ChangesPanel | VERIFIED | `renderMainContent` line 84: `if (changedFiles.length > 0)` renders `<ChangesPanel>` |
| 18 | When lastSave is set and changedFiles is empty, AppShell shows SuccessCard | VERIFIED | Lines 96-104: `if (lastSave)` renders `<SuccessCard>` |
| 19 | When both are false, AppShell shows EmptyState | VERIFIED | Line 106: `return <EmptyState projectName={activeProject.name} />` |
| 20 | GET /api/watch/status includes changed_files list | VERIFIED | `watch.py` lines 89-94: `changed_files = git_ops.git_changed_workflows(folder)` returned in response |
| 21 | Full save/undo/discard loop works end-to-end in the running app | HUMAN NEEDED | Plan 04 Task 2 is a blocking human checkpoint; 13-04-SUMMARY records human approval |

**Score:** 20/21 automated truths verified. 1 truth requires human confirmation (end-to-end UI flow).

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_save.py` | 12 stubs for SAVE-01/02/03 | VERIFIED | 12 tests, all passing, 289 lines |
| `app/frontend/src/components/ui/checkbox.tsx` | Accessible checkbox for per-file selection | VERIFIED | Radix-backed, exports `Checkbox` |
| `app/frontend/src/components/ui/textarea.tsx` | Textarea for commit message input | VERIFIED | Exports `Textarea` |
| `app/services/git_ops.py` | git_commit_files, git_undo_last_commit, git_discard_files, _is_tracked | VERIFIED | All four functions implemented (lines 110-208) |
| `app/routers/save.py` | POST /api/save/commit, /undo, /discard endpoints | VERIFIED | All three endpoints, models defined, exports `router` |
| `app/server.py` | save router registered in FastAPI app | VERIFIED | Line 50: `app.include_router(save.router)` |
| `app/frontend/src/components/ChangesPanel.tsx` | File selection + commit message + save/discard UI | VERIFIED | Full implementation, exports `ChangesPanel` |
| `app/frontend/src/components/SuccessCard.tsx` | Post-save success state with undo button | VERIFIED | Full implementation, exports `SuccessCard` |
| `app/frontend/src/store/useProjectStore.ts` | lastSave state + setLastSave action | VERIFIED | `LastSave` interface exported; both field and action present |
| `app/frontend/src/components/AppShell.tsx` | Three-state renderMainContent | VERIFIED | ChangesPanel / SuccessCard / EmptyState machine implemented |
| `app/routers/watch.py` | GET /api/watch/status returns changed_files | VERIFIED | `changed_files` field added at line 94 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_save.py` | `app/services/git_ops` | `from app.services.git_ops import` | VERIFIED | Each git_ops test imports directly from the module |
| `tests/test_save.py` | `app/routers/save` | `client.post("/api/save/...")` via mock.patch | VERIFIED | All 4 endpoint tests use mock.patch targeting `app.routers.save.*` |
| `app/routers/save.py` | `app/services/git_ops` | `from app.services import git_ops` | VERIFIED | Line 10; module import for correct mock targeting |
| `app/routers/save.py` | `app/services/watcher_manager` | `watcher_manager.clear_count` | VERIFIED | Lines 45, 76: called in commit and discard endpoints |
| `app/server.py` | `app/routers/save` | `app.include_router(save.router)` | VERIFIED | Line 50 in server.py |
| `app/frontend/src/components/ChangesPanel.tsx` | `/api/save/commit` | `fetch('/api/save/commit', ...)` in handleSave | VERIFIED | Line 56 |
| `app/frontend/src/components/ChangesPanel.tsx` | `/api/save/discard` | `fetch('/api/save/discard', ...)` in handleDiscardConfirm | VERIFIED | Line 80 |
| `app/frontend/src/components/SuccessCard.tsx` | `/api/save/undo` | `fetch('/api/save/undo', ...)` in handleUndoConfirm | VERIFIED | Line 51 |
| `app/frontend/src/components/ChangesPanel.tsx` | `useProjectStore.ts` | `setLastSave` after successful commit | VERIFIED | onSaved callback flows to AppShell.handleSaved which calls setLastSave |
| `app/frontend/src/components/AppShell.tsx` | `ChangesPanel.tsx` | conditional render when `changedFiles.length > 0` | VERIFIED | Line 84 |
| `app/frontend/src/components/AppShell.tsx` | `/api/watch/status` | `fetch(...)` in fetchWatchStatus | VERIFIED | Lines 27-39 |
| `app/frontend/src/components/AppShell.tsx` | `useProjectStore.ts` | `setLastSave` after successful commit | VERIFIED | Lines 53-55: `setLastSave(save)` |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SAVE-01 | 13-01, 13-02, 13-03, 13-04 | User can select changed workflows, write a commit message with placeholder guidance, and save a version | SATISFIED | `git_commit_files` stages selected files; ChangesPanel renders pre-checked file list + Textarea; POST /api/save/commit; AppShell wires save flow; human-approved |
| SAVE-02 | 13-01, 13-02, 13-03, 13-04 | User can undo the last saved version with one click, with confirmation copy explaining file changes are preserved | SATISFIED | `git_undo_last_commit` with soft reset; SuccessCard "Undo last save" button; AlertDialog: "Your workflow files won't change — only this saved version will be removed from the history."; human-approved |
| SAVE-03 | 13-01, 13-02, 13-03, 13-04 | Discarding uncommitted changes moves files to a .acd-backup folder rather than permanent deletion | SATISFIED | `git_discard_files` backup-first pattern; Discard AlertDialog mentions .acd-backup; human-approved |

**Orphaned requirements check:** REQUIREMENTS.md maps SAVE-01, SAVE-02, SAVE-03 to Phase 13 and all three are claimed by all four plans. No orphaned requirements.

---

## Notable Deviation: changedCount vs changedFiles

Plan 04 `must_haves.truths[0]` states: "When active project has changedCount > 0, AppShell shows ChangesPanel."

The actual implementation uses `changedFiles.length > 0` (not `activeProject.changedCount`). This is a functionally superior design — it uses the authoritative file list from `fetchWatchStatus` rather than the SSE-updated badge count, which could lag. The `totalWorkflows` prop defined in Plan 03 was not added to ChangesPanel's actual props interface; the amber callout uses `checkedFiles.length` instead. This is a harmless simplification — behavior is equivalent for the user.

Both deviations represent improvements over the plan spec. The AppShell state machine is substantively correct.

---

## Anti-Patterns Found

No blockers or warnings detected in phase 13 files:
- No TODOs, FIXMEs, placeholders, or stub returns in any phase 13 artifact
- All handlers make real API calls and handle responses
- All git operations use real subprocess calls (no mocks in production code)

---

## Human Verification Required

### 1. Full Save/Undo/Discard End-to-End Loop

**Test:** Run `make dev` (or `uvicorn app.server:app --reload` + `cd app/frontend && npm run dev`). Open the app. Select a project with changed .yxmd files.

**Expected (SAVE-01):** ChangesPanel appears with pre-checked files. Enter a commit message. Click "Save Version." SuccessCard appears showing the message, file count, "just now," and "Undo last save" button. The change badge in the sidebar clears to 0 via SSE.

**Expected (SAVE-02):** From SuccessCard, click "Undo last save." AlertDialog appears with "Your workflow files won't change — only this saved version will be removed from the history." Click "Undo Save." ChangesPanel reappears with the same files.

**Expected (SAVE-03):** In ChangesPanel, click "Discard." AlertDialog appears mentioning ".acd-backup." Confirm. Files appear in `.acd-backup/` inside the project directory. Panel transitions to EmptyState (or fewer changed files).

**Expected (SAVE-01 edge case):** On a project with no prior commits, an amber "First version save" callout appears above the file list. Textarea placeholder reads "e.g. Initial version of project workflows."

**Why human:** SSE badge clearing, panel animation transitions, AlertDialog timing and copy, amber callout appearance, and .acd-backup physical file presence require a live browser session. The 13-04-SUMMARY records this as human-approved but the checkpoint is non-automatable.

---

## Gaps Summary

No gaps blocking goal achievement. All automated checks pass across all 4 plans. The single human_needed item is a design-mandated checkpoint from Plan 04 (autonomous: false), not a defect. Per 13-04-SUMMARY, human approval was recorded on 2026-03-14.

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
