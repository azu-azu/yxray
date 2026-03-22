# Phase 11: Onboarding and Project Management - Research

**Researched:** 2026-03-13
**Domain:** React app shell layout, FastAPI project endpoints, Python folder picker, git subprocess operations, cross-platform config persistence
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Welcome screen: single splash screen (centered card), shown only when zero project folders are registered; never shown again after first folder added
- Welcome screen content: app name + tagline + 3-4 bullets + single CTA button that opens OS native folder picker
- App shell: always-visible fixed-width left sidebar (220px), not collapsible
- Sidebar project entries: folder basename only, no path, no badge in Phase 11
- Main content: empty-state guidance card when project has no saved versions
- '+' icon button pinned at sidebar top (accessible once one project exists)
- Right-click on sidebar project item: "Remove project" context menu — removes from list only, no file deletion, requires confirmation dialog
- Folder picker: OS native dialog via Python backend (tkinter.filedialog or equivalent)
- git init confirmation: plain-language dialog before running git init if folder has no git history
- git init if already has history: add silently, no confirmation
- Project metadata: persisted in JSON config at `%APPDATA%\AlteryxGitCompanion\config.json` (Windows) / platformdirs equivalent on macOS
- Git identity check: immediately after folder added successfully; if missing, show inline setup card in main content area
- Git identity: saved to global git config via `git config --global`
- After git identity saved: dismiss inline card, replace with standard empty-state panel

### Claude's Discretion
- Exact folder picker Python implementation (tkinter vs win32api vs subprocess)
- JSON config schema details (keys, versioning)
- Sidebar component styling details (hover states, active indicator, spacing)
- Exact copy for empty state and welcome screen bullets
- Error handling for edge cases (permission denied on folder, git not installed)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ONBOARD-01 | User sees a first-run welcome screen explaining what the app does before any setup | Welcome screen render logic (show when projects list is empty), React conditional rendering pattern, centered card UI |
| ONBOARD-02 | User can add a project folder — app auto-initializes git if folder is not already a repo | `/api/folder-picker` endpoint, `tkinter.filedialog.askdirectory`, `subprocess.run(["git", "init"])`, `.git` directory detection |
| ONBOARD-03 | App detects missing git user identity (name/email) and prompts for it on first use | `subprocess.run(["git", "config", "--global", "user.name"])`, inline setup card pattern, POST `/api/git/identity` |
| ONBOARD-04 | User can register and switch between multiple project folders from a left-panel project list | Zustand store for project list + active project, sidebar component, `/api/projects` CRUD endpoints, `platformdirs` config path |
</phase_requirements>

---

## Summary

Phase 11 replaces the scaffold `App.tsx` with a full app shell: a fixed sidebar listing registered project folders and a main content area that conditionally shows the welcome screen, the git-identity prompt, or the empty-state panel. The backend grows three API routers (projects, git-identity, folder-picker) and a persistent JSON config file managed via `platformdirs`.

The most critical technical decision is how to invoke the OS folder picker from a browser-based frontend. The chosen approach is a dedicated FastAPI endpoint (`POST /api/folder-picker`) that calls `tkinter.filedialog.askdirectory()` in a thread pool so the event loop is not blocked. tkinter requires a hidden root window (`Tk().withdraw()`) but works reliably on both Windows and macOS in development and in PyInstaller bundles (tkinter is bundled automatically).

State management for the active-project and project-list data is cleanly handled by Zustand — a single store file, no providers, fine-grained subscriptions. React Context would also work for this phase's scope but Zustand is the better investment given Phase 12–14 will add file-watch state and history.

**Primary recommendation:** Use Zustand for frontend state, `platformdirs.user_data_dir` for config path, `tkinter.filedialog.askdirectory` + `asyncio.to_thread` for folder picker, and FastAPI `APIRouter` per feature area (projects, git, folder-picker).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Zustand | ^5.x (npm) | Active project + project list state | No-provider pattern, fine-grained subscriptions, trivial to add persist middleware later; standard for desktop-like React apps |
| shadcn/ui | latest (already configured) | Sidebar, Dialog, AlertDialog, ContextMenu, Card, Input, Button components | Already in project; Tailwind v4 compatible as of Feb 2025 |
| lucide-react | ^0.577 (already installed) | Icons: FolderPlus, FolderOpen, Trash2, ChevronRight | Already in package.json |
| platformdirs | ^4.x (Python) | Cross-platform config directory resolution | `user_data_dir("AlteryxGitCompanion")` returns `%APPDATA%\AlteryxGitCompanion` on Windows, `~/Library/Application Support/AlteryxGitCompanion` on macOS |
| FastAPI APIRouter | built-in | Group endpoints by feature area | Standard FastAPI pattern; keeps server.py clean |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `subprocess` | stdlib | Run `git init`, `git config --global` | All git CLI operations — no extra dependency |
| Python `tkinter.filedialog` | stdlib | OS native folder picker dialog | Phase 11 folder-picker endpoint only |
| Python `json` | stdlib | Read/write config.json | Config persistence |
| Python `asyncio.to_thread` | stdlib (3.9+) | Run blocking tkinter dialog in thread pool | Required — tkinter.askdirectory() is blocking; must not block FastAPI event loop |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Zustand | React Context | Context re-renders all consumers on any change; Zustand selectors prevent this. Phase 12 will add watched-files state making Context more painful. Use Zustand. |
| Zustand | Jotai | Jotai is atom-based (more granular), adds complexity for a handful of global values. Zustand's single-store model is simpler here. |
| platformdirs | `os.environ.get("APPDATA")` manual | Manual approach breaks on macOS dev; platformdirs already available in the Python environment and handles both. |
| tkinter.filedialog | win32api ShellBrowseForFolder | win32api only works on Windows; tkinter is cross-platform and stdlib. |
| subprocess git ops | GitPython | GitPython adds a large dependency for operations that are 2-3 subprocess calls. Not worth it. |

**Installation (new deps only):**
```bash
# Frontend
cd app/frontend && npm install zustand

# Backend — add to pyproject.toml dependencies
platformdirs>=4.0
```

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── server.py               # Include new routers here (app.include_router)
├── routers/
│   ├── __init__.py
│   ├── projects.py         # GET /api/projects, POST /api/projects, DELETE /api/projects/{id}
│   ├── git_identity.py     # GET /api/git/identity, POST /api/git/identity
│   └── folder_picker.py    # POST /api/folder-picker
├── services/
│   ├── __init__.py
│   ├── config_store.py     # Read/write JSON config via platformdirs
│   └── git_ops.py          # git init check, git config read/write
└── frontend/
    └── src/
        ├── App.tsx          # Replace scaffold: render WelcomeScreen or AppShell
        ├── store/
        │   └── useProjectStore.ts  # Zustand store
        ├── components/
        │   ├── AppShell.tsx        # Sidebar + main content layout
        │   ├── Sidebar.tsx         # Project list + add button
        │   ├── WelcomeScreen.tsx   # First-run splash card
        │   ├── EmptyState.tsx      # "No saved versions yet" guidance card
        │   └── GitIdentityCard.tsx # Inline name/email setup card
        └── hooks/
            └── useProjects.ts      # API fetch hooks (or inline in store)
```

### Pattern 1: FastAPI APIRouter per Feature

**What:** Each feature domain gets its own router file; `server.py` includes all routers.
**When to use:** Always — keeps `server.py` as a thin orchestrator.

```python
# app/routers/projects.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.config_store import load_config, save_config

router = APIRouter(prefix="/api/projects", tags=["projects"])

class ProjectIn(BaseModel):
    path: str

@router.get("")
def list_projects():
    cfg = load_config()
    return cfg.get("projects", [])

@router.post("", status_code=201)
def add_project(body: ProjectIn):
    # Validate path exists, check/run git init, persist
    ...
```

```python
# app/server.py — add after existing code
from app.routers import projects, git_identity, folder_picker

app.include_router(projects.router)
app.include_router(git_identity.router)
app.include_router(folder_picker.router)
```

### Pattern 2: platformdirs Config Store

**What:** Single module that owns reading and writing the JSON config file.
**When to use:** All config access goes through this module — no direct file I/O elsewhere.

```python
# app/services/config_store.py
import json
from pathlib import Path
import platformdirs

APP_NAME = "AlteryxGitCompanion"

def _config_path() -> Path:
    data_dir = Path(platformdirs.user_data_dir(APP_NAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "config.json"

def load_config() -> dict:
    p = _config_path()
    if not p.exists():
        return {"version": 1, "projects": [], "active_project": None}
    return json.loads(p.read_text(encoding="utf-8"))

def save_config(cfg: dict) -> None:
    _config_path().write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
```

**Config schema (minimal, Phase 12 compatible):**
```json
{
  "version": 1,
  "projects": [
    { "id": "uuid4-string", "path": "/absolute/path/to/folder", "name": "folder-basename" }
  ],
  "active_project": "uuid4-string-or-null"
}
```

### Pattern 3: Folder Picker via asyncio.to_thread

**What:** FastAPI endpoint triggers tkinter dialog in a thread (blocking call off event loop).
**When to use:** Any blocking OS call from an async FastAPI endpoint.

```python
# app/routers/folder_picker.py
import asyncio
import tkinter as tk
from tkinter import filedialog
from fastapi import APIRouter

router = APIRouter(prefix="/api/folder-picker", tags=["folder-picker"])

def _pick_folder() -> str | None:
    """Must run in a thread — tkinter is blocking."""
    root = tk.Tk()
    root.withdraw()           # Hide the root window
    root.wm_attributes("-topmost", True)  # Bring dialog to front on Windows
    path = filedialog.askdirectory(title="Select Workflows Folder")
    root.destroy()
    return path or None

@router.post("")
async def pick_folder():
    selected = await asyncio.to_thread(_pick_folder)
    if selected is None:
        return {"path": None, "cancelled": True}
    return {"path": selected, "cancelled": False}
```

**Key detail:** `root.wm_attributes("-topmost", True)` is required on Windows for the dialog to appear in front of the browser window. Without it the dialog opens behind the browser and appears frozen.

### Pattern 4: Git Operations Service

**What:** Centralized subprocess wrappers for git operations.
**When to use:** Any git operation — `git init`, `git config` reads/writes.

```python
# app/services/git_ops.py
import subprocess
from pathlib import Path

def is_git_repo(folder: str) -> bool:
    """Return True if folder is inside a git repository."""
    result = subprocess.run(
        ["git", "-C", folder, "rev-parse", "--git-dir"],
        capture_output=True, text=True
    )
    return result.returncode == 0

def git_init(folder: str) -> None:
    subprocess.run(
        ["git", "-C", folder, "init"],
        capture_output=True, text=True, check=True
    )

def get_git_identity() -> dict:
    """Return {"name": str|None, "email": str|None}."""
    def _get(key: str) -> str | None:
        r = subprocess.run(
            ["git", "config", "--global", key],
            capture_output=True, text=True
        )
        return r.stdout.strip() or None
    return {"name": _get("user.name"), "email": _get("user.email")}

def set_git_identity(name: str, email: str) -> None:
    subprocess.run(["git", "config", "--global", "user.name", name], check=True)
    subprocess.run(["git", "config", "--global", "user.email", email], check=True)
```

### Pattern 5: Zustand Project Store

**What:** Single Zustand store owns project list and active project; components subscribe selectively.
**When to use:** All frontend state for project management — no prop drilling.

```typescript
// src/store/useProjectStore.ts
import { create } from 'zustand'

export interface Project {
  id: string
  path: string
  name: string
}

interface ProjectStore {
  projects: Project[]
  activeProjectId: string | null
  setProjects: (projects: Project[]) => void
  setActiveProject: (id: string) => void
  removeProject: (id: string) => void
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],
  activeProjectId: null,
  setProjects: (projects) => set({ projects }),
  setActiveProject: (id) => set({ activeProjectId: id }),
  removeProject: (id) =>
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      activeProjectId: state.activeProjectId === id ? null : state.activeProjectId,
    })),
}))
```

### Pattern 6: App-Level Routing (No React Router)

**What:** Phase 11 has no URL-based routing needs — the app is always single-view. Use conditional rendering on project state rather than a router.
**When to use:** Until Phase 14+ introduces distinct views (history screen).

```tsx
// src/App.tsx
import { useProjectStore } from './store/useProjectStore'
import { WelcomeScreen } from './components/WelcomeScreen'
import { AppShell } from './components/AppShell'

export default function App() {
  const projects = useProjectStore((s) => s.projects)
  if (projects.length === 0) return <WelcomeScreen />
  return <AppShell />
}
```

### Pattern 7: shadcn ContextMenu for "Remove Project"

**What:** Right-click on a sidebar project item opens a ContextMenu with "Remove project" action.
**When to use:** Phase 11 sidebar item — one action only.

```tsx
import {
  ContextMenu, ContextMenuContent,
  ContextMenuItem, ContextMenuTrigger,
} from '@/components/ui/context-menu'

<ContextMenu>
  <ContextMenuTrigger asChild>
    <button className="w-full text-left px-3 py-2 ...">
      {project.name}
    </button>
  </ContextMenuTrigger>
  <ContextMenuContent>
    <ContextMenuItem
      className="text-destructive"
      onSelect={() => setConfirmRemove(project)}
    >
      Remove project
    </ContextMenuItem>
  </ContextMenuContent>
</ContextMenu>
```

Pair with shadcn `AlertDialog` for the confirmation step. Use `AlertDialog` (not `Dialog`) because the action is destructive in intent (even though it doesn't delete files).

### Anti-Patterns to Avoid

- **Calling tkinter.askdirectory() directly in an async endpoint without `asyncio.to_thread`:** Blocks the uvicorn event loop, hangs all other requests.
- **Importing tkinter at module level:** On some headless CI environments tkinter import fails if no display is present. Import inside the function body or guard with `try/except`.
- **Storing absolute paths as project display names:** basename only in the sidebar, per CONTEXT.md.
- **Skipping `root.destroy()` after askdirectory:** Leaves zombie Tk instances; always destroy the root in a finally block.
- **Using React Context for project list:** Will cause excessive re-renders when Phase 12 adds file-watch status to sidebar items. Start with Zustand.
- **Exposing `git init` details in the UI:** Never show git jargon. "We'll set it up for version control" is the correct abstraction level.
- **Writing config.json without `parents=True, exist_ok=True` on the directory:** First run will fail if `%APPDATA%\AlteryxGitCompanion\` doesn't exist yet.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform config dir | `os.environ.get("APPDATA")` with manual platform checks | `platformdirs.user_data_dir()` | Handles Windows, macOS, Linux; accounts for roaming vs local on Windows |
| Right-click menu | Custom onMouseDown/onContextMenu handler + absolute-positioned div | shadcn ContextMenu (Radix UI) | Accessibility, keyboard nav, z-index, portal rendering all handled |
| Confirmation dialog | Custom modal state + portal | shadcn AlertDialog | Focus trap, Escape key, ARIA roles; 3 lines to install |
| OS folder picker UI | Browser `<input type="file" webkitdirectory>` | Backend tkinter.filedialog.askdirectory | Browser file input cannot return an absolute server-side path; tkinter returns the real filesystem path the backend can use directly |
| uuid generation | random string | Python `uuid.uuid4()` | Collision-resistant project IDs for config.json |

**Key insight:** The folder picker is the most deceptively complex piece. Browser file inputs are sandboxed and can't return usable server-side paths. The backend tkinter approach is the correct pattern for a desktop-style Python+React app.

---

## Common Pitfalls

### Pitfall 1: tkinter Dialog Appears Behind Browser Window (Windows)
**What goes wrong:** `filedialog.askdirectory()` opens but is hidden under the browser; user sees a frozen UI.
**Why it happens:** Windows z-order — tkinter root spawns behind whatever has focus.
**How to avoid:** Set `root.wm_attributes("-topmost", True)` before calling `askdirectory()`. This forces the dialog to the foreground.
**Warning signs:** Manual test shows dialog not appearing within 1-2 seconds of clicking the button.

### Pitfall 2: tkinter Import Crash in Headless CI
**What goes wrong:** `import tkinter` raises `_tkinter.TclError: no display name and no $DISPLAY environment variable` in CI.
**Why it happens:** CI runners have no display server; tkinter can't initialize Tk.
**How to avoid:** Import tkinter inside the `_pick_folder()` function body (not at module level). The import never runs in tests because the endpoint is mocked. Alternatively mock `app.routers.folder_picker._pick_folder` in tests.
**Warning signs:** Test suite crashes on import of `folder_picker.py`.

### Pitfall 3: asyncio.to_thread Not Available
**What goes wrong:** `AttributeError: module 'asyncio' has no attribute 'to_thread'` on Python < 3.9.
**Why it happens:** `asyncio.to_thread` was added in 3.9; project requires 3.11+ so this is not a real risk, but worth noting.
**How to avoid:** `pyproject.toml` already requires `python >= 3.11`. No action needed.

### Pitfall 4: Config Written with Wrong Path Separator (Windows)
**What goes wrong:** Config stored at a path that doesn't resolve on reload because backslash vs forward slash mismatch.
**Why it happens:** Manual string path construction. Python `Path` objects serialize to OS-native separators.
**How to avoid:** Always store `str(Path(folder).resolve())` in config.json. Use `Path(stored_path)` to reconstruct. Never use raw string concatenation.

### Pitfall 5: git config --global Returns Exit 1 When Value Not Set
**What goes wrong:** `subprocess.run(["git", "config", "--global", "user.name"], check=True)` raises `CalledProcessError` when user.name is not configured.
**Why it happens:** `git config --get` returns exit code 1 when the key is absent (not an error, just missing).
**How to avoid:** Use `check=False` (not `check=True`) and treat returncode 1 + empty stdout as "not configured". Only treat returncode > 1 as an error.

### Pitfall 6: Welcome Screen Shown Spuriously on Reload
**What goes wrong:** App shows welcome screen on every page reload even after folders are registered.
**Why it happens:** Zustand store is initialized from memory; if not hydrated from the API on mount, projects starts as `[]`.
**How to avoid:** `useEffect(() => { fetchProjects().then(setProjects) }, [])` in App.tsx before rendering. Show a loading state (or nothing) until hydration completes.

### Pitfall 7: Removing Active Project Leaves App in Broken State
**What goes wrong:** User removes the currently active project; sidebar shows nothing selected but main content area renders stale content.
**Why it happens:** `activeProjectId` still points to the removed project's ID.
**How to avoid:** In `removeProject` Zustand action, set `activeProjectId` to `null` if it matches the removed ID. App.tsx then renders empty state or auto-selects first remaining project.

---

## Code Examples

Verified patterns from official sources:

### shadcn ContextMenu Installation
```bash
# Source: ui.shadcn.com/docs/components/radix/context-menu
cd app/frontend && npx shadcn@latest add context-menu
```

### shadcn AlertDialog Installation
```bash
cd app/frontend && npx shadcn@latest add alert-dialog
```

### shadcn Dialog Installation (for git-identity card — optional, may use inline card instead)
```bash
cd app/frontend && npx shadcn@latest add dialog card input button
```

### platformdirs user_data_dir
```python
# Source: platformdirs.readthedocs.io
import platformdirs
# Windows: C:\Users\<user>\AppData\Local\AlteryxGitCompanion
# macOS:   ~/Library/Application Support/AlteryxGitCompanion
data_dir = platformdirs.user_data_dir("AlteryxGitCompanion")
```

### Zustand store (minimal)
```typescript
// Source: github.com/pmndrs/zustand
import { create } from 'zustand'
const useStore = create((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
}))
```

### FastAPI include_router
```python
# Source: fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import FastAPI
from app.routers import projects, git_identity, folder_picker

app = FastAPI()
app.include_router(projects.router)
app.include_router(git_identity.router)
app.include_router(folder_picker.router)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Redux for React global state | Zustand (simpler) or React Query + Zustand | 2021-2023 shift | No boilerplate, no provider hell for simple global state |
| React Context for everything | Context for static config; Zustand for dynamic shared state | 2022+ | Avoids render-cascade performance problems |
| shadcn/ui Tailwind v3 config | Tailwind v4 `@theme` CSS block | Feb 2025 | Already in this project; no tailwind.config.js needed |
| `appdirs` Python library | `platformdirs` (fork, actively maintained) | 2022 | platformdirs is the current standard; appdirs is legacy |

**Deprecated/outdated:**
- `appdirs`: replaced by `platformdirs`; same API but actively maintained
- `tkinter.filedialog` called on main thread in FastAPI: blocks event loop; always use `asyncio.to_thread`

---

## Open Questions

1. **shadcn components not yet installed**
   - What we know: `components.json` is configured, no `src/components/ui/` directory exists yet
   - What's unclear: Whether the planner should include component installation as explicit Wave 0 tasks or inline with the first component that uses them
   - Recommendation: Make Wave 0 install all required shadcn components upfront: `button card input alert-dialog context-menu`

2. **platformdirs not in pyproject.toml**
   - What we know: It is available in the dev environment (confirmed by `python3 -c "import platformdirs"`) but not listed in `pyproject.toml` dependencies
   - What's unclear: Whether it is a transitive dependency or just present in the venv
   - Recommendation: Add `platformdirs>=4.0` explicitly to `pyproject.toml` dependencies; don't rely on transitive availability

3. **`app/routers/` directory doesn't exist yet**
   - What we know: Current `app/` has only `server.py`, `main.py`, `__init__.py`, `frontend/`
   - What's unclear: Nothing — this is a known gap
   - Recommendation: Wave 0 plan creates `app/routers/__init__.py` and `app/services/__init__.py` as scaffolding

4. **Zustand not in package.json**
   - What we know: Not listed in dependencies; must be added
   - What's unclear: Whether version 4 or 5 — Zustand v5 released late 2024 with breaking changes to the `create` API import
   - Recommendation: Install `zustand@^5` (v5 is current); the `create` import pattern is `import { create } from 'zustand'` in both v4 and v5

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_projects.py tests/test_git_ops.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ONBOARD-01 | GET /api/projects returns [] on first run (triggers welcome screen client-side) | unit (API) | `pytest tests/test_projects.py::test_list_projects_empty -x` | Wave 0 |
| ONBOARD-02 | POST /api/projects with valid folder: adds to config, returns 201 | unit (API) | `pytest tests/test_projects.py::test_add_project_new_git_repo -x` | Wave 0 |
| ONBOARD-02 | POST /api/projects with folder that has no .git: git init is called | unit (API+mock) | `pytest tests/test_projects.py::test_add_project_runs_git_init -x` | Wave 0 |
| ONBOARD-02 | POST /api/projects with folder that has .git: git init NOT called | unit (API+mock) | `pytest tests/test_projects.py::test_add_project_skips_git_init -x` | Wave 0 |
| ONBOARD-03 | GET /api/git/identity returns null name/email when not configured | unit (API+mock) | `pytest tests/test_git_identity.py::test_get_identity_missing -x` | Wave 0 |
| ONBOARD-03 | POST /api/git/identity sets global user.name and user.email | unit (API+mock) | `pytest tests/test_git_identity.py::test_set_identity -x` | Wave 0 |
| ONBOARD-04 | DELETE /api/projects/{id} removes project from config | unit (API) | `pytest tests/test_projects.py::test_remove_project -x` | Wave 0 |
| ONBOARD-04 | GET /api/projects returns multiple registered projects | unit (API) | `pytest tests/test_projects.py::test_list_multiple_projects -x` | Wave 0 |

### Frontend Testing
Frontend behaviour (welcome screen toggle, sidebar rendering) is manual-only in Phase 11 — no Jest/Vitest installed. The planner should include manual verification steps but not automated frontend test tasks.

### Sampling Rate
- **Per task commit:** `pytest tests/test_projects.py tests/test_git_ops.py tests/test_server.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_projects.py` — covers ONBOARD-01, ONBOARD-02, ONBOARD-04
- [ ] `tests/test_git_identity.py` — covers ONBOARD-03
- [ ] `app/routers/__init__.py` — empty package marker
- [ ] `app/services/__init__.py` — empty package marker
- [ ] `app/routers/projects.py` — skeleton (router defined, no logic)
- [ ] `app/routers/git_identity.py` — skeleton
- [ ] `app/routers/folder_picker.py` — skeleton
- [ ] `app/services/config_store.py` — skeleton
- [ ] `app/services/git_ops.py` — skeleton
- [ ] Frontend: `npm install zustand` in `app/frontend/`
- [ ] Frontend: `npx shadcn@latest add button card input alert-dialog context-menu` in `app/frontend/`
- [ ] Backend: add `platformdirs>=4.0` to `pyproject.toml` dependencies

---

## Sources

### Primary (HIGH confidence)
- FastAPI official docs (fastapi.tiangolo.com/tutorial/bigger-applications/) — APIRouter pattern
- Python stdlib docs (docs.python.org/3/library/dialog.html) — tkinter.filedialog.askdirectory
- platformdirs docs (platformdirs.readthedocs.io/en/latest/api.html) — user_data_dir behavior
- Python stdlib asyncio docs — asyncio.to_thread (Python 3.9+, confirmed available in project's 3.11+ requirement)
- shadcn/ui official docs (ui.shadcn.com/docs/components/radix/context-menu, alert-dialog) — component APIs
- Zustand GitHub (github.com/pmndrs/zustand) — store creation pattern

### Secondary (MEDIUM confidence)
- WebSearch verified: Zustand v5 import pattern `import { create } from 'zustand'` — consistent across multiple 2025 sources
- WebSearch verified: `root.wm_attributes("-topmost", True)` required for Windows focus — consistent across tkinter community sources
- WebSearch verified: platformdirs replaces appdirs as the current standard — confirmed by PyPI and GitHub activity

### Tertiary (LOW confidence)
- tkinter + PyInstaller threading behavior on macOS — mentioned in PyInstaller docs but not specifically tested for this use case; validate during dev

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib, already-installed, or verified in official docs
- Architecture: HIGH — FastAPI APIRouter pattern is official docs; Zustand pattern is direct from source
- Pitfalls: MEDIUM — tkinter Windows topmost behavior and CI headless issue confirmed by multiple community sources; not tested against this specific project setup

**Research date:** 2026-03-13
**Valid until:** 2026-06-13 (stable ecosystem — platformdirs, Zustand, shadcn APIs unlikely to break)
