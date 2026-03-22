# Phase 13: Save Version - Research

**Researched:** 2026-03-14
**Domain:** Git commit workflow, FastAPI router, React state management, shadcn/ui
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Save dialog design**
- Main content panel is the primary interaction surface — no modal; everything inline
- Panel appears when `changedCount > 0` for the active project; replaces EmptyState
- All changed files pre-checked by default — user unchecks files to exclude
- Filenames shown as basename only (e.g. `CustomerReport.yxmd`) — consistent with sidebar pattern from Phase 11
- Commit message field is always visible inline in the panel (not revealed on click)
- Default placeholder: `What changed? e.g. Updated filter logic`
- Save Version and Discard buttons both live at the bottom of the panel
- Discard respects the file checkboxes — only discards checked files, not all changed files

**Initial commit warning (WATCH-03)**
- When `has_any_commits: false` (from `GET /api/watch/status`): amber/yellow callout card appears above the file list
- Copy: "First version save — This will save all N existing workflows in this folder as your starting point."
- When N is large: file list truncates to first 5 entries + "...and N more" — no full scrollable list
- Placeholder changes for first save: `e.g. Initial version of project workflows` instead of the default diff-focused placeholder

**Post-save state (idle state in Phase 13)**
- After successful save: Changes panel is replaced by a Success card showing:
  - "Saved successfully"
  - Commit message text
  - "N files • just now"
  - [Undo last save] button (right-aligned)
- When watcher detects new changes: Success card is replaced by the Changes panel again
- If no commits ever exist (EmptyState condition): show EmptyState until first save

**Undo last save**
- Undo button lives on the Success card in the main content area
- Confirmation dialog (plain language): "Undo this save? Your workflow files won't change — only this saved version will be removed from the history." with [Cancel] / [Undo Save]
- After successful undo: main area returns to Changes panel (files show as changed again vs git HEAD)
- Underlying git operation: `git reset --soft HEAD~1` — files untouched, commit removed

**Discard changes**
- [Discard] button in the Changes panel — acts on checked files only
- Confirmation dialog: "Discard changes to these N workflows? They'll be moved to .acd-backup — you can recover them from there." with [Cancel] / [Discard]
- After discard: brief success card "Changes discarded — files moved to .acd-backup" with [Dismiss], then transitions to idle state
- `.acd-backup` folder is created in the project root; files copied there before git checkout
- Discard respects the file checkboxes — only discards checked files

### Claude's Discretion
- Exact CSS/shadcn component choices for callout card, success card, and file list
- Animation/transition between panel states (save → success, discard → idle)
- How "just now" timestamp is computed and when it switches to a real time (e.g. "5 min ago")
- Whether Save button is disabled while commit message is empty vs allowed with empty message
- Error handling for git commit failure (network issues, lock files, etc.)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SAVE-01 | User can select changed workflows, write a commit message with placeholder guidance, and save a version | `ChangesPanel` component + `POST /api/save/commit` endpoint + `git_commit_files()` in git_ops.py |
| SAVE-02 | User can undo the last saved version with one click, with confirmation copy explaining file changes are preserved | `SuccessCard` component + `POST /api/save/undo` endpoint + `git reset --soft HEAD~1` in git_ops.py |
| SAVE-03 | Discarding uncommitted changes moves files to a `.acd-backup` folder rather than permanent deletion | `git_discard_files()` helper that copies to `.acd-backup` before `git checkout -- <files>` |
</phase_requirements>

---

## Summary

Phase 13 implements the core save/undo/discard loop. All three requirements operate against an existing git repo that was initialized in Phase 11. The backend needs a new `app/routers/save.py` router with three endpoints: commit, undo, and discard. The frontend needs two new components (`ChangesPanel` and `SuccessCard`) and an updated `AppShell.tsx` conditional render. Both the Checkbox shadcn component (for file selection) and a Textarea component (for commit messages) need to be added.

The git operations are all simple subprocess calls: `git add <files> && git commit -m <msg>` for save, `git reset --soft HEAD~1` for undo, and a copy-to-backup + `git checkout -- <files>` for discard. The critical integration point is badge clearing: after save or discard, `watcher_manager.clear_count(project_id)` must be called so the SSE stream sends a `badge_update` event with count 0, which the existing `useWatchEvents` hook in the frontend will handle automatically.

The panel state machine in AppShell is the primary architectural complexity. Three mutually exclusive states drive what the main content area renders: `changedCount > 0` shows `ChangesPanel`, `changedCount === 0 && hasCommits` shows `SuccessCard`, `!hasCommits && changedCount === 0` shows `EmptyState`. The `hasCommits` flag comes from `GET /api/watch/status` and must be re-fetched after undo (because undo can reduce commits to zero).

**Primary recommendation:** Build backend git functions first, then the save router, then the two new frontend components, wiring AppShell last. This keeps each plan independently testable.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | already installed | Save/undo/discard endpoints | Matches all existing routers |
| subprocess (stdlib) | stdlib | `git add`, `git commit`, `git reset`, `git checkout` | Already used throughout `git_ops.py` |
| shutil (stdlib) | stdlib | `shutil.copy2()` to copy files to `.acd-backup` | Standard Python file copy with metadata |
| shadcn/ui Card | already installed | `ChangesPanel` and `SuccessCard` UI containers | Already used in `EmptyState`, `GitIdentityCard` |
| shadcn/ui AlertDialog | already installed | Undo and Discard confirmation dialogs | Already used in `Sidebar.tsx` and `App.tsx` |
| shadcn/ui Button | already installed | Save Version, Discard, Undo last save buttons | Already used throughout |
| zustand | ^5.0.11 | Frontend state: last save metadata for SuccessCard | Already used for project store |
| React | ^19.2.4 | Component state (`useState`) for checkbox selection | Already in use |

### Supporting — Need Installation
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn Checkbox | current | Per-file selection in ChangesPanel | Required for SAVE-01 file selection UX |
| shadcn Textarea | current | Commit message input field | Required for SAVE-01 message entry |

**Installation:**
```bash
# From app/frontend directory
npx shadcn@latest add checkbox
npx shadcn@latest add textarea
```

Note: `npm legacy-peer-deps=true` is already set globally (Phase 11 decision) — shadcn add commands will resolve peer conflicts automatically.

---

## Architecture Patterns

### Recommended Project Structure — New Files
```
app/
├── routers/
│   └── save.py              # POST /api/save/commit, /undo, /discard
app/
└── services/
    └── git_ops.py           # Add: git_commit_files(), git_undo_last_commit(), git_discard_files()

app/frontend/src/
├── components/
│   ├── ChangesPanel.tsx     # File checklist + message input + Save/Discard buttons
│   └── SuccessCard.tsx      # Post-save state card with Undo button
│   └── AppShell.tsx         # MODIFIED: add conditional render for ChangesPanel/SuccessCard
└── store/
    └── useProjectStore.ts   # MODIFIED: add lastSave state field
```

### Pattern 1: Save Router (FastAPI)
**What:** New router `app/routers/save.py` with three POST endpoints. Each mutates git state and calls `watcher_manager.clear_count()` or triggers rescan.
**When to use:** Any git-mutating operation initiated by the user.
```python
# Source: established pattern from app/routers/projects.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import git_ops
from app.services.watcher_manager import watcher_manager

router = APIRouter(prefix="/api/save", tags=["save"])

class CommitBody(BaseModel):
    project_id: str
    folder: str
    files: list[str]
    message: str

@router.post("/commit")
def commit_version(body: CommitBody) -> dict:
    git_ops.git_commit_files(body.folder, body.files, body.message)
    watcher_manager.clear_count(body.project_id)
    return {"ok": True}
```

### Pattern 2: git_ops Git Functions
**What:** New helper functions in `app/services/git_ops.py` following existing subprocess pattern.
**When to use:** Any new git operation — always go through git_ops, never call git directly in a router.
```python
# Source: established pattern from git_ops.py
import subprocess, shutil
from pathlib import Path

def git_commit_files(folder: str, files: list[str], message: str) -> None:
    """Stage specific files and create a commit."""
    subprocess.run(["git", "-C", folder, "add", "--"] + files,
                   capture_output=True, text=True, check=True)
    subprocess.run(["git", "-C", folder, "commit", "-m", message],
                   capture_output=True, text=True, check=True)

def git_undo_last_commit(folder: str) -> None:
    """Remove the last commit, keep working tree changes (soft reset)."""
    subprocess.run(["git", "-C", folder, "reset", "--soft", "HEAD~1"],
                   capture_output=True, text=True, check=True)

def git_discard_files(folder: str, files: list[str]) -> None:
    """Copy files to .acd-backup, then restore them to HEAD state."""
    backup = Path(folder) / ".acd-backup"
    backup.mkdir(exist_ok=True)
    for rel_path in files:
        src = Path(folder) / rel_path
        if src.exists():
            shutil.copy2(src, backup / src.name)
    # Restore files to HEAD (for tracked files); untracked files just get left in backup
    # Use git checkout for tracked files only
    tracked = [f for f in files if _is_tracked(folder, f)]
    if tracked:
        subprocess.run(["git", "-C", folder, "checkout", "--"] + tracked,
                       capture_output=True, text=True, check=True)
    # Remove untracked files that were copied to backup
    for rel_path in files:
        if not _is_tracked(folder, rel_path):
            src = Path(folder) / rel_path
            if src.exists():
                src.unlink()

def _is_tracked(folder: str, rel_path: str) -> bool:
    """Return True if rel_path is tracked by git (not untracked/new)."""
    r = subprocess.run(
        ["git", "-C", folder, "ls-files", "--error-unmatch", rel_path],
        capture_output=True, text=True,
    )
    return r.returncode == 0
```

### Pattern 3: AppShell State Machine
**What:** `renderMainContent()` in AppShell updated to drive three mutually exclusive states. `hasCommits` comes from watch status API, fetched once per project activation and re-fetched after undo.
**When to use:** Any time active project or changedCount changes.
```tsx
// Source: established pattern from AppShell.tsx renderMainContent()
function renderMainContent() {
  if (showIdentityCard && onIdentitySaved) {
    return <GitIdentityCard ... />
  }
  if (!activeProjectId) {
    return <div>Select a project ...</div>
  }
  if ((activeProject?.changedCount ?? 0) > 0) {
    return <ChangesPanel project={activeProject} onSaved={handleSaved} onDiscarded={handleDiscarded} />
  }
  if (hasCommits) {
    return <SuccessCard lastSave={lastSave} onUndo={handleUndo} />
  }
  return <EmptyState projectName={activeProject?.name} />
}
```

### Pattern 4: Badge Auto-Clear via SSE
**What:** After `POST /api/save/commit` succeeds, backend calls `watcher_manager.clear_count(project_id)`. This pushes a `badge_update` event with `changed_count: 0` to all SSE subscribers. The existing `useWatchEvents` hook in the frontend receives it and calls `setChangedCount(project_id, 0)`. This automatically transitions AppShell from ChangesPanel to SuccessCard.
**Why:** No frontend polling needed; no manual store update needed after commit. The SSE path already wired in Phase 12 handles it.

### Anti-Patterns to Avoid
- **Calling git directly in router:** All git operations must go through `git_ops.py` — keeps routers testable via `patch("app.routers.save.git_ops.git_commit_files", ...)`.
- **Using `git checkout .` for discard:** Discards ALL files. Use `git checkout -- <specific files>` to respect user's checkbox selection.
- **Deleting untracked files with os.remove before backup:** Always copy to `.acd-backup` FIRST, then remove/checkout.
- **Using `git reset --hard` for undo:** Hard reset destroys working tree changes. The decision is `--soft` only.
- **Staging all files with `git add .`:** Only stage the explicitly selected files. User may have deliberately unchecked some files.
- **Updating changedCount in frontend after commit manually:** Let SSE badge_update handle it — avoids dual-source-of-truth bugs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File copy with metadata | Custom file copy loop | `shutil.copy2()` | Preserves timestamps, handles permissions |
| Checkbox UI | Custom `<input type="checkbox">` | `shadcn Checkbox` | Accessible, keyboard-navigable, consistent with design system |
| Multi-line text input | `<input>` with CSS | `shadcn Textarea` | Correct semantics, accessible, auto-resize variants |
| Badge clear after commit | Frontend timer or poll | `watcher_manager.clear_count()` + SSE | Existing SSE path; watcher will also re-trigger on next file event |
| Confirmation dialogs | Custom modal | `shadcn AlertDialog` | Already installed and used in Sidebar.tsx |

**Key insight:** The watcher_manager already has `clear_count()` (line 159-165 of watcher_manager.py) specifically built for Phase 13. Use it — no custom SSE event type needed.

---

## Common Pitfalls

### Pitfall 1: Undo When No Commits Exist
**What goes wrong:** Calling `git reset --soft HEAD~1` on a repo with only one commit exits with error 128 (cannot reset — no parent commit).
**Why it happens:** After the initial commit is undone, HEAD~1 doesn't exist.
**How to avoid:** Before calling undo, verify `git_has_commits()` AND check if there is more than one commit. Simpler: catch `subprocess.CalledProcessError` and return a 400 with a user-facing message.
**Warning signs:** The undo button should not appear if `lastSave` is the very first commit — but since Phase 13 doesn't track commit depth, guard server-side.

### Pitfall 2: Untracked Files and `git checkout`
**What goes wrong:** `git checkout -- untracked_file.yxmd` returns an error because the file has no HEAD version to restore to.
**Why it happens:** `git checkout --` works only for tracked files. New/untracked files show as `??` in `git status --porcelain`.
**How to avoid:** Use `_is_tracked()` helper before calling checkout; untracked files should be deleted from working dir (after backup). The `git_changed_workflows()` function already includes untracked files (line 63 in git_ops.py parses both `??` and `M` prefix lines).

### Pitfall 3: File Paths Are Relative to Repo Root
**What goes wrong:** `git_changed_workflows()` returns relative paths (e.g. `subdir/workflow.yxmd`). `git checkout -- subdir/workflow.yxmd` works. But `shutil.copy2(Path(folder) / rel_path, backup / Path(rel_path).name)` may conflict if two files in different subdirs share the same basename.
**Why it happens:** `.acd-backup` is flat — all files go into one folder.
**How to avoid:** For the `.acd-backup` copy, use `Path(rel_path).name` as backup filename; document that name collision is possible but acceptable for v1 (users can recover from backup folder manually). For `git checkout --`, pass the relative path exactly as returned by `git_changed_workflows()`.

### Pitfall 4: shadcn Checkbox Not Yet Installed
**What goes wrong:** Importing `@/components/ui/checkbox` fails at build time.
**Why it happens:** The component was referenced in CONTEXT.md but is not in `app/frontend/src/components/ui/` (only 5 components exist: alert-dialog, button, card, context-menu, input).
**How to avoid:** Wave 0 task must run `npx shadcn@latest add checkbox textarea` before any component code is written.

### Pitfall 5: `git commit` Fails with "nothing to commit"
**What goes wrong:** If all selected files are already staged/committed, `git commit` exits with code 1 and the router returns a 500.
**Why it happens:** `git_changed_workflows()` returned files, but between the panel load and the save button click, the watcher may not have re-run.
**How to avoid:** Wrap `git_commit_files` in try/except `subprocess.CalledProcessError`; if returncode is 1 and stderr contains "nothing to commit", return a 409 or 200 with `{"ok": true, "nothing_changed": true}` rather than a 500.

### Pitfall 6: `has_any_commits` Stale After Undo
**What goes wrong:** After undo, AppShell still shows `SuccessCard` because `hasCommits` is cached in frontend state from the initial watch status fetch.
**Why it happens:** `hasCommits` must be re-fetched from `GET /api/watch/status` after a successful undo operation.
**How to avoid:** In the `handleUndo` success path in AppShell (or ChangesPanel parent), call `GET /api/watch/status` again to refresh `hasCommits`. Alternatively, the undo endpoint response can include `has_any_commits: bool`.

---

## Code Examples

Verified patterns from existing codebase:

### Existing `watcher_manager.clear_count()` (already built for Phase 13)
```python
# Source: app/services/watcher_manager.py lines 159-165
def clear_count(self, project_id: str) -> None:
    """Zero the change count for *project_id* and push an SSE event.

    Called by Phase 13 after a successful git commit so the badge resets.
    """
    self._change_counts[project_id] = 0
    self._push_badge_update(project_id, 0)
```

### Router Registration Pattern (must add to server.py)
```python
# Source: app/server.py lines 17-18 and 46-49 — add save router the same way
from app.routers import folder_picker, git_identity, projects, watch, save

app.include_router(save.router)
```

### AlertDialog Pattern (Discard confirmation)
```tsx
// Source: app/frontend/src/components/Sidebar.tsx lines 85-99
<AlertDialog open={confirmDiscard !== null} onOpenChange={(open) => !open && setConfirmDiscard(null)}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Discard changes to these {checkedFiles.length} workflows?</AlertDialogTitle>
      <AlertDialogDescription>
        They'll be moved to .acd-backup — you can recover them from there.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDiscardConfirm}>Discard</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

### Existing `git_changed_workflows()` Output Format
```python
# Source: app/services/git_ops.py lines 51-74
# Returns relative paths like: ["CustomerReport.yxmd", "subdir/Pipeline.yxwz"]
# Basename display: use Path(rel_path).name → "CustomerReport.yxmd"
# git operations: pass full relative path → git checkout -- subdir/Pipeline.yxwz
```

### Zustand Store Extension Pattern
```typescript
// Source: app/frontend/src/store/useProjectStore.ts
// Add lastSave state alongside existing project state
interface LastSave {
  message: string
  fileCount: number
  savedAt: Date
}
// Either extend useProjectStore or create a new useSaveStore with same create() pattern
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `git add .` (all files) | `git add -- <specific files>` | Phase 13 decision | Respects user's checkbox selection |
| `git reset --hard` | `git reset --soft HEAD~1` | Phase 13 decision | Preserves working tree; user never loses file changes |
| Permanent delete for discard | Copy to `.acd-backup` first | Phase 13 SAVE-03 | No data loss on discard |
| Modal dialog for save | Inline panel (no modal) | Phase 13 decision | Less disruptive; Figma-like model |

**Deprecated/outdated:**
- AppShell showing `EmptyState` for any active project: After Phase 13, `EmptyState` only shows when `!hasCommits && changedCount === 0`. The previous default of always showing EmptyState for `activeProjectId` is replaced by the three-state conditional.

---

## Open Questions

1. **Textarea vs Input for commit message**
   - What we know: CONTEXT.md says "commit message field is always visible inline" — single vs multi-line not specified
   - What's unclear: Whether analysts will write multi-line commit messages
   - Recommendation: Use shadcn Textarea (2-3 rows) — allows multi-line without forcing it; Claude's discretion per CONTEXT.md

2. **Save button enabled/disabled state with empty message**
   - What we know: Left to Claude's discretion in CONTEXT.md
   - What's unclear: Whether UX is better with enabled+warning or disabled+tooltip
   - Recommendation: Allow save with empty message (no validation); empty message commits as "Save" or similar — avoids friction for non-technical Alteryx users who may not know what to write

3. **"just now" → relative time transition**
   - What we know: Left to Claude's discretion
   - Recommendation: Use `Date.now()` comparison; show "just now" for first 60 seconds, then switch to "X min ago" using a `setInterval(, 30000)` in SuccessCard. No external library needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pytest.ini (root) |
| Quick run command | `pytest tests/test_save.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAVE-01 | `git_commit_files()` stages and commits selected files only | unit | `pytest tests/test_save.py::test_git_commit_files -x` | ❌ Wave 0 |
| SAVE-01 | `POST /api/save/commit` returns 200 and calls `watcher_manager.clear_count` | unit | `pytest tests/test_save.py::test_commit_endpoint -x` | ❌ Wave 0 |
| SAVE-01 | `POST /api/save/commit` with empty files list returns 400 | unit | `pytest tests/test_save.py::test_commit_empty_files -x` | ❌ Wave 0 |
| SAVE-02 | `git_undo_last_commit()` soft-resets without changing file content | unit | `pytest tests/test_save.py::test_git_undo_last_commit -x` | ❌ Wave 0 |
| SAVE-02 | `POST /api/save/undo` returns 200 and re-enables badge | unit | `pytest tests/test_save.py::test_undo_endpoint -x` | ❌ Wave 0 |
| SAVE-03 | `git_discard_files()` copies files to `.acd-backup` before removing | unit | `pytest tests/test_save.py::test_git_discard_files_backup -x` | ❌ Wave 0 |
| SAVE-03 | `git_discard_files()` restores tracked file to HEAD state | unit | `pytest tests/test_save.py::test_git_discard_files_restore -x` | ❌ Wave 0 |
| SAVE-03 | `git_discard_files()` removes (not restores) untracked files | unit | `pytest tests/test_save.py::test_git_discard_untracked -x` | ❌ Wave 0 |
| SAVE-03 | `POST /api/save/discard` returns 200 and clears badge | unit | `pytest tests/test_save.py::test_discard_endpoint -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_save.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_save.py` — covers all SAVE-01, SAVE-02, SAVE-03 backend tests listed above
- [ ] `npx shadcn@latest add checkbox textarea` in `app/frontend/` — required before ChangesPanel can be written

*(Existing `tests/conftest.py` and shared fixtures are sufficient — no new conftest needed)*

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `app/services/git_ops.py` — subprocess pattern for all new git functions
- Existing codebase: `app/services/watcher_manager.py` — `clear_count()` already implemented for Phase 13
- Existing codebase: `app/routers/projects.py` — router/Pydantic model pattern to replicate
- Existing codebase: `app/frontend/src/store/useProjectStore.ts` — Zustand store extension pattern
- Existing codebase: `app/frontend/src/components/Sidebar.tsx` — AlertDialog usage pattern
- Existing codebase: `app/frontend/src/components/AppShell.tsx` — `renderMainContent()` pattern to extend
- git documentation: `git reset --soft HEAD~1` (soft reset semantics)
- git documentation: `git checkout -- <files>` (file restore semantics)

### Secondary (MEDIUM confidence)
- shadcn/ui docs: Checkbox and Textarea components available via `npx shadcn@latest add`
- Python stdlib: `shutil.copy2()` preserves file metadata on copy

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed except Checkbox/Textarea (both standard shadcn); verified from package.json and existing component files
- Architecture: HIGH — patterns directly derived from existing codebase (projects.py, git_ops.py, AppShell.tsx)
- Pitfalls: HIGH — derived from git documentation and direct inspection of `git_changed_workflows()` parsing logic for untracked vs tracked file distinction
- Validation: HIGH — existing pytest infrastructure is complete; only new test file needed

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable stack — shadcn, FastAPI, React versions unlikely to change)
