# Phase 14: History and Diff Viewer - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can browse a flat timeline of saved versions per project (date, message, author) and view the ACD diff report for any version embedded inline in the app. Branch management (Phase 17) and remote viewing are separate phases.

</domain>

<decisions>
## Implementation Decisions

### History panel placement
- History panel is the idle state — replaces Phase 13's SuccessCard placeholder
- State machine for main content area:
  - `changedCount > 0` → ChangesPanel (Phase 13, unchanged)
  - `changedCount = 0, hasCommits` → HistoryPanel (Phase 14)
  - `!hasCommits` → EmptyState (Phase 11, unchanged)
- After a successful save: jump straight to HistoryPanel with the new entry at the top showing "just now" — no intermediate SuccessCard
- Undo last save button moves from SuccessCard to the latest history entry (top of list)
- Project switch while in any view: always reset to history list (or EmptyState) for the newly selected project — consistent with Phase 13 pattern

### History entry display
- Each entry shows: commit message (truncated ~60 chars), relative timestamp ("2 hours ago" / "Mar 13"), author name
- Most recent entry gets a subtle "Latest" pill badge
- Scrollable list, all entries loaded — no pagination (typical team has 10–30 saves)
- Entries are clickable rows; hover state to signal interactivity

### Diff viewer — layout
- Clicking an entry replaces the history list with a full-screen diff view:
  - Header row: "← History  |  [commit message]"
  - "← History" link returns to the history list
  - Below: full-height iframe loading the ACD diff report
- Loading state: centered spinner fills the iframe area while ACD pipeline runs (1–5 sec)
- First entry (no parent commit): clicking shows an explanation message — "This is the first saved version — no previous version to compare." No iframe, no broken state.

### Diff viewer — file selection
- A save can include multiple .yxmd files
- When multiple files were changed in a commit: show a file selector above the iframe (file basenames, e.g. `CustomerReport.yxmd`)
- User selects which file to inspect → iframe loads the diff report for that file
- When only one file was changed: skip the selector, load the report directly

### Diff viewer — backend API
- Phase 14 scope: main branch only — each entry diffs against its parent commit
- Endpoint: `GET /api/history/{sha}/diff?file={filename}` — backend checks out `{sha}` and `{sha}~1`, extracts the specified file, runs `pipeline.run(DiffRequest)`, returns the HTML report
- `GET /api/history/{project_id}` — returns flat list of commits: `[{sha, message, author, timestamp, files_changed: [...]}]`
- API designed for Phase 17 extensibility: endpoint will accept an optional `compare_to` param (branch name or SHA) when cross-branch comparison is added — Phase 14 does not implement this UI

### Claude's Discretion
- Exact shadcn/Tailwind component choices for history entry rows
- Animation/transition when entering and exiting the full-screen diff view
- Relative timestamp formatting and when it switches from "just now" to "X min ago" to "Mar 13"
- Whether the file selector is a dropdown or tab row
- Exact error state if ACD pipeline fails (timeout, corrupt file, etc.)

</decisions>

<specifics>
## Specific Ideas

- Branch-aware comparison vision (Phase 17 preview): on main branch, diff is always vs parent. On an experiment branch, user will get a choice: diff vs previous save on this branch OR diff vs another branch (e.g. main). Phase 14 designs the API to support the `compare_to` extension without rework.
- The "← History" navigation in the diff view is the only back mechanism — no browser history needed since this is a SPA with no URL routing currently.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/frontend/src/components/AppShell.tsx`: conditional rendering pattern already in place — Phase 14 adds `HistoryPanel` as a new branch in `renderMainContent()`, replacing the `lastSave !== null → SuccessCard` branch
- `app/frontend/src/components/SuccessCard.tsx`: Phase 14 removes/replaces this — undo button migrates to the top history entry
- `app/frontend/src/components/ChangesPanel.tsx` / `EmptyState.tsx`: existing sibling components; HistoryPanel follows the same prop/structure pattern
- `app/services/git_ops.py`: needs two new functions — `git_log(folder)` returning flat commit list, and content extraction for diffing (`git show {sha}:{filepath}`)
- `src/pipeline.py` (v1.0 ACD engine): `pipeline.run(DiffRequest)` is the existing diff entry point; Phase 14 calls it server-side from the history diff endpoint
- `app/frontend/src/store/useProjectStore.ts`: Zustand store — `lastSave` field currently drives SuccessCard; Phase 14 replaces this with active diff state (selected SHA + file)

### Established Patterns
- shadcn/ui + Tailwind for all UI components
- FastAPI router modules in `app/routers/` — new `history.py` router follows existing pattern
- Module-level service imports in routers so `unittest.mock.patch` targets work (Phase 11/13 pattern)
- Plain-language copy — no git jargon; "saved version" not "commit", "← History" not "← Back to log"
- AppShell owns all fetch/state; child components receive data as props (Phase 13 pattern)

### Integration Points
- `app/frontend/src/components/AppShell.tsx`: `renderMainContent()` — replace `lastSave !== null` SuccessCard branch with `hasCommits && !selectedDiff → HistoryPanel` and `selectedDiff → DiffViewer`
- `app/routers/` — add `history.py` router; register in `server.py`
- `src/` (v1.0 ACD engine) — called via `pipeline.run(DiffRequest(old_content, new_content))` where content is extracted using `git show`; no changes to v1.0 engine needed

</code_context>

<deferred>
## Deferred Ideas

- Cross-branch comparison UI ("compare to main" selector on experiment branches) — Phase 17 extends the diff viewer with this; Phase 14 API is designed to support it via `compare_to` param
- "Undo any version" (not just last) — not in v1.1 scope; would require cherry-pick or revert logic

</deferred>

---

*Phase: 14-history-and-diff-viewer*
*Context gathered: 2026-03-14*
