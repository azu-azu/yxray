# Phase 20: Tech Debt Cleanup — Research

**Researched:** 2026-03-22
**Domain:** Python backend, React/TypeScript frontend, GitLab CI
**Confidence:** HIGH — all findings are from direct code inspection of the live codebase

---

## Summary

Phase 20 closes 7 non-intentional tech debt items identified in the v1.1 milestone audit. The items are spread across three layers: Python backend (`app/main.py`, `app/services/config_store.py`), React frontend (`src/components/App.tsx`, `src/components/RemotePanel.tsx`, `src/components/HistoryPanel.tsx`), and GitLab CI in the separate `/Users/laxmikantmukkawar/alteryx` repo. None of the items require new dependencies or new architectural patterns; every fix is a targeted 1–10 line change to existing files.

The most behaviorally significant item is the autostart regression (APP-02 toggle disable path): `app/main.py:87` calls `register_autostart()` unconditionally on every non-background launch, silently overwriting the user's Settings toggle. The fix is a single guard: `if not autostart.is_autostart_enabled():`. All other items are dead interface surface removal, UI error feedback surfacing, a controlled-state replacement for a `document.querySelector` DOM hack, a documented return-type unification, and GitLab CI find-or-update parity.

**Primary recommendation:** Fix each item in isolation in its own plan. The autostart guard, frontend error feedback, and GitLab CI comment dedup each need a small test addition; the interface cleanup items (dead props) and config_store return-type doc are zero-test code changes.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| APP-02 | App starts automatically on boot; toggle disable path must be preserved | Autostart guard in `app/main.py` — `is_autostart_enabled()` already exists in `autostart.py` |
| ONBOARD-02 | Add project error must surface visibly in UI | `doAddProject()` in `App.tsx:76` silently returns on non-ok responses; add error state + display |
| REMOTE-02 | GitLab tab switch in RemotePanel uses controlled React state | `renderDisconnectedCTA()` uses `document.querySelector('[data-value="gitlab"]')` at line 531–533 |
| CI-01 | GitLab CI implements find-or-update for MR comments (matching GitHub Actions behavior) | `.gitlab-ci.yml` uses `curl POST .../notes`; needs GET-then-PUT or POST with marker search |
</phase_requirements>

---

## Standard Stack

No new dependencies required. All changes use existing tools.

### Core (already installed)
| Library | Purpose | File |
|---------|---------|------|
| Python `app/services/autostart.py` | `is_autostart_enabled()` + `register_autostart()` | Already implemented, fully tested |
| FastAPI + TestClient | Backend router testing | Already used in `tests/test_projects.py` |
| React `useState` | Controlled tab/error state | Already in `RemotePanel.tsx` |
| `curl` + GitLab REST API | MR notes (GET + PUT/POST) | Already in `.gitlab-ci.yml` |
| `python3 -c` / stdlib `urllib` | JSON payload and note search | Used in GitHub version for marker search |

---

## Architecture Patterns

### Item 1: Autostart Guard — APP-02

**File:** `app/main.py`, line 85–87

**Current (broken):**
```python
from app.services import autostart  # noqa: PLC0415
autostart.register_autostart()
```

**Fix:**
```python
from app.services import autostart  # noqa: PLC0415
if not autostart.is_autostart_enabled():
    autostart.register_autostart()
```

**Why this is the right fix:** `is_autostart_enabled()` checks the HKCU Run key — it returns `False` when the user has disabled autostart via Settings (which calls `unregister_autostart()`). The guard prevents re-registration on every manual launch while preserving first-run registration when the key is absent.

**Alternative rejected:** Calling `register_autostart()` only on first-run detection would require persisting a separate first-run flag. The registry key itself is the source of truth — if it's absent (user disabled), don't re-register.

**Test to add:** `test_main_does_not_reregister_when_enabled()` — patches `is_autostart_enabled` to return `True`, confirms `register_autostart` is not called.
Existing test `test_register_writes_run_key` in `tests/test_autostart.py` is unaffected.

---

### Item 2: Add Project Error Feedback — ONBOARD-02

**File:** `app/frontend/src/App.tsx`, lines 69–90 (`doAddProject` function)

**Current (silent fail):**
```typescript
if (!addRes.ok) {
  // TODO: surface error toast in Phase 12
  return
}
```

**Fix pattern:** Add a local error state, show error message in-component (not a toast library). Consistent with existing pattern in `RemotePanel.tsx` which uses inline `<p className="text-xs text-red-500">` error paragraphs for all error feedback.

```typescript
const [addProjectError, setAddProjectError] = useState<string | null>(null)

async function doAddProject(path: string) {
  setAddProjectError(null)
  const addRes = await fetch('/api/projects', { ... })
  if (!addRes.ok) {
    const data = await addRes.json().catch(() => ({}))
    const status = addRes.status
    if (status === 409) {
      setAddProjectError('This folder is already registered.')
    } else if (status === 400) {
      setAddProjectError(data.detail ?? 'That path does not exist.')
    } else {
      setAddProjectError('Could not add project. Try again.')
    }
    return
  }
  // ... rest unchanged
}
```

**Where to display:** Render error inside the `AlertDialog` used for git-init confirmation, or as a persistent inline message in the flow. Since the error can occur after the dialog closes (at `doAddProject` call site), simplest approach is to render it inline in `WelcomeScreen` (via prop) or in `AppShell` (if on the main view). The cleanest position is an alert below the `AlertDialog` in `App.tsx` since that is where the flow is orchestrated.

**Backend already returns correct HTTP codes:** `projects.py:44` returns 400 for missing path; `projects.py:47–48` returns 409 for duplicate. No backend change needed.

**Test to add:** Frontend-only change; no new Python test needed. Verifiable via manual flow.

---

### Item 3: GitLab Tab Switch Controlled State — REMOTE-02

**File:** `app/frontend/src/components/RemotePanel.tsx`, lines 529–533

**Current (brittle DOM query):**
```typescript
<Button size="sm" variant="outline" onClick={() => {
  const trigger = document.querySelector<HTMLElement>('[data-value="gitlab"]')
  trigger?.click()
}}>
  Connect GitLab
</Button>
```

**Fix pattern:** The `Tabs` component from shadcn (Radix UI) supports a `value` + `onValueChange` controlled pattern. Add a controlled `activeTab` state.

```typescript
const [activeTab, setActiveTab] = useState<'github' | 'gitlab'>('github')

// In renderDisconnectedCTA():
<Button size="sm" variant="outline" onClick={() => setActiveTab('gitlab')}>
  Connect GitLab
</Button>

// In render:
<Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'github' | 'gitlab')}>
  <TabsList>
    <TabsTrigger value="github">GitHub</TabsTrigger>
    <TabsTrigger value="gitlab">GitLab</TabsTrigger>
  </TabsList>
  ...
</Tabs>
```

**Radix Tabs controlled mode:** `value` prop overrides `defaultValue`. The `onValueChange` callback fires when the user clicks a trigger directly. Both modes (programmatic `setActiveTab` and user click) work correctly with this pattern.

**Source:** Radix UI Tabs docs — controlled usage with `value` + `onValueChange` is the standard documented pattern. HIGH confidence from direct use within the existing codebase (same component import already used in `HistoryPanel.tsx`).

---

### Item 4: config_store.get_remote_repo() Return Type Unification — Maintainability

**File:** `app/services/config_store.py`, lines 35–48

**Current return type:**
```python
def get_remote_repo(project_id: str, provider: str | None = None) -> dict | str | None:
```

When `provider=None` → returns `dict` (the full info dict, e.g. `{github_url: ..., gitlab_url: ...}`)
When `provider="github"` → returns `str | None` (the URL for that provider)

**The concern:** The dual return type means callers must know which overload they're calling. The docstring partially documents this but type checkers emit `Union[dict, str, None]` which is hard to narrow.

**Fix options (two are valid):**
1. **Document and type-annotate with overloads** — Add `@overload` decorators (Python `typing.overload`) to declare the two call signatures separately. Zero behavior change. Callers don't need to change.
2. **Split into two functions** — `get_remote_repo_dict(project_id)` and `get_remote_repo_url(project_id, provider)`. More explicit, requires updating callers.

**Recommendation: Option 1 (overloads + docstring update).** The function already works correctly. Zero callers need to change. `@typing.overload` is the idiomatic Python solution for this exact pattern (conditional return type based on argument).

```python
from typing import overload

@overload
def get_remote_repo(project_id: str, provider: str) -> str | None: ...
@overload
def get_remote_repo(project_id: str, provider: None = None) -> dict: ...
def get_remote_repo(project_id: str, provider: str | None = None) -> dict | str | None:
    ...  # existing implementation unchanged
```

**No test change needed.** Existing callers in `app/routers/remote.py` and `app/routers/pr.py` continue to work.

---

### Item 5: Dead Interface Surface Removal — HistoryPanelProps.mergeBaseSha

**File:** `app/frontend/src/components/HistoryPanel.tsx`, line 46

**Current (dead prop):**
```typescript
interface HistoryPanelProps {
  ...
  mergeBaseSha?: string | null   // declared but NEVER destructured in function body
  ...
}
```

**From audit:** `mergeBaseSha` is passed from `AppShell.tsx:228` but HistoryPanel never uses it — `DiffViewer` receives `compareTo` directly from `AppShell`. The prop flows in but is silently ignored.

**Fix:** Remove `mergeBaseSha?: string | null` from `HistoryPanelProps` and remove `mergeBaseSha={mergeBaseSha}` from the `HistoryPanel` JSX in `AppShell.tsx:228`.

**Caller:** `AppShell.tsx` passes `mergeBaseSha={mergeBaseSha}` — this prop must also be removed from the call site to avoid TypeScript error.

**No test change needed.** Behavioral no-op.

---

### Item 6: Dead Interface Surface Removal — RemoteStatus.gitlab_repo_url

**File:** `app/frontend/src/components/RemotePanel.tsx`, line 13

**Current (unused field):**
```typescript
interface RemoteStatus {
  ...
  gitlab_repo_url: string | null   // present in interface, never used in renderPushButton
  ...
}
```

**From audit:** `gitlab_repo_url` is set in `fetchStatus()` (line 83: `gitlab_repo_url: gitlabData?.repo_url ?? null`) and declared in the local interface, but `renderPushButton('gitlab')` uses `remoteStatus.repo_url` (the GitHub one) for both providers — asymmetric behavior.

**Fix:** Remove `gitlab_repo_url: string | null` from the local `RemoteStatus` interface and remove the field assignment in `fetchStatus()` (line 83). The `renderPushButton` logic already uses `remoteStatus.repo_url` for both providers — this is the correct behavior (the backend `/api/remote/status?provider=gitlab` returns `repo_url` for the GitLab case when queried separately, but the merged status object only surfaces the GitHub `repo_url`).

**Note:** If GitLab push button should show a separate repo URL in future, that is a new feature (out of scope). The current fix simply removes unused dead surface.

---

### Item 7: GitLab CI Find-or-Update MR Comment — CI-01

**File:** `/Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml` (separate repo)
**Related file:** `/Users/laxmikantmukkawar/alteryx/.gitlab/scripts/generate_diff_comment.py`

**Current behavior:** Every pipeline run does `curl POST .../notes` unconditionally — creates a new MR comment on each push.

**Target behavior (matching GitHub Actions):** Search existing notes for `<!-- acd-diff-report -->` marker; PUT update existing note if found, POST new note if not.

**GitLab REST API for MR notes:**
- List notes: `GET /projects/:id/merge_requests/:iir/notes?per_page=100`
- Create note: `POST /projects/:id/merge_requests/:iir/notes` with body `{"body": "..."}`
- Update note: `PUT /projects/:id/merge_requests/:iir/notes/:note_id` with body `{"body": "..."}`

**Environment variables available in GitLab CI:**
- `CI_API_V4_URL` — base URL, e.g. `https://gitlab.com/api/v4`
- `CI_PROJECT_ID` — project numeric ID
- `CI_MERGE_REQUEST_IID` — MR internal ID (scoped to project)
- `GITLAB_TOKEN` — user-provided CI variable (already present in current `.gitlab-ci.yml`)

**Implementation pattern:** Replace the current shell `curl POST` block in `.gitlab-ci.yml` with a Python helper script call (consistent with how GitHub Actions uses `generate_diff_comment.py` + a separate JS script). Alternatively, implement the find-or-update logic directly in Python inside `generate_diff_comment.py`.

**Recommended approach:** Add a `post_or_update_note()` function to `.gitlab/scripts/generate_diff_comment.py` (mirrors how GitHub version embeds the marker in `build_comment()`). The GitLab generate script already uses Python for all logic — keeping the note-posting in Python is consistent.

**MARKER:** The GitLab `generate_diff_comment.py` `build_comment()` does NOT currently prepend `<!-- acd-diff-report -->`. This must be added first (matching the GitHub version where Python owns the marker). Then the find-or-update logic reads back notes and searches `body.includes(MARKER)`.

**Python urllib example for GitLab note search + update:**
```python
import json, urllib.request, os

MARKER = "<!-- acd-diff-report -->"
API_BASE = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
PROJECT_ID = os.environ.get("CI_PROJECT_ID", "")
MR_IID = os.environ.get("CI_MERGE_REQUEST_IID", "")
TOKEN = os.environ.get("GITLAB_TOKEN", "")

def _headers():
    return {"PRIVATE-TOKEN": TOKEN, "Content-Type": "application/json"}

def list_notes() -> list[dict]:
    url = f"{API_BASE}/projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes?per_page=100"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def post_note(body: str) -> None:
    url = f"{API_BASE}/projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes"
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    urllib.request.urlopen(req, timeout=10)

def update_note(note_id: int, body: str) -> None:
    url = f"{API_BASE}/projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes/{note_id}"
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PUT")
    urllib.request.urlopen(req, timeout=10)

def post_or_update_note(body: str) -> None:
    if not TOKEN:
        print("GITLAB_TOKEN not set — skipping comment post")
        return
    notes = list_notes()
    existing = next((n for n in notes if MARKER in n.get("body", "")), None)
    if existing:
        update_note(existing["id"], body)
        print(f"Updated existing MR note {existing['id']}")
    else:
        post_note(body)
        print("Created new MR note")
```

**`.gitlab-ci.yml` script change:** Replace the current `curl POST` shell block with a `python3 -c` call or a new standalone post script. Cleanest: add `post_or_update_note.py` under `.gitlab/scripts/` and call it from `script:`.

**Test:** Add `test_ci_gitlab_comment.py` mirroring `test_ci_github_comment.py`. Tests:
1. `build_comment()` output starts with `<!-- acd-diff-report -->` marker
2. `build_no_files_comment()` output starts with marker
3. `post_or_update_note()` calls PUT when existing note with marker found
4. `post_or_update_note()` calls POST when no existing note with marker found

Import pattern: `sys.path.insert(0, "/Users/laxmikantmukkawar/alteryx/.gitlab/scripts")` (matching `test_ci_github_comment.py` line 24 pattern for the GitLab script path).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Tab programmatic switch | Custom event system or DOM query | Radix Tabs `value` + `onValueChange` controlled mode |
| Error state display | Toast library | Inline `<p className="text-xs text-red-500">` (existing pattern in codebase) |
| Return type narrowing | Runtime `typeof` checks at call sites | Python `@typing.overload` decorators |
| GitLab note dedup | Custom state file or pipeline cache | GitLab Notes REST API GET + marker search |

---

## Common Pitfalls

### Pitfall 1: Autostart Guard Placement
**What goes wrong:** Placing the `is_autostart_enabled()` check inside `register_autostart()` instead of in `main.py`.
**Why it happens:** Seems cleaner to self-guard inside the function.
**How to avoid:** Keep the guard in `main.py`. `register_autostart()` is a low-level operation that should remain idempotent and transparent. The policy decision (when to register) belongs in the caller.

### Pitfall 2: Tabs Controlled Mode — defaultValue vs value
**What goes wrong:** Leaving `defaultValue="github"` alongside adding `value={activeTab}` — React will warn about controlled/uncontrolled mixing.
**How to avoid:** Remove `defaultValue` entirely when switching to controlled mode. Use `value={activeTab}` only.

### Pitfall 3: GitLab MR IID vs ID
**What goes wrong:** Using `CI_MERGE_REQUEST_ID` (global ID) instead of `CI_MERGE_REQUEST_IID` (project-scoped ID).
**How to avoid:** The notes API path uses `merge_requests/:iid` — must use `CI_MERGE_REQUEST_IID`. The current `.gitlab-ci.yml` already uses `CI_MERGE_REQUEST_IID` at line 71 — maintain consistency.

### Pitfall 4: Marker in GitLab Comment Body
**What goes wrong:** Adding the marker to the shell `curl` command JSON payload (in `.gitlab-ci.yml`) instead of in the Python `build_comment()` output.
**How to avoid:** Consistent with GitHub version where Python owns the marker (`build_comment()` outputs `<!-- acd-diff-report -->` as first line). The JavaScript GitHub Actions step reads the file and does NOT prepend the marker. Same pattern for GitLab: Python owns it, shell/Python post step reads it.

### Pitfall 5: Removing gitlab_repo_url Without Checking renderPushButton Logic
**What goes wrong:** Removing the field but `renderPushButton('gitlab')` still references it somewhere.
**How to avoid:** `renderPushButton` uses `remoteStatus.repo_url` (not `gitlab_repo_url`) for the "No remote repo yet" check. Confirmed at line 276 and 282 of `RemotePanel.tsx`. Safe to remove.

### Pitfall 6: AppShell mergeBaseSha state after removing HistoryPanel prop
**What goes wrong:** Removing the prop from HistoryPanelProps but leaving `mergeBaseSha={mergeBaseSha}` in the JSX call in `AppShell.tsx` — TypeScript error at compile time.
**How to avoid:** Remove both: the interface declaration in `HistoryPanel.tsx` AND the prop value `mergeBaseSha={mergeBaseSha}` from the `HistoryPanel` JSX in `AppShell.tsx`. The `mergeBaseSha` state in AppShell itself must stay — it is still passed to `DiffViewer` as `compareTo={mergeBaseSha}`.

---

## Code Examples

### Autostart Guard (main.py)
```python
# Source: app/main.py, replacing lines 85-87
from app.services import autostart  # noqa: PLC0415
if not autostart.is_autostart_enabled():
    autostart.register_autostart()
```

### Test for autostart guard
```python
# Source: tests/test_main.py — new test
def test_main_does_not_reregister_when_already_enabled():
    """main() must NOT call register_autostart() if autostart is already enabled."""
    with (
        patch("app.main.is_instance_running", return_value=False),
        patch("app.main.find_available_port", return_value=(7433, MagicMock())),
        patch("app.main.autostart.is_autostart_enabled", return_value=True),
        patch("app.main.autostart.register_autostart") as mock_register,
        patch("app.main.tray.start_tray"),
        patch("asyncio.run"),
        patch("threading.Thread"),
        patch("sys.argv", ["app"]),
    ):
        from app.main import main
        main()
    mock_register.assert_not_called()
```

### Controlled Tabs (RemotePanel.tsx)
```typescript
// Add state alongside other state declarations at top of RemotePanel
const [activeTab, setActiveTab] = useState<'github' | 'gitlab'>('github')

// Replace defaultValue with value+onValueChange
<Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'github' | 'gitlab')}>

// Replace DOM query in renderDisconnectedCTA:
<Button size="sm" variant="outline" onClick={() => setActiveTab('gitlab')}>
  Connect GitLab
</Button>
```

### Add project error display (App.tsx)
```typescript
// New state
const [addProjectError, setAddProjectError] = useState<string | null>(null)

// In doAddProject:
if (!addRes.ok) {
  const data = await addRes.json().catch(() => ({}))
  setAddProjectError(
    addRes.status === 409
      ? 'This folder is already registered.'
      : (data.detail ?? 'Could not add project. Try again.')
  )
  return
}

// In JSX — render near the AlertDialog or after WelcomeScreen onAddFolder:
{addProjectError && (
  <p className="text-sm text-red-500 mt-2">{addProjectError}</p>
)}
```

### Python @overload for config_store
```python
# Source: app/services/config_store.py
from typing import overload

@overload
def get_remote_repo(project_id: str, provider: str) -> str | None: ...
@overload
def get_remote_repo(project_id: str, provider: None = None) -> dict: ...
def get_remote_repo(project_id: str, provider: str | None = None) -> dict | str | None:
    """Return the remote repo info for project_id.

    Without provider: returns the full info dict
      {"github_url": "...", "gitlab_url": "..."} — empty dict if unset.
    With provider ("github" or "gitlab"): returns the URL string, or None if unset.
    """
    cfg = load_config()
    info = cfg.get("remote_repos", {}).get(project_id, {})
    if provider is not None:
        return info.get(f"{provider}_url")
    return info
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `document.querySelector` for tab switching | Radix Tabs controlled `value` prop | Decoupled from DOM structure |
| Silent `return` on fetch error | Inline error state + `<p className="text-xs text-red-500">` | User sees feedback |
| Unconditional `register_autostart()` | Guard with `is_autostart_enabled()` | Respects user preference |
| `curl POST` for every CI run | GET-search-then-PUT/POST pattern | Single comment per MR |

---

## Open Questions

1. **Where to display the add-project error in App.tsx**
   - What we know: The error occurs inside `doAddProject()` which is called both from `handleConfirmGitInit()` (after dialog closes) and from `handleAddFolder()` (step 3b, no dialog).
   - What's unclear: If the AlertDialog for git-init is already closed when the error fires, the error needs a separate display location. The welcome screen `WelcomeScreen` component would need to accept an error prop, or a separate inline toast container is needed.
   - Recommendation: Add `addProjectError` state to `App.tsx`, render it as a floating error near the "Add project" button entry point. Since both `WelcomeScreen` and `AppShell` show the Add button, the simplest fix is to render the error in `App.tsx` directly (not inside a child component), e.g. as a fixed-position `<div>` or at the root level before the router.

2. **gitlab_repo_url asymmetry — do renderPushButton(gitlab) callers need a separate URL?**
   - What we know: `renderPushButton('gitlab')` reads `remoteStatus.repo_url` (line 276) which only carries the GitHub repo URL in the current merged status shape.
   - What's unclear: If GitLab push button should show the GitLab repo URL (not GitHub's), this is a separate feature. The audit item is only about removing dead interface surface, not fixing the asymmetry.
   - Recommendation: Remove the dead field as stated; note in comments that per-provider `repo_url` is a future improvement if needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/test_autostart.py tests/test_main.py tests/test_projects.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-02 | `main()` does NOT call `register_autostart()` when `is_autostart_enabled()` is True | unit | `pytest tests/test_main.py -x -q -k autostart` | ✅ (test file exists, new test needed) |
| ONBOARD-02 | `POST /api/projects` 400/409 responses surface error text in UI | manual | Visual verification | N/A |
| REMOTE-02 | GitLab tab switches via controlled state (no DOM query) | manual | Visual verification | N/A |
| CI-01 | GitLab `build_comment()` starts with marker; find-or-update calls PUT on match | unit | `pytest tests/test_ci_gitlab_comment.py -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_main.py tests/test_autostart.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ci_gitlab_comment.py` — covers CI-01 marker + find-or-update logic
  - Framework install: none required (stdlib + sys.path pattern matches existing `test_ci_github_comment.py`)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app/main.py` — unconditional `register_autostart()` at line 87 confirmed
- Direct code inspection: `app/services/autostart.py` — `is_autostart_enabled()` function confirmed present
- Direct code inspection: `app/frontend/src/components/RemotePanel.tsx` — `document.querySelector` at lines 531–533 confirmed
- Direct code inspection: `app/frontend/src/components/HistoryPanel.tsx` — `mergeBaseSha?: string | null` at line 46, never destructured in function body confirmed
- Direct code inspection: `app/services/config_store.py` — dual return type at line 35 confirmed
- Direct code inspection: `/Users/laxmikantmukkawar/alteryx/.gitlab-ci.yml` — unconditional `curl POST .../notes` at lines 60–75 confirmed
- Direct code inspection: `/Users/laxmikantmukkawar/alteryx/.gitlab/scripts/generate_diff_comment.py` — no MARKER in `build_comment()` confirmed
- Direct code inspection: `/Users/laxmikantmukkawar/alteryx/.github/scripts/generate_diff_comment.py` — MARKER pattern at line 232 confirmed (reference implementation)
- Direct code inspection: `app/frontend/src/App.tsx` — silent `return` on non-ok response at lines 76–79 confirmed

### Secondary (MEDIUM confidence)
- v1.1 milestone audit: `.planning/v1.1-MILESTONE-AUDIT.md` — all 7 items listed and described precisely

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all changes to existing well-understood files
- Architecture: HIGH — all fix patterns derived from existing codebase conventions
- Pitfalls: HIGH — each pitfall discovered by reading the actual code path, not speculative

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (stable — no fast-moving dependencies involved)
