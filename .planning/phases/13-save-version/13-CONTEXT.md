# Phase 13: Save Version - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can intentionally save named versions of changed workflows, undo the last save, and safely discard uncommitted changes. This is the core version control loop. History timeline (Phase 14), remote push (Phase 16), and branch management (Phase 17) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Save dialog design
- Main content panel is the primary interaction surface — no modal; everything inline
- Panel appears when `changedCount > 0` for the active project; replaces EmptyState
- All changed files pre-checked by default — user unchecks files to exclude
- Filenames shown as basename only (e.g. `CustomerReport.yxmd`) — consistent with sidebar pattern from Phase 11
- Commit message field is always visible inline in the panel (not revealed on click)
- Default placeholder: `What changed? e.g. Updated filter logic`
- Save Version and Discard buttons both live at the bottom of the panel
- Discard respects the file checkboxes — only discards checked files, not all changed files

### Initial commit warning (WATCH-03)
- When `has_any_commits: false` (from `GET /api/watch/status`): amber/yellow callout card appears above the file list
- Copy: "First version save — This will save all N existing workflows in this folder as your starting point."
- When N is large: file list truncates to first 5 entries + "...and N more" — no full scrollable list
- Placeholder changes for first save: `e.g. Initial version of project workflows` instead of the default diff-focused placeholder

### Post-save state (idle state in Phase 13)
- After successful save: Changes panel is replaced by a Success card showing:
  - "Saved successfully"
  - Commit message text
  - "N files • just now"
  - [Undo last save] button (right-aligned)
- When watcher detects new changes: Success card is replaced by the Changes panel again
- If no commits ever exist (EmptyState condition): show EmptyState until first save

### Undo last save
- Undo button lives on the Success card in the main content area
- Confirmation dialog (plain language): "Undo this save? Your workflow files won't change — only this saved version will be removed from the history." with [Cancel] / [Undo Save]
- After successful undo: main area returns to Changes panel (files show as changed again vs git HEAD)
- Underlying git operation: `git reset --soft HEAD~1` — files untouched, commit removed

### Discard changes
- [Discard] button in the Changes panel — acts on checked files only
- Confirmation dialog: "Discard changes to these N workflows? They'll be moved to .acd-backup — you can recover them from there." with [Cancel] / [Discard]
- After discard: brief success card "Changes discarded — files moved to .acd-backup" with [Dismiss], then transitions to idle state (Success card if previous save exists, EmptyState if no saves yet)
- `.acd-backup` folder is created in the project root; files copied there before git checkout

### Claude's Discretion
- Exact CSS/shadcn component choices for callout card, success card, and file list
- Animation/transition between panel states (save → success, discard → idle)
- How "just now" timestamp is computed and when it switches to a real time (e.g. "5 min ago")
- Whether Save button is disabled while commit message is empty vs allowed with empty message
- Error handling for git commit failure (network issues, lock files, etc.)

</decisions>

<specifics>
## Specific Ideas

- The Changes panel should feel like Figma's "Unsaved changes" indicator — actionable without being alarming
- "Files moved to .acd-backup" is the key safety message — users should never fear data loss from Discard
- Undo confirmation uses "version record" framing — avoids "commit" jargon; keeps it plain-language per Phase 11 pattern

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/git_ops.py`: `git_changed_workflows(folder)` returns list of changed file paths — drives the file list in the Changes panel
- `app/services/git_ops.py`: `git_has_commits(folder)` — determines whether to show the initial commit callout
- `app/routers/watch.py`: `GET /api/watch/status` returns `{changed_count, total_workflows, has_any_commits}` per project — call this at panel load time
- `app/frontend/src/store/useProjectStore.ts`: `Project.changedCount` field + `setChangedCount()` action already in Zustand store — badge clearing after save hooks into this
- `app/frontend/src/components/EmptyState.tsx`: existing empty-state card — shown until first save, and as fallback after discard with no commits
- `app/frontend/src/components/Sidebar.tsx`: amber badge already renders from `changedCount` — needs to clear (set to 0) after successful save or discard

### Established Patterns
- shadcn/ui + Tailwind for all UI — Card, Button, Checkbox, AlertDialog (for confirmations) all available
- Zustand store for project state — new save/discard actions go in `useProjectStore` or a new `useSaveStore`
- FastAPI router modules in `app/routers/` — new `save.py` router follows existing pattern
- Plain-language copy throughout — no git jargon (Phase 11 constraint)

### Integration Points
- `app/routers/watch.py` / `watcher_manager.py`: after successful commit, watcher re-scans via `git status --porcelain` — badge clears automatically OR save router calls `setChangedCount(id, 0)` via SSE event
- `app/frontend/src/AppShell.tsx`: main content area routing — Phase 13 adds conditional rendering: `changedCount > 0 → ChangesPanel`, `changedCount === 0 && hasCommits → SuccessCard`, `!hasCommits → EmptyState`
- Phase 14 (History): will replace SuccessCard with a full history timeline; Phase 13's SuccessCard is a temporary placeholder for that slot

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-save-version*
*Context gathered: 2026-03-14*
