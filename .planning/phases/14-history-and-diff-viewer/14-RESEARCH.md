# Phase 14: History and Diff Viewer - Research

**Researched:** 2026-03-14
**Domain:** FastAPI history endpoint, git log subprocess, React inline iframe diff viewer, AppShell state machine refactor
**Confidence:** HIGH

## Summary

Phase 14 adds two capabilities to a working FastAPI + React SPA: a flat commit timeline panel (HistoryPanel) that replaces the current SuccessCard idle state, and an inline diff viewer (DiffViewer) that runs the existing ACD pipeline on-demand when the user clicks a history entry. Both features wire into the already-established AppShell state machine and follow patterns that are 100% consistent with Phases 11-13.

The backend work is a new `app/routers/history.py` router with two endpoints: `GET /api/history/{project_id}` (flat commit list) and `GET /api/history/{sha}/diff` (on-demand ACD HTML report). Both call `app/services/git_ops.py` using the established module-level import pattern. The frontend work is two new components (HistoryPanel, DiffViewer) and a modified AppShell that replaces the `lastSave !== null → SuccessCard` branch.

The critical integration point is how the AppShell state machine evolves: SuccessCard is retired; after a successful save, `handleSaved` now transitions directly to HistoryPanel by fetching the history list instead of setting `lastSave`. The Zustand `lastSave` field can be removed (or repurposed as `selectedDiff` state for the diff viewer's SHA + file selection).

**Primary recommendation:** Implement backend first (git_log, git_show_file, history router), then HistoryPanel as a pure display component, then DiffViewer with iframe, then wire AppShell state machine to retire SuccessCard last.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- History panel is the idle state — replaces Phase 13's SuccessCard placeholder
- State machine for main content area:
  - `changedCount > 0` → ChangesPanel (Phase 13, unchanged)
  - `changedCount = 0, hasCommits` → HistoryPanel (Phase 14)
  - `!hasCommits` → EmptyState (Phase 11, unchanged)
- After a successful save: jump straight to HistoryPanel with new entry at top showing "just now" — no intermediate SuccessCard
- Undo last save button moves from SuccessCard to the latest history entry (top of list)
- Project switch while in any view: always reset to history list (or EmptyState) for the newly selected project — consistent with Phase 13 pattern
- Each entry shows: commit message (truncated ~60 chars), relative timestamp ("2 hours ago" / "Mar 13"), author name
- Most recent entry gets a subtle "Latest" pill badge
- Scrollable list, all entries loaded — no pagination (typical team has 10–30 saves)
- Entries are clickable rows; hover state to signal interactivity
- Clicking an entry replaces the history list with a full-screen diff view:
  - Header row: "← History  |  [commit message]"
  - "← History" link returns to the history list
  - Below: full-height iframe loading the ACD diff report
- Loading state: centered spinner fills the iframe area while ACD pipeline runs (1–5 sec)
- First entry (no parent commit): clicking shows explanation message — "This is the first saved version — no previous version to compare." No iframe, no broken state.
- When multiple files were changed in a commit: show a file selector above the iframe (file basenames)
- When only one file was changed: skip the selector, load the report directly
- Phase 14 scope: main branch only — each entry diffs against its parent commit
- Endpoint: `GET /api/history/{sha}/diff?file={filename}` — backend checks out `{sha}` and `{sha}~1`, extracts the specified file, runs `pipeline.run(DiffRequest)`, returns HTML report
- `GET /api/history/{project_id}` — returns flat list: `[{sha, message, author, timestamp, files_changed: [...]}]`
- API designed for Phase 17 extensibility: endpoint will accept optional `compare_to` param (branch name or SHA) — Phase 14 does not implement this UI

### Claude's Discretion

- Exact shadcn/Tailwind component choices for history entry rows
- Animation/transition when entering and exiting the full-screen diff view
- Relative timestamp formatting and when it switches from "just now" to "X min ago" to "Mar 13"
- Whether the file selector is a dropdown or tab row
- Exact error state if ACD pipeline fails (timeout, corrupt file, etc.)

### Deferred Ideas (OUT OF SCOPE)

- Cross-branch comparison UI ("compare to main" selector on experiment branches) — Phase 17
- "Undo any version" (not just last) — not in v1.1 scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HIST-01 | User can view a flat timeline of saved versions (date, message, author) per project — no branch DAG | `git log --pretty=format` with `--name-only` provides all fields; git_log() service function + GET /api/history/{project_id} endpoint; HistoryPanel component displays entries |
| HIST-02 | User can click any history entry to view the ACD diff report for that version embedded inline | `git show {sha}:{file}` extracts file content for both sha and sha~1; `pipeline.run(DiffRequest(path_a, path_b))` + `HTMLRenderer.render()` produces the HTML; DiffViewer component embeds report in an iframe via blob URL |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | History router, diff endpoint | Project standard — all routers use FastAPI |
| Pydantic | existing | Response models for history list | Project standard — all router responses validated |
| subprocess (stdlib) | stdlib | git log, git show calls | Project standard — all git ops use subprocess wrappers |
| alteryx_diff.pipeline | v1.0 bundled | Diff computation via pipeline.run(DiffRequest) | Existing ACD engine — no changes needed |
| alteryx_diff.renderers.html_renderer | v1.0 bundled | HTMLRenderer.render() produces self-contained HTML string | Existing renderer — produces the inline report |
| React + TypeScript | existing | HistoryPanel, DiffViewer components | Project standard |
| shadcn/ui + Tailwind | existing | All UI components | Project standard — all existing components use this |
| Zustand | existing | State store update (retire lastSave, add selectedDiff) | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile (stdlib) | stdlib | Write git-extracted file content to temp files for pipeline.run() | Required because DiffRequest takes pathlib.Path objects, not raw bytes |
| Intl.RelativeTimeFormat | browser built-in | Relative timestamp formatting | Zero dependencies — "2 hours ago" / "Mar 13" |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| iframe for diff report | Inline HTML injection | iframe provides full isolation — the ACD report has its own CSS/JS and theme toggle; injecting into the React DOM would cause style collisions and script execution issues. Use iframe unconditionally. |
| Blob URL for iframe src | srcdoc attribute | srcdoc has a 64KB limit risk on large reports; blob URL is cleaner for large HTML. Use `URL.createObjectURL(new Blob([html], {type: 'text/html'}))` and revoke on cleanup. |
| tempfile.NamedTemporaryFile | tempfile.mkstemp | NamedTemporaryFile with delete=True holds a file lock on Windows preventing re-open. mkstemp + manual unlink is the safe cross-platform pattern. |

**Installation:** No new packages required — all dependencies are already present.

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── routers/
│   ├── history.py          # NEW: GET /api/history/{project_id}, GET /api/history/{sha}/diff
│   └── ...                 # existing routers unchanged
├── services/
│   └── git_ops.py          # EXTEND: add git_log(), git_show_file()
└── server.py               # EXTEND: app.include_router(history.router)

app/frontend/src/
├── components/
│   ├── HistoryPanel.tsx    # NEW: flat commit list
│   ├── DiffViewer.tsx      # NEW: header + iframe
│   ├── AppShell.tsx        # MODIFY: state machine, retire SuccessCard branch
│   └── SuccessCard.tsx     # REMOVE (delete in final plan of this phase)
└── store/
    └── useProjectStore.ts  # MODIFY: remove lastSave, add selectedDiff state

tests/
└── test_history.py         # NEW: unit + endpoint tests for history router
```

### Pattern 1: git_log() — Flat Commit List

**What:** Subprocess wrapper returning structured list of commits using `git log` with a unit-separator `--pretty` format, then a second call per SHA for file lists.
**When to use:** Called by `GET /api/history/{project_id}` endpoint.

```python
# Source: established git_ops.py subprocess pattern in this project
import subprocess
from pathlib import Path

def git_log(folder: str) -> list[dict]:
    """Return flat list of commits (newest first) with changed workflow files."""
    # Step 1: get commit metadata with unit-separator fields
    result = subprocess.run(
        ["git", "-C", folder, "log", "--pretty=format:%H\x1f%s\x1f%an\x1f%aI"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    entries = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\x1f", 3)
        if len(parts) != 4:
            continue
        sha, message, author, timestamp = parts

        # Step 2: get changed workflow files for this sha
        has_parent = subprocess.run(
            ["git", "-C", folder, "rev-parse", "--verify", f"{sha}~1"],
            capture_output=True, text=True,
        ).returncode == 0

        files_result = subprocess.run(
            ["git", "-C", folder, "diff-tree", "--no-commit-id", "-r",
             "--name-only", sha],
            capture_output=True, text=True,
        )
        all_files = files_result.stdout.strip().splitlines()
        workflow_files = [f for f in all_files if Path(f).suffix in WORKFLOW_SUFFIXES]

        entries.append({
            "sha": sha,
            "message": message,
            "author": author,
            "timestamp": timestamp,
            "files_changed": workflow_files,
            "has_parent": has_parent,
        })
    return entries
```

**Note on N subprocesses:** For the typical 10-30 commits, N+1 subprocess calls (1 for log + N for diff-tree) is acceptable. If performance becomes a concern, `git log --name-only` can consolidate to a single call but requires careful blank-line parsing (see Pitfall 1).

### Pattern 2: git_show_file() — Extract File at SHA

**What:** Extract file content at a specific SHA using `git show {sha}:{filepath}`.
**When to use:** Called by `GET /api/history/{sha}/diff` to get both versions for the pipeline.

```python
# Source: established git_ops.py subprocess pattern in this project
def git_show_file(folder: str, sha: str, filepath: str) -> bytes:
    """Return raw bytes of `filepath` at commit `sha`.

    Raises FileNotFoundError if the file did not exist at that commit.
    """
    result = subprocess.run(
        ["git", "-C", folder, "show", f"{sha}:{filepath}"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise FileNotFoundError(f"{filepath} not found at {sha}")
    return result.stdout
```

### Pattern 3: History Diff Endpoint

**What:** FastAPI endpoint that extracts both versions of a file, writes to temp files, runs ACD pipeline, returns HTML.
**When to use:** Called by DiffViewer via fetch when user clicks a history entry.

```python
# Source: established app/routers/save.py FastAPI pattern in this project
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
import tempfile, os, pathlib
from app.services import git_ops
from alteryx_diff.pipeline import run as pipeline_run, DiffRequest
from alteryx_diff.renderers.html_renderer import HTMLRenderer

router = APIRouter(prefix="/api/history", tags=["history"])

@router.get("/{project_id}")
def list_history(project_id: str, folder: str = Query(...)) -> list[dict]:
    """Return flat commit list for project folder."""
    if not git_ops.git_has_commits(folder):
        return []
    return git_ops.git_log(folder)

@router.get("/{sha}/diff")
def get_diff(
    sha: str,
    folder: str = Query(...),
    file: str = Query(...),
    compare_to: str | None = Query(None),  # Phase 17 extensibility point
):
    """Run ACD pipeline on sha vs sha~1 for the given file, return HTML report."""
    parent_sha = compare_to if compare_to else f"{sha}~1"

    # Handle first commit (no parent)
    has_parent = subprocess.run(
        ["git", "-C", folder, "rev-parse", "--verify", parent_sha],
        capture_output=True, text=True,
    ).returncode == 0
    if not has_parent:
        return JSONResponse({"is_first_commit": True})

    try:
        old_bytes = git_ops.git_show_file(folder, parent_sha, file)
        new_bytes = git_ops.git_show_file(folder, sha, file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    html = _run_diff(old_bytes, new_bytes, file)
    return HTMLResponse(content=html)
```

### Pattern 4: AppShell State Machine Refactor

**What:** Replace `lastSave !== null → SuccessCard` with `hasCommits && !selectedDiff → HistoryPanel` and `selectedDiff → DiffViewer`.

```typescript
// Source: existing app/frontend/src/components/AppShell.tsx pattern
// State additions in AppShell (local state, not Zustand):
// const [history, setHistory] = useState<CommitEntry[]>([])
// const [selectedDiff, setSelectedDiff] = useState<{sha: string; file: string} | null>(null)

// renderMainContent() AFTER Phase 14:
function renderMainContent() {
  // ... identity card and no-project checks unchanged ...
  if (changedFiles.length > 0) {
    return <ChangesPanel ... />
  }
  if (hasCommits && selectedDiff) {
    return (
      <DiffViewer
        sha={selectedDiff.sha}
        file={selectedDiff.file}
        folder={activeProject.path}
        commitMessage={history.find(e => e.sha === selectedDiff.sha)?.message ?? ''}
        onBack={() => setSelectedDiff(null)}
      />
    )
  }
  if (hasCommits) {
    return (
      <HistoryPanel
        entries={history}
        projectId={activeProject.id}
        projectPath={activeProject.path}
        onSelectEntry={(entry, file) => setSelectedDiff({ sha: entry.sha, file })}
        onUndo={handleUndo}
      />
    )
  }
  return <EmptyState projectName={activeProject.name} />
}
```

**After save transition:** In `handleSaved`, replace `setLastSave(save)` with `await fetchHistory()`. Because `fetchHistory` populates `history` and `hasCommits` is already true, the panel renders HistoryPanel automatically.

**On project switch:** Clear `history`, `selectedDiff` synchronously in the `useEffect` cleanup, same as `changedFiles` and `hasCommits`.

### Pattern 5: DiffViewer Iframe with Blob URL

**What:** Fetch HTML string from backend, create blob URL, set as iframe src, revoke on cleanup.
**When to use:** Renders the ACD diff report inline without style collisions.

```typescript
// Source: Web platform standard — URL.createObjectURL / URL.revokeObjectURL
useEffect(() => {
  let blobUrl: string | null = null
  let cancelled = false

  async function loadDiff() {
    setLoading(true)
    setIsFirstCommit(false)
    const res = await fetch(
      `/api/history/${sha}/diff?folder=${encodeURIComponent(folder)}&file=${encodeURIComponent(file)}`
    )
    if (cancelled) return
    const data = res.headers.get('content-type')?.includes('json')
      ? await res.json()
      : null
    if (data?.is_first_commit) {
      setIsFirstCommit(true)
      setLoading(false)
      return
    }
    const html = await res.text()
    if (cancelled) return
    blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    setIframeSrc(blobUrl)
    setLoading(false)
  }

  loadDiff()
  return () => {
    cancelled = true
    if (blobUrl) URL.revokeObjectURL(blobUrl)
  }
}, [sha, file, folder])
```

### Anti-Patterns to Avoid

- **Injecting raw HTML into the React DOM for the diff report:** The ACD HTML report has its own `<style>` and `<script>` tags plus a theme toggle. Injecting it into the React component tree causes CSS conflicts with Tailwind and the inline scripts will not execute. Always use an `<iframe>` element.
- **Calling `git show` without checking for first commit:** The first commit has no parent. `git show sha~1:file` will fail with exit code 128. Always check for parent existence before calling the diff endpoint, or handle it in the endpoint and return a JSON sentinel.
- **Using `git log --name-only` single-pass without careful blank-line handling:** The format mixes blank lines as separators between commit header and file list, and between commits. If parser assumes fixed-line structure it will misalign metadata with files. Prefer the two-pass approach (git log for headers, git diff-tree per SHA for files).
- **Storing `lastSave` in Zustand and using it for panel routing in Phase 14:** After Phase 14, panel routing is purely driven by `hasCommits` + `selectedDiff`. `lastSave` becomes irrelevant. Keeping it alongside the new state creates confusion and dual truth.
- **Local import inside router functions for mock.patch targets:** Follow the established Phase 11/13 pattern — `from app.services import git_ops` at module level, use `git_ops.git_log(folder)` in endpoint body. Patch target: `app.routers.history.git_ops.git_log`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative timestamps | Custom date math | `Intl.RelativeTimeFormat` (browser built-in) | Handles locale, pluralization, and cutoffs correctly |
| HTML diff report | Custom XML diff display | `alteryx_diff.pipeline.run()` + `HTMLRenderer.render()` | Already built, tested, handles all Alteryx-specific normalization |
| File content at a git SHA | Git object database parsing | `git show {sha}:{file}` subprocess | Git handles all edge cases (binary, renames, encoding) |
| Commit list with file changes | Custom log parser | `git log` + `git diff-tree` | Handles merges, renames, encoding edge cases |
| Iframe isolation | Shadow DOM or raw HTML injection | Native `<iframe>` | Zero-dependency, complete CSS/JS isolation |

**Key insight:** The ACD diff pipeline is the single most complex piece of this project. Phase 14 calls it as a library — no modifications needed. All complexity around XML parsing, tool matching, and HTML rendering is already solved.

---

## Common Pitfalls

### Pitfall 1: git log --name-only Parsing

**What goes wrong:** The output of `git log --pretty=format:... --name-only` has blank line separators between the commit header and the file list, and between commits. If the parser assumes a fixed-line structure it will misalign commit metadata with file lists.

**Why it happens:** `--pretty=format:` (without `tformat:`) does not add a trailing newline after each commit block. The `--name-only` file list appears after a blank line. The next commit's header appears after another blank line.

**How to avoid:** Use the two-pass approach documented in Pattern 1: `git log --pretty=format:%H\x1f%s\x1f%an\x1f%aI` for headers (unit-separator makes parsing unambiguous), then `git diff-tree --no-commit-id -r --name-only {sha}` per SHA for file lists.

**Warning signs:** History list shows wrong files under a commit, or last commit's files appear under the next commit.

### Pitfall 2: First Commit Has No Parent

**What goes wrong:** `GET /api/history/{sha}/diff` for the first commit calls `git show {sha}~1:{file}`, which fails with exit code 128. This surfaces as a 500 error in the UI.

**Why it happens:** The first commit has no parent; `HEAD~1` does not exist.

**How to avoid:** In the diff endpoint, check `git rev-parse --verify {sha}~1` before extracting files. If it fails, return `JSONResponse({"is_first_commit": True})`. In `git_log()`, include `has_parent: bool` in each entry so the frontend can disable the diff viewer click for the oldest entry rather than making a round-trip.

**Warning signs:** 500 on clicking the oldest history entry.

### Pitfall 3: Temp File Cleanup on Windows

**What goes wrong:** `tempfile.NamedTemporaryFile(delete=True)` holds a file lock on Windows, preventing `pipeline.run()` from opening the file by path in a separate call. File remains locked until garbage collected.

**Why it happens:** Windows does not allow a file opened with `delete=True` to be opened again by name by another caller.

**How to avoid:** Use `tempfile.mkstemp()` returning a file descriptor, write bytes, close the fd, then pass the path to `DiffRequest`. In a `finally` block, call `os.unlink(path)`. This is the safe cross-platform pattern.

**Warning signs:** `PermissionError` or `FileNotFoundError` in the diff endpoint on Windows test environments.

### Pitfall 4: AppShell fetchHistory Race Condition

**What goes wrong:** On project switch, `fetchWatchStatus()` and `fetchHistory()` are both called. If they resolve in different orders, `history` state could belong to the previous project when the panel renders.

**Why it happens:** React state updates are asynchronous; two concurrent fetches can complete out of order.

**How to avoid:** Clear `history` to `[]` and `selectedDiff` to `null` synchronously in the `useEffect` cleanup for `activeProjectId` changes, same as how `changedFiles` and `hasCommits` are cleared. This is already the established pattern in AppShell.

**Warning signs:** History list shows stale entries from the previous project briefly after switching projects.

### Pitfall 5: Blob URL Memory Leak

**What goes wrong:** Each time the user clicks a history entry, a new blob URL is created. If `URL.revokeObjectURL` is not called (e.g., component unmounts before fetch resolves), blob URLs accumulate in browser memory.

**Why it happens:** Browser blob URLs are not garbage-collected until explicitly revoked.

**How to avoid:** The useEffect cleanup function must always call `URL.revokeObjectURL(blobUrl)` if `blobUrl` was created. Use a `cancelled` flag (shown in Pattern 5) to avoid setting state after cleanup. Revoke the blob URL in the cleanup return.

**Warning signs:** Increasing memory usage as user navigates between many history entries.

### Pitfall 6: Module-Level Import for mock.patch Targets

**What goes wrong:** If `history.py` router imports `git_ops` functions at call time inside the endpoint function, `unittest.mock.patch("app.routers.history.git_ops.git_log")` will fail because the name doesn't exist at module level.

**Why it happens:** `mock.patch` replaces the name in the target module's namespace. If the import is local to a function, the name is not in the module namespace.

**How to avoid:** Follow the established Phase 11/13 pattern: `from app.services import git_ops` at module level. In endpoint: `git_ops.git_log(folder)`. Patch target: `app.routers.history.git_ops.git_log`.

---

## Code Examples

### git_log() Response Shape
```python
# Source: confirmed from CONTEXT.md API spec and existing git_ops.py patterns
[
    {
        "sha": "abc123def456",
        "message": "Updated filter logic for customer report",
        "author": "Jane Smith",
        "timestamp": "2026-03-14T10:30:00+00:00",  # ISO-8601 from %aI
        "files_changed": ["CustomerReport.yxmd", "SummaryWorkflow.yxmd"],
        "has_parent": True,
    },
    {
        "sha": "deadbeef1234",
        "message": "Initial version of project workflows",
        "author": "Jane Smith",
        "timestamp": "2026-03-13T09:00:00+00:00",
        "files_changed": ["CustomerReport.yxmd"],
        "has_parent": False,  # first commit — clicking shows friendly message, no iframe
    },
]
```

### ACD Pipeline Call Pattern (History Diff Endpoint)
```python
# Source: src/alteryx_diff/pipeline/__init__.py — confirmed DiffRequest(path_a, path_b) signature
# Source: src/alteryx_diff/renderers/html_renderer.py — confirmed HTMLRenderer().render(result)

import tempfile, os, pathlib
from alteryx_diff.pipeline import run as pipeline_run, DiffRequest
from alteryx_diff.renderers.html_renderer import HTMLRenderer

def _run_diff(old_bytes: bytes, new_bytes: bytes, filename: str) -> str:
    """Write bytes to temp files, run pipeline, return HTML string."""
    fd_a, path_a = tempfile.mkstemp(suffix=".yxmd")
    fd_b, path_b = tempfile.mkstemp(suffix=".yxmd")
    try:
        os.write(fd_a, old_bytes)
        os.close(fd_a)
        os.write(fd_b, new_bytes)
        os.close(fd_b)
        response = pipeline_run(DiffRequest(
            path_a=pathlib.Path(path_a),
            path_b=pathlib.Path(path_b),
        ))
        return HTMLRenderer().render(
            response.result,
            file_a=f"{filename} (previous)",
            file_b=f"{filename} (this version)",
        )
    finally:
        os.unlink(path_a)
        os.unlink(path_b)
```

### HistoryPanel Entry Row (shadcn/Tailwind)
```typescript
// Source: established ChangesPanel.tsx + shadcn/ui pattern in this project
// Recommended: plain div rows with hover:bg-muted/60 — no extra shadcn component needed
// "Latest" pill: <Badge variant="secondary">Latest</Badge>

<div
  key={entry.sha}
  onClick={() => onSelectEntry(entry)}
  className="flex items-center justify-between px-3 py-2 rounded-md
             cursor-pointer hover:bg-muted/60 transition-colors"
>
  <div className="flex flex-col gap-0.5 min-w-0">
    <span className="text-sm font-medium truncate max-w-[240px]">
      {entry.message || 'Save'}
    </span>
    <span className="text-xs text-muted-foreground">
      {entry.author} · {formatRelativeTime(entry.timestamp)}
    </span>
  </div>
  {isLatest && (
    <Badge variant="secondary" className="ml-2 shrink-0 text-xs">Latest</Badge>
  )}
</div>
```

### Relative Timestamp (Intl.RelativeTimeFormat)
```typescript
// Source: MDN Web Docs — Intl.RelativeTimeFormat, browser built-in, no install needed
function formatRelativeTime(isoTimestamp: string): string {
  const diffMs = Date.now() - new Date(isoTimestamp).getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  // Older than 24h: show "Mar 13" style
  return new Date(isoTimestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
```

### File Selector Recommendation (Claude's Discretion)
Use a tab row (not a dropdown) when there are 2-4 files; a `<Select>` dropdown for 5+. For Phase 14 (typical: 1-3 files per commit), a tab row is the cleanest UX. If only one file, render neither selector.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SuccessCard as idle state after save | HistoryPanel as permanent idle state | Phase 14 | SuccessCard is removed entirely |
| `lastSave: LastSave \| null` drives SuccessCard | `history: CommitEntry[]` + `selectedDiff` drives panel routing | Phase 14 | Zustand store updated |
| No history API | `GET /api/history/{project_id}` + `GET /api/history/{sha}/diff` | Phase 14 | Two new endpoints in history.py router |

**Deprecated/outdated after Phase 14:**
- `SuccessCard.tsx`: Removed; undo button migrates to top history entry row
- `lastSave` Zustand state: Removed or repurposed
- `handleSaved` in AppShell: Refactored to call `fetchHistory()` instead of `setLastSave(save)`

---

## Open Questions

1. **git log parsing strategy — single-pass vs two-pass**
   - What we know: `git log --name-only` is single-pass but parsing is fiddly; two-pass (git log for headers, git diff-tree per SHA) is simpler but N+1 subprocesses
   - What's unclear: Whether blank line handling in `git log --pretty=format:` is reliable across all git versions
   - Recommendation: Use two-pass for implementation clarity (30 commits = 31 subprocesses, all fast local git ops, acceptable performance)

2. **HTTP response shape for first commit diff request**
   - What we know: The user clicking the first entry must see a friendly message, not an error
   - Recommendation: Return `200 application/json` with `{"is_first_commit": true}` — simpler for the frontend to check than 204 with content-type inference

3. **project_id vs folder as the history endpoint parameter**
   - What we know: `GET /api/history/{project_id}` spec needs `folder` too — project_id alone is not enough to locate the git repo
   - Recommendation: `GET /api/history/{project_id}?folder={folder_path}` (path param for ID, query param for folder), same pattern as `/api/watch/status`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, confirmed in tests/) |
| Config file | pyproject.toml (existing project) |
| Quick run command | `pytest tests/test_history.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HIST-01 | `git_log()` returns commits with sha/message/author/timestamp/files_changed | unit | `pytest tests/test_history.py::test_git_log -x` | ❌ Wave 0 |
| HIST-01 | `git_log()` returns empty list for repo with no commits | unit | `pytest tests/test_history.py::test_git_log_empty -x` | ❌ Wave 0 |
| HIST-01 | `GET /api/history/{project_id}` returns 200 with commit list | endpoint | `pytest tests/test_history.py::test_list_history_endpoint -x` | ❌ Wave 0 |
| HIST-01 | `GET /api/history/{project_id}` returns [] when no commits | endpoint | `pytest tests/test_history.py::test_list_history_empty -x` | ❌ Wave 0 |
| HIST-02 | `GET /api/history/{sha}/diff` returns HTML with ACD report for valid sha+file | endpoint | `pytest tests/test_history.py::test_diff_endpoint -x` | ❌ Wave 0 |
| HIST-02 | `GET /api/history/{sha}/diff` for first commit returns first_commit indicator | endpoint | `pytest tests/test_history.py::test_diff_endpoint_first_commit -x` | ❌ Wave 0 |
| HIST-02 | `git_show_file()` returns correct bytes at given sha | unit | `pytest tests/test_history.py::test_git_show_file -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_history.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_history.py` — all HIST-01 and HIST-02 tests (Wave 0 creates stubs/RED tests)
- [ ] `app/routers/history.py` — new router file (stub required before RED tests can import)
- [ ] Register `history.router` in `app/server.py` — required for TestClient to reach endpoints

None of the framework infrastructure is missing — existing `conftest.py` with `client` fixture and `_make_git_repo` helper (from `test_save.py`) cover all setup needs for history tests.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `app/services/git_ops.py`: subprocess patterns, WORKFLOW_SUFFIXES, module-level import convention
- Direct codebase inspection — `app/routers/save.py`: router structure, Pydantic models, mock.patch target pattern
- Direct codebase inspection — `app/frontend/src/components/AppShell.tsx`: state machine, fetchWatchStatus pattern, renderMainContent
- Direct codebase inspection — `src/alteryx_diff/pipeline/pipeline.py`: `DiffRequest(path_a, path_b)` signature, `DiffResponse.result` field
- Direct codebase inspection — `src/alteryx_diff/renderers/html_renderer.py`: `HTMLRenderer().render(result, file_a, file_b)` signature returns `str`
- Direct codebase inspection — `app/frontend/src/store/useProjectStore.ts`: `lastSave` field to be retired
- Direct codebase inspection — `tests/conftest.py` + `tests/test_save.py`: confirmed test patterns
- `.planning/phases/14-history-and-diff-viewer/14-CONTEXT.md`: all locked decisions and API spec

### Secondary (MEDIUM confidence)
- Web platform standard — `URL.createObjectURL` / `URL.revokeObjectURL` for iframe content (standard API, zero install risk)
- `Intl.RelativeTimeFormat` — browser built-in, supported in all modern browsers including Electron-embedded Chromium

### Tertiary (LOW confidence)
- None — all findings verified against existing codebase or web platform standards

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries present and verified in the codebase
- Architecture: HIGH — all patterns mirror existing Phase 11-13 code in the same repo
- Pitfalls: HIGH — git edge cases (first commit, log parsing, Windows temp files) verified against existing test patterns and git documentation
- Test patterns: HIGH — test_save.py + conftest.py confirm exact patterns to replicate

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (stable stack — no fast-moving dependencies)
