# Phase 17: Branch Management - Research

**Researched:** 2026-03-15
**Domain:** Git branch operations (Python subprocess) + React popover UI (shadcn/ui + Tailwind v4)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Branch UI location:**
- Branch label and switcher live inline in the Changes panel header — a small chip `[⎇ main ▾]` (or `[⎇ experiment/2026-03-15-... ▾]`)
- Clicking the chip opens a popover listing all branches with a checkmark on the active one, and a `+ New experiment` option at the bottom
- Branch label/switcher is in the Changes panel only — History and Remote panels do not show it (History passively filters to the active branch; Remote is project-level)
- When on an experiment branch: chip uses amber tint to signal "you're not on main"; on main the chip is neutral/muted
- In the chip: truncated to fit the header (e.g., `experiment/2026-03-...`); in the popover: full name shown

**Branch creation flow:**
- Clicking `+ New experiment` in the popover expands the popover inline with a text field and a Create button — no modal
- Placeholder: `e.g. price-calc-test`
- Description is required — Create button is disabled until user types something
- As user types, a live preview shows below: `Will be: experiment/2026-03-15-price-calc-test` (spaces → hyphens, lowercased, date auto-inserted)
- After creation: auto-switch to the new experiment copy

**Unsaved changes on switch:**
- If uncommitted file changes exist when user opens the branch popover: switch is blocked — branch rows are disabled, warning shown: `⚠ Save changes before switching (X files)`
- After a successful switch: brief inline status in the Changes panel header (e.g., `Switched to experiment/...`) that fades after a few seconds — no toast, no modal
- Users can delete experiment copies from the popover: each experiment row has a trash icon; main is not deletable
- Deletion uses `git branch -d` (safe delete — refuses if branch has unmerged saves); confirmation dialog explains: "Deleting this experiment copy removes the branch. Files on main are not affected."

**History on experiment branches:**
- History panel shows current branch commits only — filtered to the active branch; switching branches in Changes panel refreshes History
- Diff viewer on experiment branches gains a compare toggle: `[● vs previous save] [ vs main ]` — lets user see what their experiment changed relative to the stable baseline. Uses the pre-built `compare_to` param from Phase 14's history API design.
- Phase 16.1's graph view (currently main-branch linear) is extended to show branching lines for experiment branches — multi-branch DAG visualization in the graph view when multiple branches exist

### Claude's Discretion
- Exact SVG/CSS implementation of branch lines in the graph view (node size, line thickness, colors)
- Animation/transition when the popover expands to show the text field
- Exact amber shade for experiment chip tint
- How to handle `git branch -d` refusal (unmerged branch) — show informative error or offer force-delete option
- Error handling for checkout failures (git lock files, etc.)

### Deferred Ideas (OUT OF SCOPE)
- Pull / merge experiment back to main — own phase; requires conflict resolution UX
- Rename experiment copy — not in v1.1 scope
- Multiple GitHub accounts — unrelated, remains deferred from Phase 16
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BRANCH-01 | User can create an experiment copy (branch) with auto-generated name (experiment/YYYY-MM-DD-description) | `git_create_branch` + name formatting function in Python; description → hyphen-slug; name preview in React UI |
| BRANCH-02 | User can switch between experiment copies | `git_checkout` in git_ops.py; API endpoints for list/switch; `activeBranch` in useProjectStore; HistoryPanel re-fetches on branch change |
| BRANCH-03 | Current workspace shown as a label in the UI (no DAG visualization) | Branch chip in ChangesPanel header; amber tint for experiment branches; flat label, no graph DAG of branches |
</phase_requirements>

---

## Summary

Phase 17 adds git branch management to the existing FastAPI + React app. The backend work is four new `git_ops.py` functions (`git_list_branches`, `git_create_branch`, `git_checkout`, `git_delete_branch`) plus a new `branch.py` router registered in `server.py`. The frontend work is a branch chip + popover in `ChangesPanel.tsx`, `activeBranch` state in `useProjectStore.ts`, re-fetch wiring in `AppShell.tsx`, a `?branch=` query param on the history endpoint, and a compare toggle in `DiffViewer.tsx`.

The shadcn `Popover` component is not yet installed — it requires `@radix-ui/react-popover`. The `AlertDialog` component already exists and is the correct component for the delete confirmation. The existing `git_push` pattern (GIT_ASKPASS temp script, module-level imports for mock.patch) and the `lastPushTimestamp`-as-signal pattern for cross-component refresh both apply directly to this phase.

The multi-branch SVG extension to `GraphView` in `HistoryPanel.tsx` requires identifying which commits belong to which branch via `git log --decorate` or per-branch log queries. The existing `GraphView` renders a single linear column; branching adds a second column for experiment-branch commits with connecting lines to the shared ancestor.

**Primary recommendation:** Implement in four plans — (1) backend git_ops functions + branch router with tests, (2) ChangesPanel branch chip + popover with create/switch/delete wiring, (3) HistoryPanel branch-aware filtering + compare toggle in DiffViewer, (4) GraphView multi-branch SVG extension + verification.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess (stdlib) | Python 3.11+ | Git CLI execution | Established pattern in git_ops.py throughout all prior phases |
| FastAPI + APIRouter | >=0.111 | New branch router | Same pattern as all other routers (history.py, save.py, remote.py) |
| shadcn/ui Popover | via @radix-ui/react-popover | Branch chip dropdown | Not yet installed; required for the branch switcher popover |
| shadcn/ui AlertDialog | already installed | Delete confirmation dialog | Already used in ChangesPanel for discard confirm |
| Tailwind v4 (amber) | ^4.2.1 | Chip tint for experiment branches | amber-50/amber-400 already used in ChangesPanel first-save warning |
| Zustand | ^5.0.11 | activeBranch per project | useProjectStore already owns project state |
| lucide-react | ^0.577.0 | Icons (Trash2, GitBranch, Check) | Already in use for Cloud icon in HistoryPanel |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @radix-ui/react-popover | ^1.x | Popover primitive for Shadcn | Required for branch chip dropdown; not yet in package.json |
| Input (shadcn) | already available via @radix-ui/react-slot | Text field for branch description | May reuse existing `input.tsx` if present, or use basic `<input>` |

**Installation (new package only):**
```bash
cd app/frontend && npx shadcn@latest add popover
```
This adds `@radix-ui/react-popover` to package.json and creates `src/components/ui/popover.tsx`.

Note: shadcn CLI resolves `@/` literally — move generated `@/components/ui/popover.tsx` to `src/components/ui/popover.tsx` per the established alias pattern (documented in STATE.md for Phases 11, 13, 15, 16).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| shadcn Popover | Custom dropdown div with useState | Popover handles focus trap, keyboard nav, click-outside; don't hand-roll |
| shadcn Popover | shadcn DropdownMenu | DropdownMenu is for actions; Popover is for interactive content that expands (the inline create form) |

## Architecture Patterns

### Recommended Project Structure — New Files
```
app/
├── routers/
│   └── branch.py          # NEW: /api/branch/* endpoints
├── services/
│   └── git_ops.py         # EXTEND: 4 new functions
app/frontend/src/
├── components/
│   ├── ChangesPanel.tsx    # EXTEND: branch chip + popover in header
│   ├── HistoryPanel.tsx    # EXTEND: ?branch= param, compare toggle
│   └── DiffViewer.tsx      # EXTEND: compare toggle (vs previous / vs main)
│   └── ui/
│       └── popover.tsx     # NEW: shadcn Popover component
├── store/
│   └── useProjectStore.ts  # EXTEND: activeBranch field per project
tests/
└── test_branch.py          # NEW: backend branch tests
```

### Pattern 1: git_ops.py New Functions (subprocess pattern)
**What:** Four new functions following the exact style of existing git_ops functions — `subprocess.run` with `capture_output=True, text=True`, returning error dict or raising CalledProcessError.
**When to use:** All git operations — never call subprocess directly in routers.

```python
# Pattern — matches git_ahead_behind, git_fetch style exactly
def git_list_branches(folder: str) -> list[dict]:
    """Return all branches with name and is_current flag.

    Returns list of {"name": str, "is_current": bool}.
    Returns [] when repo has no commits (unborn HEAD).
    """
    result = subprocess.run(
        ["git", "-C", folder, "branch", "--format=%(refname:short)\x1f%(HEAD)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    branches = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f", 1)
        if len(parts) < 2:
            continue
        name, head_marker = parts
        branches.append({"name": name, "is_current": head_marker == "*"})
    return branches


def git_current_branch(folder: str) -> str:
    """Return the current branch name. Returns 'main' as fallback."""
    result = subprocess.run(
        ["git", "-C", folder, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "main"


def git_create_branch(folder: str, name: str) -> None:
    """Create a new branch from HEAD and switch to it.

    Raises subprocess.CalledProcessError on failure.
    """
    subprocess.run(
        ["git", "-C", folder, "checkout", "-b", name],
        capture_output=True,
        text=True,
        check=True,
    )


def git_checkout(folder: str, branch: str) -> dict:
    """Switch to an existing branch.

    Returns {"success": True} or {"success": False, "error": str}.
    Does NOT raise — caller handles the error dict.
    IMPORTANT: Check for uncommitted changes BEFORE calling this;
    caller owns the "block if dirty" logic.
    """
    result = subprocess.run(
        ["git", "-C", folder, "checkout", branch],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    return {"success": True}


def git_delete_branch(folder: str, branch: str, force: bool = False) -> dict:
    """Delete a branch using safe (-d) or force (-D) delete.

    Returns {"success": True} or {"success": False, "error": str}.
    Uses -d (safe) by default — refuses if branch has unmerged commits.
    Does NOT raise — caller handles the error dict.
    """
    flag = "-D" if force else "-d"
    result = subprocess.run(
        ["git", "-C", folder, "branch", flag, branch],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    return {"success": True}
```

### Pattern 2: Branch Router (branch.py)
**What:** New FastAPI router at prefix `/api/branch` with module-level `git_ops` import (mock.patch compatibility).
**When to use:** All branch API endpoints.

```python
# app/routers/branch.py
from app.services import git_ops  # noqa: F401 — required for mock.patch targeting

router = APIRouter(prefix="/api/branch", tags=["branch"])

@router.get("/{project_id}")
def list_branches(project_id: str, folder: str = Query(...)) -> list[dict]:
    """Return all branches for the project. Each entry: {name, is_current}."""
    return git_ops.git_list_branches(folder)

@router.post("/{project_id}/create")
def create_branch(project_id: str, body: BranchCreateRequest) -> dict:
    """Create and switch to a new experiment branch."""
    # name validation: must match experiment/YYYY-MM-DD-* prefix
    ...

@router.post("/{project_id}/checkout")
def checkout_branch(project_id: str, body: BranchCheckoutRequest) -> dict:
    """Switch to an existing branch."""
    # Pre-check: git_changed_workflows must be empty (block if dirty)
    changed = git_ops.git_changed_workflows(body.folder)
    if changed:
        return {"success": False, "error": f"Save changes before switching ({len(changed)} files)"}
    return git_ops.git_checkout(body.folder, body.branch)

@router.delete("/{project_id}/delete")
def delete_branch(project_id: str, body: BranchDeleteRequest) -> dict:
    """Delete an experiment branch (safe delete by default)."""
    if body.branch in ("main", "master"):
        return {"success": False, "error": "Cannot delete main branch"}
    return git_ops.git_delete_branch(body.folder, body.branch, force=body.force)
```

### Pattern 3: activeBranch in useProjectStore
**What:** Add `activeBranch` field and `setActiveBranch` action to the Zustand store. Per-project because different projects can be on different branches.
**When to use:** Branch chip reads from here; branch switch updates here.

```typescript
// Extension to useProjectStore.ts
interface ProjectStore {
  // ... existing fields ...
  activeBranch: Record<string, string>  // project_id -> branch name
  setActiveBranch: (projectId: string, branch: string) => void
}

// In create():
activeBranch: {},
setActiveBranch: (projectId, branch) =>
  set((state) => ({
    activeBranch: { ...state.activeBranch, [projectId]: branch },
  })),
```

### Pattern 4: Branch chip in ChangesPanel header
**What:** The ChangesPanel does not currently have a visible header — it starts at `<div className="flex flex-col gap-4 p-4">`. The chip needs to be added as a header row at the top of this div, above the file list.
**When to use:** Always rendered when a project is active.

Key behaviors to implement:
- Chip truncates branch name: `experiment/2026-03-...` (max ~20 chars visible)
- Amber tint classes: `bg-amber-100 text-amber-800 border-amber-300` (matches existing amber in ChangesPanel)
- Neutral tint for main: `bg-muted text-muted-foreground border-border`
- Popover opens on chip click; closes on outside click (Radix Popover handles this)
- Popover body: list of branches, checkmark on active, `+ New experiment` at bottom
- If `changedFiles.length > 0`: branch rows show `opacity-50 cursor-not-allowed`; warning shown at top of popover

### Pattern 5: History branch-awareness
**What:** `AppShell.tsx` passes `activeBranch` to `fetchHistory`. History endpoint gains `?branch=` query param. `git_log` accepts optional `branch` param.
**When to use:** Every time history is fetched after a branch switch.

```python
# Extension to git_log in git_ops.py
def git_log(folder: str, branch: str | None = None) -> list[dict]:
    """Pass branch name to git log to filter to that branch's commits."""
    cmd = ["git", "-C", folder, "log", "--pretty=format:%H\x1f%s\x1f%an\x1f%aI"]
    if branch:
        cmd.append(branch)  # git log <branch> shows only that branch's commits
    ...
```

```python
# Extension to list_history in history.py
@router.get("/{project_id}")
def list_history(
    project_id: str,
    folder: str = Query(...),
    branch: str | None = Query(None),
) -> list[dict]:
    ...
    entries = git_ops.git_log(folder, branch=branch)
    ...
```

### Pattern 6: Multi-branch GraphView SVG
**What:** When multiple branches exist, the GraphView SVG must show two columns: main (left) and experiment (right), connected by a branch line from the shared ancestor.
**When to use:** Only when experiment branches exist alongside main.

Implementation approach:
- Call `git_list_branches` to know if multi-branch context exists
- Pass branch metadata alongside history entries so GraphView knows which commit is the branch point
- For linear view (single branch): existing code unchanged
- For multi-branch: experiment commits rendered in a second SVG column at `SVG_COL_WIDTH * 2`; a line connects from the shared ancestor node on column 1 to the first experiment node on column 2
- Use `currentColor` / Tailwind color tokens for the branch line (amber for experiment track)

### Anti-Patterns to Avoid
- **Calling git in the router directly:** All git operations stay in `git_ops.py` — routers import `git_ops` at module level for mock.patch compatibility (established in Phase 11-02 and every subsequent phase).
- **Raising exceptions from checkout/delete:** These functions return `{"success": False, "error": "..."}` — they do not raise. The UI handles the error text. Only create_branch raises (it's a programming error if the name is invalid).
- **Hardcoding branch name 'main':** Use `git_current_branch()` or read from `git_list_branches()` is_current flag. Some repos use 'master'.
- **Fetching branch list inside the popover component:** Fetch on popover open (lazy) or when project changes; don't fetch on every render.
- **Embedding branch in URL/path:** The branch is workspace state, not a route. Keep it in `useProjectStore.activeBranch`, not the URL.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Click-outside-to-close popover | Custom event listener on document | shadcn Popover (Radix) | Handles focus trap, keyboard Escape, outside click, portal rendering |
| Branch name slug generation | Complex regex | Simple JS: `.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')` | Date prefix added in Python at create time |
| Uncommitted changes check | New git status parse | Reuse `git_changed_workflows(folder)` | Already implemented, already tested |
| Delete confirmation | Custom confirm div | shadcn AlertDialog (already installed) | Same component used for discard confirm in ChangesPanel |

**Key insight:** The "block switch if dirty" logic requires zero new code in git_ops.py — `git_changed_workflows` already returns the list of changed files; the checkout endpoint just calls it before proceeding.

## Common Pitfalls

### Pitfall 1: Popover component path alias
**What goes wrong:** `npx shadcn@latest add popover` writes to `@/components/ui/popover.tsx` which doesn't resolve in this project.
**Why it happens:** shadcn CLI resolves `@/` literally, not via vite alias.
**How to avoid:** After install, move `@/components/ui/popover.tsx` → `src/components/ui/popover.tsx` (same fix applied in Phases 11, 13, 15, 16 for every shadcn add).
**Warning signs:** TypeScript import error `Cannot find module '@/components/ui/popover'` at build time.

### Pitfall 2: git checkout vs git switch
**What goes wrong:** Using `git switch` instead of `git checkout` for switching branches. `git switch` was added in Git 2.23 but `git checkout` is universally available.
**Why it happens:** Newer git docs prefer `git switch`, but `git checkout` works on all git versions the app targets.
**How to avoid:** Use `git checkout <branch>` for switching, `git checkout -b <name>` for creating. Already established pattern in `git_discard_files` which uses `git checkout --`.

### Pitfall 3: git branch -d refusal on unmerged branch
**What goes wrong:** `git branch -d` exits non-zero with stderr: `error: The branch 'experiment/...' is not fully merged.`
**Why it happens:** Safe delete refuses if the branch has commits not reachable from HEAD.
**How to avoid:** `git_delete_branch` returns `{"success": False, "error": stderr}` — the UI reads the error and can offer a re-try with `force=True`. Claude's Discretion: whether to show the error inline or offer a force-delete button.
**Warning signs:** `returncode != 0` from `git branch -d`.

### Pitfall 4: History showing all-branch commits when branch param is absent
**What goes wrong:** `git log` without a branch argument shows all commits reachable from HEAD — on main after merging an experiment, this shows merged commits too.
**Why it happens:** `git log` default is all commits reachable from the current ref.
**How to avoid:** When `branch` param is provided, pass it explicitly to `git log <branch>` — this shows only commits on that branch. When `branch` is None, `git log` shows current branch (default git behavior is correct).

### Pitfall 5: activeBranch stale after project switch
**What goes wrong:** If the user switches projects, `activeBranch` in the store may reflect a branch from the previous project.
**Why it happens:** The store persists `activeBranch` as a dict keyed by `project_id`, but `AppShell` needs to fetch the current branch from the API on project selection.
**How to avoid:** On project select (`useEffect` on `activeProjectId`), call `GET /api/branch/{project_id}` and update `setActiveBranch` with the `is_current` entry. This is the same pattern as `fetchWatchStatus` and `fetchHistory` on project change.

### Pitfall 6: graph `git log` scope for multi-branch DAG
**What goes wrong:** When rendering the graph view with multiple branches, passing a single branch name to `git log` means the graph only shows one branch at a time, never both.
**Why it happens:** To render a multi-branch graph, the frontend needs commits from multiple branches simultaneously — or a single `git log --all` call with branch decoration.
**How to avoid:** For the multi-branch GraphView, call `git log --all --decorate` (or fetch per-branch and merge client-side). Simpler approach: pass `branch=None` to get all reachable commits from HEAD, then annotate with which branch each commit belongs to using `git branch --contains <sha>`. Claude's Discretion on the exact implementation.

### Pitfall 7: Branch name with forward slash in URL path
**What goes wrong:** Branch names like `experiment/2026-03-15-test` contain `/` which, if used in a URL path segment, become ambiguous (e.g., `DELETE /api/branch/proj1/delete/experiment/2026-03-15-test` is misrouted).
**Why it happens:** FastAPI path parameters can't contain `/` by default.
**How to avoid:** All branch-name parameters must be query params (`?branch=experiment/2026-03-15-test`) or POST body JSON — never path segments.

## Code Examples

### Branch list git command
```python
# Source: git documentation, verified locally
# %(refname:short) = branch name, %(HEAD) = '*' if current else ' '
result = subprocess.run(
    ["git", "-C", folder, "branch", "--format=%(refname:short)\x1f%(HEAD)"],
    capture_output=True,
    text=True,
)
# Example output line: "main\x1f*"  or  "experiment/2026-03-15-test\x1f "
```

### Branch name generation (frontend)
```typescript
// Source: CONTEXT.md specification
// spaces → hyphens, lowercased, date auto-inserted
function formatBranchName(description: string, date: string): string {
  const slug = description
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
  return `experiment/${date}-${slug}`
}
// date = new Date().toISOString().slice(0, 10)  // "2026-03-15"
```

### Amber chip classes (Tailwind v4)
```typescript
// Experiment branch chip — matches existing amber pattern in ChangesPanel
const chipClass = isExperiment
  ? 'bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950 dark:text-amber-200'
  : 'bg-muted text-muted-foreground border border-border'
```

### History endpoint with branch param
```python
# Source: existing history.py extended — git log <branch> limits to branch commits
@router.get("/{project_id}")
def list_history(
    project_id: str,
    folder: str = Query(...),
    branch: str | None = Query(None),
) -> list[dict]:
    if not git_ops.git_has_commits(folder):
        return []
    entries = git_ops.git_log(folder, branch=branch)
    pushed = git_ops.git_pushed_shas(folder)
    for entry in entries:
        entry["is_pushed"] = entry["sha"] in pushed
    return entries
```

### DiffViewer compare toggle
```typescript
// compareTo is either undefined (vs previous) or the merge-base SHA (vs main)
const url = `/api/history/${sha}/diff?folder=${encodeURIComponent(folder)}&file=${encodeURIComponent(file)}${compareTo ? `&compare_to=${compareTo}` : ''}`
// compare_to param already supported by the existing diff endpoint (Phase 14 design)
```

### Getting merge-base SHA for "vs main" comparison
```python
# git merge-base finds the common ancestor of current branch and main
result = subprocess.run(
    ["git", "-C", folder, "merge-base", "HEAD", "main"],
    capture_output=True,
    text=True,
)
merge_base_sha = result.stdout.strip()  # pass as compare_to
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| git switch (new syntax) | git checkout (universal) | Git 2.23 introduced switch | Use checkout for compatibility |
| shadcn Dialog for branch popover | shadcn Popover | n/a | Popover is correct for inline interactive content |
| git log --all for branch history | git log <branch> | n/a | Branch-scoped log filters to active branch commits only |

**Existing patterns that directly apply:**
- Module-level `from app.services import git_ops` in router — mock.patch targeting (every phase from 11 onwards)
- `lastPushTimestamp = Date.now()` signal pattern — used in AppShell to trigger HistoryPanel re-fetch; same signal reused for `lastBranchSwitchTimestamp`
- shadcn `@/` alias fix — applies to popover.tsx after shadcn add
- AlertDialog for confirmations — already in ChangesPanel for discard, reuse for delete branch
- Amber tint for state signaling — already used for "first version save" card in ChangesPanel; extend same pattern to experiment chip

## Open Questions

1. **merge-base SHA for "vs main" compare toggle**
   - What we know: The diff endpoint already accepts `compare_to` as a SHA (Phase 14 design). `git merge-base HEAD main` returns the SHA where experiment branched from main.
   - What's unclear: Where does the frontend get this SHA? Either a new API endpoint (`GET /api/branch/{project_id}/merge-base?folder=...`) or computed in the list_history response.
   - Recommendation: Add `merge_base_sha` to the response from `GET /api/branch/{project_id}` (the "current branch info" endpoint), so the frontend can pass it directly to the diff endpoint without an extra round-trip.

2. **Multi-branch graph layout algorithm**
   - What we know: The current GraphView is purely linear (single column, one node per commit). Adding a second column for experiment-branch commits requires knowing which commits are on main vs experiment.
   - What's unclear: If the user has switched to the experiment branch, `git log experiment/...` returns only experiment commits — the main commits before the branch point won't appear. A `git log --all` approach returns all commits from all branches.
   - Recommendation: For the multi-branch graph, fetch all branches' commits in a single call (`git log --all --decorate --format=...`) in a new `git_log_all` function. This is a Claude's Discretion implementation detail.

3. **git push behavior for new experiment branches**
   - What we know: The existing `git_push` in git_ops.py pushes the current branch with `--set-upstream`. If the user creates an experiment branch and backs up, push will create `origin/experiment/2026-03-15-test`.
   - What's unclear: The push button in HistoryPanel calls the existing push endpoint — it will push whatever the current branch is. No change needed, but this interaction should be verified.
   - Recommendation: No API changes needed; push works naturally for any branch. Verify in the phase 4 verification plan.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_branch.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BRANCH-01 | `git_create_branch` creates and checks out new branch | unit | `pytest tests/test_branch.py::test_git_create_branch -x` | Wave 0 |
| BRANCH-01 | `POST /api/branch/{id}/create` returns 200 with new branch name | integration | `pytest tests/test_branch.py::test_create_branch_endpoint -x` | Wave 0 |
| BRANCH-01 | Branch name formatting: spaces→hyphens, lowercase, date prefix | unit | `pytest tests/test_branch.py::test_branch_name_format -x` | Wave 0 |
| BRANCH-02 | `git_checkout` succeeds on clean working tree | unit | `pytest tests/test_branch.py::test_git_checkout -x` | Wave 0 |
| BRANCH-02 | `POST /api/branch/{id}/checkout` blocks if uncommitted files exist | integration | `pytest tests/test_branch.py::test_checkout_blocked_if_dirty -x` | Wave 0 |
| BRANCH-02 | `git_delete_branch` safe-deletes and returns error dict on unmerged | unit | `pytest tests/test_branch.py::test_git_delete_branch -x` | Wave 0 |
| BRANCH-03 | `git_list_branches` returns list with is_current flag | unit | `pytest tests/test_branch.py::test_git_list_branches -x` | Wave 0 |
| BRANCH-03 | `GET /api/branch/{id}` returns branches list | integration | `pytest tests/test_branch.py::test_list_branches_endpoint -x` | Wave 0 |
| BRANCH-01/02 | History endpoint passes `branch` param to `git_log` | integration | `pytest tests/test_history.py::test_list_history_with_branch -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_branch.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_branch.py` — all BRANCH-01, BRANCH-02, BRANCH-03 tests above
- [ ] `tests/test_history.py` needs `test_list_history_with_branch` added (existing file, additive)

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `app/services/git_ops.py` — all existing function signatures, patterns, and subprocess conventions confirmed by direct read
- Codebase inspection: `app/frontend/src/components/ChangesPanel.tsx` — current header structure (no existing header div), amber card pattern
- Codebase inspection: `app/frontend/src/components/HistoryPanel.tsx` — GraphView SVG structure, lastPushTimestamp pattern, compare_to already in diff endpoint
- Codebase inspection: `app/frontend/src/store/useProjectStore.ts` — current store shape, confirmed no activeBranch field
- Codebase inspection: `app/routers/history.py` — compare_to param already present on diff endpoint (Phase 14)
- Codebase inspection: `app/frontend/package.json` — confirmed @radix-ui/react-popover NOT installed
- Codebase inspection: `app/frontend/src/components/ui/` — confirmed popover.tsx does NOT exist yet
- Codebase inspection: `.planning/STATE.md` — confirmed shadcn alias fix required (documented for all prior shadcn installs)
- git documentation: `git branch --format=%(refname:short)\x1f%(HEAD)` — verified locally on project repo

### Secondary (MEDIUM confidence)
- git documentation: `git checkout -b <name>` creates and switches in one command — standard, universally available
- git documentation: `git branch -d` (safe) vs `-D` (force) — verified by git --help output
- git documentation: `git merge-base HEAD main` for finding branch ancestor — standard git operation
- shadcn/ui docs: Popover component — `npx shadcn@latest add popover` install path (consistent with all prior shadcn installs in this project)

### Tertiary (LOW confidence)
- None — all critical claims verified against codebase or git documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries either already present or standard shadcn install with known workaround
- Architecture: HIGH — all patterns directly derived from existing code; no new patterns introduced
- Pitfalls: HIGH — all pitfalls derived from either existing STATE.md documented decisions or direct git behavior testing
- Test map: HIGH — framework confirmed in pyproject.toml, test file list derived from requirements

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (30 days — stable stack, no fast-moving dependencies)
