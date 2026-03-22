# Phase 17: Branch Management - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can create experiment copies of their project (git branches), switch between them, and always see which copy they're working on. No DAG visualization, no merge UI, no conflict resolution. History and diff viewer gain branch-awareness. Phase delivers BRANCH-01, BRANCH-02, BRANCH-03.

</domain>

<decisions>
## Implementation Decisions

### Branch UI location
- Branch label and switcher live **inline in the Changes panel header** — a small chip `[⎇ main ▾]` (or `[⎇ experiment/2026-03-15-... ▾]`)
- Clicking the chip opens a **popover** listing all branches with a checkmark on the active one, and a `+ New experiment` option at the bottom
- Branch label/switcher is in the **Changes panel only** — History and Remote panels do not show it (History passively filters to the active branch; Remote is project-level)
- When on an **experiment branch**: chip uses **amber tint** to signal "you're not on main"; on main the chip is neutral/muted
- In the chip: **truncated** to fit the header (e.g., `experiment/2026-03-...`); in the popover: **full name** shown

### Branch creation flow
- Clicking `+ New experiment` in the popover **expands the popover inline** with a text field and a Create button — no modal
- Placeholder: `e.g. price-calc-test`
- Description is **required** — Create button is disabled until user types something
- As user types, a live preview shows below: `Will be: experiment/2026-03-15-price-calc-test` (spaces → hyphens, lowercased, date auto-inserted)
- After creation: **auto-switch** to the new experiment copy

### Unsaved changes on switch
- If uncommitted file changes exist when user opens the branch popover: **switch is blocked** — branch rows are disabled, warning shown: `⚠ Save changes before switching (X files)`
- After a successful switch: **brief inline status** in the Changes panel header (e.g., `Switched to experiment/...`) that fades after a few seconds — no toast, no modal
- Users can **delete experiment copies** from the popover: each experiment row has a trash icon; main is not deletable
- Deletion uses `git branch -d` (safe delete — refuses if branch has unmerged saves); confirmation dialog explains: "Deleting this experiment copy removes the branch. Files on main are not affected."

### History on experiment branches
- History panel shows **current branch commits only** — filtered to the active branch; switching branches in Changes panel refreshes History
- Diff viewer on experiment branches gains a **compare toggle**: `[● vs previous save] [ vs main ]` — lets user see what their experiment changed relative to the stable baseline. Uses the pre-built `compare_to` param from Phase 14's history API design.
- Phase 16.1's graph view (currently main-branch linear) is **extended to show branching lines** for experiment branches — multi-branch DAG visualization in the graph view when multiple branches exist

### Claude's Discretion
- Exact SVG/CSS implementation of branch lines in the graph view (node size, line thickness, colors)
- Animation/transition when the popover expands to show the text field
- Exact amber shade for experiment chip tint
- How to handle `git branch -d` refusal (unmerged branch) — show informative error or offer force-delete option
- Error handling for checkout failures (git lock files, etc.)

</decisions>

<specifics>
## Specific Ideas

- The branch chip feels like a VS Code-style branch indicator — compact, always visible, clickable
- "Experiment copy" in all user-facing copy — never "branch"
- Live name preview during creation removes the mystery of the auto-generated format
- Graph view branching lines are a natural extension of Phase 16.1's graph view, not a new feature from scratch

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/frontend/src/components/ChangesPanel.tsx`: panel header is the insertion point for the branch chip + popover
- `app/frontend/src/components/HistoryPanel.tsx`: already fetches `/api/history/{project_id}`; extend to pass `branch` param; Phase 16.1 graph view is the base for branching lines extension
- `app/frontend/src/components/DiffViewer.tsx`: add compare toggle (vs previous save | vs main) for experiment branches — calls `compare_to` param on the diff endpoint
- `app/frontend/src/components/AppShell.tsx`: `activeView` state pattern — branch switch triggers a re-fetch in HistoryPanel (same signal mechanism as Phase 16.1's push-completion event)
- `app/services/git_ops.py`: new functions needed — `git_list_branches(folder)`, `git_create_branch(folder, name)`, `git_checkout(folder, branch)`, `git_delete_branch(folder, branch, force=False)`
- `app/frontend/src/store/useProjectStore.ts`: add `activeBranch` field per project (or derive from API on project select)

### Established Patterns
- shadcn/ui + Tailwind for all UI — `Popover` component available in shadcn for the branch switcher
- Self-fetching panels — HistoryPanel re-fetches when branch changes
- Module-level imports in routers for `unittest.mock.patch` compatibility (Phases 11–16 pattern)
- Plain-language copy: "experiment copy" not "branch", "saved versions" not "commits"
- Amber tint pattern follows Phase 16.1's cloud icon badge pattern for status signaling

### Integration Points
- `app/routers/history.py`: `GET /api/history/{project_id}` gains optional `?branch=` query param; history diff endpoint gains `compare_to` param (was already designed in Phase 14)
- `app/services/git_ops.py`: `git_checkout` must check for uncommitted changes before switching (return error, not exception — UI handles the blocking)
- `app/frontend/src/store/useProjectStore.ts`: `activeBranch` state — updated on project select (fetch current branch from API) and on branch switch

</code_context>

<deferred>
## Deferred Ideas

- Pull / merge experiment back to main — own phase; requires conflict resolution UX
- Rename experiment copy — not in v1.1 scope
- Multiple GitHub accounts — unrelated, remains deferred from Phase 16

</deferred>

---

*Phase: 17-branch-management*
*Context gathered: 2026-03-15*
