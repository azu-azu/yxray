# Phase 12: File Watcher - Research

**Researched:** 2026-03-14
**Domain:** watchdog filesystem monitoring, FastAPI SSE, asyncio/threading bridge, network path detection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Change badge design**
- Count badge showing number of changed `.yxmd`/`.yxwz` files (e.g. "3")
- Positioned on the far right of the sidebar project row (float right)
- Amber/orange color — signals "attention needed" without alarm; consistent with yellow=modified in ACD diff graph
- Badge clears after the user saves a version (wired in Phase 13)

**Watcher state persistence**
- On startup, re-scan all registered projects using `git status --porcelain` against git HEAD to determine pending changes — badges restore accurately without storing stale state
- "Changed" means files modified vs git HEAD (not filesystem timestamps)
- Badge updates near-real-time with ~1–2 second debounce after OS event fires — avoids flicker during rapid Alteryx saves
- Frontend receives badge updates via Server-Sent Events (SSE) push from backend — no frontend polling

**Watcher lifecycle**
- All registered projects watched simultaneously — not just the active one
- Watcher starts immediately when a new project folder is added (dynamic registration, no restart required)
- Watcher stops immediately when a project is removed
- If native observer fails on a network drive, auto-retry with polling fallback silently — no error shown to user unless both modes fail repeatedly

**Observer selection (WATCH-02)**
- Auto-detect path type at watcher startup per project:
  - UNC paths (`\\server\share`) → polling observer (5-second interval)
  - Paths on network drives (detected via drive type / mount check) → polling observer
  - Local drives → native OS observer (watchdog's FSEventsObserver on macOS, ReadDirectoryChangesW on Windows)
  - No manual configuration required

**Watch status API (for WATCH-03 / Phase 13)**
- `GET /api/watch/status` returns per-project status:
  ```json
  {
    "project_id": {
      "changed_count": 3,
      "total_workflows": 12,
      "has_any_commits": false
    }
  }
  ```
- `has_any_commits: false` signals to Phase 13 that the initial commit warning is needed
- `total_workflows` is the count of `.yxmd`/`.yxwz` files scanned — used in the warning copy

**SSE endpoint**
- `GET /api/watch/events` — SSE stream that pushes badge update events to the React frontend
- Event format: `{type: "badge_update", project_id: "...", changed_count: N}`
- Frontend subscribes on mount, updates `useProjectStore` with change counts per project

### Claude's Discretion

- Exact watchdog observer class selection and threading model
- Debounce implementation details (asyncio vs threading.Timer)
- SMB/network drive detection mechanism (platform-specific)
- SSE connection reconnect logic on frontend
- How change counts are stored in-process between events

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WATCH-01 | App auto-detects changed .yxmd and .yxwz files in registered folders and shows a change badge | watchdog PatternMatchingEventHandler with `*.yxmd`/`*.yxwz` patterns; `git status --porcelain` to count vs HEAD; SSE badge_update events to React store |
| WATCH-02 | App auto-switches to polling observer (5-second interval) for network/SMB/UNC paths, native observer for local drives | `is_network_path()` helper using UNC prefix check + Windows `GetDriveType` DRIVE_REMOTE=4; watchdog `Observer` (native) vs `PollingObserver(timeout=5)` |
| WATCH-03 | App warns user when first version save will capture all N existing workflows in a folder | `GET /api/watch/status` returns `has_any_commits` + `total_workflows` per project; Phase 13 calls this endpoint; Phase 12 only supplies counts |
</phase_requirements>

---

## Summary

Phase 12 adds continuous file monitoring across all registered project folders, surfacing changes as amber count badges in the sidebar. The backend work centers on three pillars: (1) a singleton `WatcherManager` service that orchestrates watchdog observers per project, (2) a platform-aware path classifier that auto-selects native vs polling observers, and (3) an SSE endpoint that pushes badge update events to the React frontend without any frontend polling.

The watchdog library (v6.0.0, already installed in the environment) provides the core filesystem monitoring. Because watchdog observers run on their own daemon threads, events must cross the thread boundary into FastAPI's asyncio event loop using `loop.call_soon_threadsafe(queue.put_nowait, event)`. The sse-starlette library (v2.1.3, already installed) provides `EventSourceResponse` for SSE — `fastapi.sse` does NOT exist in FastAPI 0.115.x; the official docs page for it describes a version newer than what is installed.

The most subtle part of this phase is the debounce strategy: Alteryx Designer often writes a `.yxmd` file in multiple rapid bursts (temp file + rename, or partial writes). A 1–2 second `threading.Timer`-based debounce per project path is the standard approach — simpler than asyncio and correct because it only needs to reset a timer, not await coroutines.

**Primary recommendation:** Build `app/services/watcher_manager.py` as the central singleton. New `app/routers/watch.py` exposes SSE and status endpoints. Wire `add_project`/`remove_project` in `projects.py` to call into the manager. All change state lives in-process in the manager's dict — no database required.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| watchdog | 6.0.0 (installed) | Filesystem event monitoring | Only mature Python library for cross-platform OS-native file events |
| sse-starlette | 2.1.3 (installed) | SSE response type for FastAPI | Purpose-built for FastAPI/Starlette; `EventSourceResponse` wraps async generators cleanly |
| asyncio (stdlib) | Python 3.11+ | Event loop for SSE streaming | Already used by FastAPI's uvicorn runtime |
| threading (stdlib) | Python 3.11+ | Watchdog runs on daemon threads | Standard bridge pattern for watchdog ↔ asyncio |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| subprocess (stdlib) | Python 3.11+ | `git status --porcelain` for change counting | On startup re-scan; also post-watchdog-event to get authoritative changed list |
| ctypes (stdlib) | Python 3.11+ | Windows `GetDriveType` call for network drive detection | Windows only; needed to classify mapped drives (Z:\\) as network |
| pathlib (stdlib) | Python 3.11+ | Path manipulation for UNC detection | `str(path).startswith("\\\\")` for UNC check |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette EventSourceResponse | StreamingResponse with manual `data:...\n\n` formatting | Manual formatting is error-prone; sse-starlette handles keep-alive, reconnect headers, and proper SSE framing automatically |
| threading.Timer debounce | asyncio debounce via asyncio.sleep in coroutine | threading.Timer is simpler here — watchdog callbacks are already in a separate thread; asyncio debounce requires careful loop.call_soon_threadsafe plumbing |
| watchdog Observer (auto) | inotify / FSEvents direct | Observer auto-selects best native impl; no reason to bypass it for local drives |
| in-process dict for change state | Redis / SQLite | For a single-user desktop app this is massive over-engineering; dict survives all needed lifecycle events |

**Installation (nothing new required — both already in the environment):**
```bash
# Both already installed; add to pyproject.toml dependencies:
# watchdog>=6.0
# sse-starlette>=2.1
```

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── services/
│   ├── config_store.py       # existing — load_config() used by watcher on startup
│   ├── git_ops.py            # existing — add git_changed_workflows() helper
│   └── watcher_manager.py   # NEW — WatcherManager singleton
├── routers/
│   ├── projects.py           # existing — wire add/remove to watcher_manager
│   └── watch.py              # NEW — /api/watch/events and /api/watch/status
└── server.py                 # existing — include watch router, start watcher on startup
```

### Pattern 1: WatcherManager Singleton

**What:** A module-level singleton that holds all per-project Observer instances, their per-project change counts, and a list of active SSE subscriber queues.
**When to use:** Whenever code needs to start/stop watching a folder or read current change counts.

```python
# Source: https://python-watchdog.readthedocs.io/en/stable/api.html
# Source: https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6
import asyncio
import threading
from typing import Callable
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent

POLL_INTERVAL_SECONDS = 5
DEBOUNCE_SECONDS = 1.5

class WatcherManager:
    def __init__(self) -> None:
        self._observers: dict[str, Observer | PollingObserver] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._change_counts: dict[str, int] = {}  # project_id -> count
        self._total_workflows: dict[str, int] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once at FastAPI startup to capture the running event loop."""
        self._loop = loop

    def start_watching(self, project_id: str, path: str) -> None:
        """Start watching a project folder. Idempotent if already watching."""
        if project_id in self._observers:
            return
        observer = PollingObserver(timeout=POLL_INTERVAL_SECONDS) \
            if is_network_path(path) else Observer()
        handler = _WorkflowEventHandler(
            project_id=project_id,
            path=path,
            on_change=self._schedule_rescan,
        )
        observer.schedule(handler, path, recursive=False)
        observer.start()
        self._observers[project_id] = observer
        # Populate initial counts
        self._rescan(project_id, path)

    def stop_watching(self, project_id: str) -> None:
        if project_id not in self._observers:
            return
        obs = self._observers.pop(project_id)
        obs.stop()
        obs.join(timeout=2)
        self._change_counts.pop(project_id, None)
        self._total_workflows.pop(project_id, None)

    def _schedule_rescan(self, project_id: str, path: str) -> None:
        """Debounced: cancel any pending timer and restart the countdown."""
        if project_id in self._timers:
            self._timers[project_id].cancel()
        timer = threading.Timer(
            DEBOUNCE_SECONDS, self._rescan, args=(project_id, path)
        )
        timer.daemon = True
        self._timers[project_id] = timer
        timer.start()

    def _rescan(self, project_id: str, path: str) -> None:
        """Run git status, update counts, push SSE event."""
        from app.services.git_ops import git_changed_workflows, git_has_commits, count_workflows
        changed = git_changed_workflows(path)
        total = count_workflows(path)
        self._change_counts[project_id] = len(changed)
        self._total_workflows[project_id] = total
        self._push_badge_update(project_id, len(changed))

    def _push_badge_update(self, project_id: str, count: int) -> None:
        """Thread-safe push to all SSE subscriber queues."""
        if self._loop is None:
            return
        event = {"type": "badge_update", "project_id": project_id, "changed_count": count}
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, event)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q) if hasattr(self._subscribers, 'discard') \
            else (self._subscribers.remove(q) if q in self._subscribers else None)

    def get_status(self) -> dict:
        """Return per-project status dict for /api/watch/status."""
        from app.services.config_store import load_config
        from app.services.git_ops import git_has_commits
        result = {}
        for proj in load_config().get("projects", []):
            pid = proj["id"]
            path = proj["path"]
            result[pid] = {
                "changed_count": self._change_counts.get(pid, 0),
                "total_workflows": self._total_workflows.get(pid, 0),
                "has_any_commits": git_has_commits(path),
            }
        return result


watcher_manager = WatcherManager()
```

### Pattern 2: Network Path Detection

**What:** Determines whether a given path is on a network drive, triggering PollingObserver instead of native observer.
**When to use:** Called once per project in `start_watching`.

```python
# Source: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypea
import os
import platform
import ctypes

DRIVE_REMOTE = 4  # Windows GetDriveType constant

def is_network_path(path: str) -> bool:
    """Return True if path is on a network/SMB/UNC filesystem."""
    # Fast check: UNC path (\\server\share or //server/share)
    normalized = path.replace("\\", "/")
    if normalized.startswith("//"):
        return True
    if platform.system() == "Windows":
        # Get drive letter root (e.g. "Z:\\")
        drive = os.path.splitdrive(path)[0]
        if drive:
            root = drive + "\\"
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
                return drive_type == DRIVE_REMOTE
            except Exception:
                return False
    # macOS/Linux: check if path crosses a mount boundary
    # (st_dev of path differs from st_dev of parent = different filesystem)
    try:
        path_dev = os.stat(path).st_dev
        parent_dev = os.stat(os.path.dirname(path) or "/").st_dev
        if path_dev != parent_dev:
            # Different device — likely a mount point
            # Further refine: check /proc/mounts for CIFS/NFS on Linux
            if platform.system() == "Linux":
                return _linux_is_network_mount(path)
            # On macOS, assume network if device differs and path is under /Volumes
            if "/Volumes/" in path:
                return True
    except OSError:
        pass
    return False

def _linux_is_network_mount(path: str) -> bool:
    """Check /proc/mounts for cifs/nfs/smb filesystem types."""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2].lower() in ("cifs", "nfs", "nfs4", "smbfs"):
                    mount_point = parts[1]
                    if path.startswith(mount_point):
                        return True
    except OSError:
        pass
    return False
```

### Pattern 3: git_ops Helpers for Change Counting

**What:** New functions added to `app/services/git_ops.py` for phase 12 use.
**When to use:** Called by `_rescan` in WatcherManager.

```python
# Source: https://git-scm.com/docs/git-status (--porcelain format v1)
import subprocess
from pathlib import Path

WORKFLOW_SUFFIXES = {".yxmd", ".yxwz"}

def git_changed_workflows(folder: str) -> list[str]:
    """Return list of .yxmd/.yxwz files modified vs git HEAD (porcelain v1)."""
    result = subprocess.run(
        ["git", "-C", folder, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    changed = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        filename = line[3:].strip()
        if Path(filename).suffix in WORKFLOW_SUFFIXES:
            changed.append(filename)
    return changed

def count_workflows(folder: str) -> int:
    """Count all .yxmd/.yxwz files in folder (non-recursive)."""
    p = Path(folder)
    return sum(1 for f in p.iterdir()
               if f.is_file() and f.suffix in WORKFLOW_SUFFIXES)

def git_has_commits(folder: str) -> bool:
    """Return True if the repo has at least one commit."""
    result = subprocess.run(
        ["git", "-C", folder, "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    return result.returncode == 0
```

### Pattern 4: SSE Router Endpoint

**What:** FastAPI router using sse-starlette for push events.
**When to use:** Frontend subscribes on mount; fires on any badge update.

```python
# Source: https://github.com/sysid/sse-starlette
# sse-starlette 2.1.3 (already installed)
import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.services.watcher_manager import watcher_manager

router = APIRouter(prefix="/api/watch", tags=["watch"])

@router.get("/events")
async def watch_events():
    """SSE stream of badge_update events for all projects."""
    async def event_generator():
        q = watcher_manager.subscribe()
        try:
            while True:
                event = await q.get()
                yield {"data": json.dumps(event)}
        except asyncio.CancelledError:
            pass
        finally:
            watcher_manager.unsubscribe(q)
    return EventSourceResponse(event_generator())

@router.get("/status")
def watch_status() -> dict:
    """Return per-project change counts and commit status."""
    return watcher_manager.get_status()
```

### Pattern 5: FastAPI Lifespan for Watcher Startup

**What:** Start WatcherManager during FastAPI startup using async lifespan context manager.
**When to use:** Replace direct app.on_event with lifespan pattern (FastAPI 0.93+ recommended approach).

```python
# In app/server.py
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.services.watcher_manager import watcher_manager
from app.services import config_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: capture event loop, start watchers for all registered projects
    loop = asyncio.get_running_loop()
    watcher_manager.set_event_loop(loop)
    cfg = config_store.load_config()
    for proj in cfg.get("projects", []):
        watcher_manager.start_watching(proj["id"], proj["path"])
    yield
    # Shutdown: stop all observers
    for project_id in list(watcher_manager._observers.keys()):
        watcher_manager.stop_watching(project_id)

app = FastAPI(title="Alteryx Git Companion", lifespan=lifespan)
```

### Pattern 6: Frontend SSE Hook + Badge

**What:** React hook consuming SSE and updating Zustand store; badge rendered in Sidebar.
**When to use:** Called once in App.tsx or a top-level component on mount.

```typescript
// app/frontend/src/hooks/useWatchEvents.ts
import { useEffect } from 'react'
import { useProjectStore } from '@/store/useProjectStore'

export function useWatchEvents() {
  const setChangedCount = useProjectStore((s) => s.setChangedCount)

  useEffect(() => {
    const es = new EventSource('/api/watch/events')

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'badge_update') {
          setChangedCount(payload.project_id, payload.changed_count)
        }
      } catch { /* ignore malformed events */ }
    }

    es.onerror = () => {
      // EventSource auto-reconnects by default after error
      // No manual reconnect logic needed for same-host SSE
    }

    return () => es.close()
  }, [setChangedCount])
}
```

```typescript
// useProjectStore.ts additions
export interface Project {
  id: string
  path: string
  name: string
  changedCount?: number   // ADD THIS FIELD
}

// Add to ProjectStore interface:
setChangedCount: (id: string, count: number) => void

// Add to store implementation:
setChangedCount: (id, count) =>
  set((state) => ({
    projects: state.projects.map((p) =>
      p.id === id ? { ...p, changedCount: count } : p
    ),
  })),
```

```tsx
// Sidebar.tsx badge addition — inside the project button, after {project.name}
{project.changedCount != null && project.changedCount > 0 && (
  <span className="ml-auto text-xs font-semibold bg-amber-500 text-white
                   rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
    {project.changedCount}
  </span>
)}
```

### Pattern 7: Dynamic Watcher Registration in projects.py

**What:** Notify WatcherManager whenever a project is added or removed via the API.
**When to use:** In `add_project` and `remove_project` router handlers.

```python
# In app/routers/projects.py — add after save_config:
from app.services.watcher_manager import watcher_manager

# In add_project, after config_store.save_config(cfg):
watcher_manager.start_watching(project["id"], path_str)

# In remove_project, before return:
watcher_manager.stop_watching(project_id)
```

### Anti-Patterns to Avoid

- **Calling `queue.put_nowait()` directly from watchdog's observer thread:** asyncio.Queue is not thread-safe. Always use `loop.call_soon_threadsafe(queue.put_nowait, event)`.
- **Using `observer.join()` without a timeout:** If the watched path is on a disconnected network share, `observer.join()` can block indefinitely. Always use `observer.join(timeout=2)`.
- **Scheduling `recursive=True` on the watchdog observer for a project folder:** Alteryx project folders contain only flat `.yxmd`/`.yxwz` files. Recursive watching adds CPU overhead scanning subdirectories.
- **Using `git diff --name-only HEAD` instead of `git status --porcelain`:** `git diff` only captures tracked modified files. `git status --porcelain` also catches untracked new files that haven't been committed yet.
- **Using `watchdog.observers.Observer` for UNC paths:** The auto-selected native observer (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows) does not work reliably over CIFS/SMB. `PollingObserver` must be selected explicitly for network paths.
- **Re-instantiating a new Observer on every file event:** Observer instances are expensive. Instantiate once per project; let the handler drive rescan logic.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS filesystem events | Custom inotify/kqueue wrapper | `watchdog.observers.Observer` | Handles 5 platforms, observer thread lifecycle, error recovery |
| SSE framing and keep-alive | Manual `data:...\n\n` StreamingResponse | `sse_starlette.EventSourceResponse` | Handles SSE framing, retry headers, keep-alive pings, client disconnect |
| Network drive detection on Windows | Win32 registry parsing | `ctypes.windll.kernel32.GetDriveTypeW` | Authoritative Windows API; no dependencies |
| Debounce logic | asyncio.sleep-based debounce | `threading.Timer` reset pattern | Watchdog callbacks are in thread context; threading.Timer is the idiomatic debounce in that context |
| Change detection logic | File modification timestamps | `git status --porcelain` | Timestamps are unreliable (network clock skew, Alteryx temp-file pattern); git HEAD comparison is authoritative |

**Key insight:** The thread-boundary problem (watchdog observer thread → asyncio event loop) is the central architectural challenge. The `loop.call_soon_threadsafe` pattern is well-established and must be used correctly — any other approach risks race conditions or deadlocks.

---

## Common Pitfalls

### Pitfall 1: fastapi.sse Does Not Exist in FastAPI 0.115.x

**What goes wrong:** Official FastAPI docs now show `from fastapi.sse import EventSourceResponse`, but this module only exists in FastAPI >= 0.116 (not yet released as of the project's installed version 0.115.12).
**Why it happens:** FastAPI docs are ahead of the released package.
**How to avoid:** Use `from sse_starlette.sse import EventSourceResponse` — this is the correct import for FastAPI 0.115.x, and sse-starlette 2.1.3 is already installed.
**Warning signs:** `ModuleNotFoundError: No module named 'fastapi.sse'` on import.

### Pitfall 2: asyncio.Queue Put From Non-Loop Thread

**What goes wrong:** `q.put_nowait(event)` called directly from watchdog's observer thread silently corrupts the queue's internal state or causes sporadic `RuntimeError: Event loop is closed`.
**Why it happens:** asyncio primitives are not thread-safe.
**How to avoid:** Always use `loop.call_soon_threadsafe(q.put_nowait, event)`. Capture the loop once at FastAPI startup via `asyncio.get_running_loop()` and store it in WatcherManager.
**Warning signs:** Intermittent failures only visible under concurrent file changes; normal test cases pass.

### Pitfall 3: Watchdog Observer Startup Race on Startup

**What goes wrong:** WatcherManager starts observers before FastAPI's event loop is captured, so `self._loop` is None when the first filesystem event fires.
**Why it happens:** Startup order matters — observers can fire events before `lifespan` completes.
**How to avoid:** Call `watcher_manager.set_event_loop(loop)` as the FIRST thing in the `lifespan` startup block, before calling `start_watching`.
**Warning signs:** First few badge updates after startup are silently dropped.

### Pitfall 4: Alteryx Double-Write Debounce

**What goes wrong:** Alteryx Designer writes `.yxmd` files in multiple bursts (saves a temp file, renames it). Without debounce, `git status` gets called 3–6 times per logical save, flooding SSE subscribers and causing badge flicker.
**Why it happens:** OS-level file rename triggers `on_created` + `on_modified` events in rapid succession.
**How to avoid:** Per-project `threading.Timer` with 1.5 seconds — each new event resets the timer. Run `git status` only once when the timer fires.
**Warning signs:** SSE stream shows 4–6 `badge_update` events within 200ms of a single Alteryx save.

### Pitfall 5: Observer.stop() Blocks on Dead Network Share

**What goes wrong:** Calling `observer.stop()` and then `observer.join()` (no timeout) hangs indefinitely if the network share is unreachable.
**Why it happens:** watchdog PollingObserver's internal thread is blocked on a filesystem stat call.
**How to avoid:** Always use `observer.join(timeout=2)`. Log a warning if join times out but proceed with cleanup.
**Warning signs:** App shutdown hangs; CTRL-C has no effect.

### Pitfall 6: git_has_commits False Positive on New Repos

**What goes wrong:** `git rev-parse HEAD` exits with code 0 on a repo that was `git init`-ed but never committed, returning the string "HEAD". This is wrong — HEAD does not exist until after the first commit.
**Why it happens:** `git rev-parse HEAD` returns exit code 128 on a repo with no commits — which subprocess interprets as a non-zero exit, so `returncode != 0` correctly signals no commits. This is actually safe as long as you check `returncode == 0`.
**How to avoid:** The pattern `git_has_commits` returning `result.returncode == 0` is correct. Document this clearly.
**Warning signs:** If someone changes to `"HEAD" in result.stdout`, it would break.

---

## Code Examples

### git status --porcelain Output Format

```
# Source: https://git-scm.com/docs/git-status#_output (porcelain v1)
# XY PATH  or  XY ORIG_PATH -> PATH  (rename)
# X = staged status, Y = unstaged status
# Common codes: M=modified, A=added, D=deleted, ??=untracked
 M workflow.yxmd          # unstaged modification
M  analysis.yxmd          # staged modification
?? new_workflow.yxmd      # untracked new file
 D old_report.yxwz        # deleted (unstaged)
```

Parsing rule: `line[3:]` gives the filename (strip leading spaces); check `Path(filename).suffix in {".yxmd", ".yxwz"}`.

### SSE Wire Format

```
# Source: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
# Each event ends with double newline
data: {"type": "badge_update", "project_id": "abc-123", "changed_count": 3}\n\n
```

sse-starlette handles this format automatically when you `yield {"data": json.dumps(payload)}`.

### watchdog PatternMatchingEventHandler Pattern

```python
# Source: https://python-watchdog.readthedocs.io/en/stable/api.html
from watchdog.events import PatternMatchingEventHandler

class _WorkflowEventHandler(PatternMatchingEventHandler):
    def __init__(self, project_id: str, path: str, on_change) -> None:
        super().__init__(
            patterns=["*.yxmd", "*.yxwz"],
            ignore_patterns=["*.tmp", "~*"],
            ignore_directories=True,
            case_sensitive=False,
        )
        self._project_id = project_id
        self._path = path
        self._on_change = on_change

    def on_any_event(self, event):
        self._on_change(self._project_id, self._path)
```

Using `on_any_event` (rather than `on_modified` only) ensures that file renames, creations, and deletions all trigger a rescan — important because Alteryx save involves a rename.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `app.on_event("startup")` decorator | `@asynccontextmanager async def lifespan(app)` | FastAPI 0.93 (2023) | `on_event` is deprecated; lifespan is the correct startup/shutdown hook |
| `from sse_starlette.sse import EventSourceResponse` | `from fastapi.sse import EventSourceResponse` | FastAPI 0.116+ (not released yet as of 0.115.12) | Use sse-starlette import for now; will change when FastAPI 0.116 is released |
| PollingObserver polling_interval kwarg | PollingObserver timeout kwarg | watchdog 2.x+ | The constructor parameter is `timeout`, not `polling_interval`; `PollingObserver(timeout=5)` |

**Deprecated/outdated:**
- `watchdog.observers.polling.PollingObserverVFS`: Lower-level VFS variant not needed here — standard `PollingObserver(timeout=5)` is correct.
- `app.on_event("startup"/"shutdown")`: Replaced by lifespan context manager in all FastAPI documentation.
- `fastapi.sse` module: Does not exist in FastAPI 0.115.x; use sse-starlette.

---

## Open Questions

1. **WatcherManager unsubscribe with list vs set**
   - What we know: `_subscribers` is a list; removal uses `remove()`.
   - What's unclear: Under concurrent SSE connections, list mutation during iteration could be a problem.
   - Recommendation: Use `list(self._subscribers)` when iterating to push events (already shown in pattern above). For add/remove, a simple list with a lock is sufficient for this single-user desktop use case. A `threading.Lock` around mutations is the safest approach.

2. **macOS network mount detection accuracy**
   - What we know: UNC detection covers `//server/share` format. `/Volumes/` + `st_dev` check covers most macOS SMB mounts.
   - What's unclear: Some macOS autofs mounts may not be under `/Volumes`. Corporate macOS setups can map SMB shares to arbitrary paths.
   - Recommendation: Default to native observer and handle the `start()` → `OSError` fallback. If the native observer fails to start (OSError), retry with PollingObserver. This is more resilient than trying to perfectly classify every path type.

3. **Badge clear after save (Phase 13 integration)**
   - What we know: CONTEXT.md says badge clears after user saves a version, wired in Phase 13.
   - What's unclear: Whether Phase 13 calls `watcher_manager._change_counts[pid] = 0` directly or relies on watcher auto-rescan post-commit.
   - Recommendation: Expose a `watcher_manager.clear_count(project_id)` method that zeroes the count and pushes a `badge_update` SSE event. Phase 13 calls this after a successful commit. Keeps Phase 12 and 13 cleanly separated.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_watch.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WATCH-01 | `git_changed_workflows()` returns only `.yxmd`/`.yxwz` files modified vs HEAD | unit | `pytest tests/test_watch.py::test_git_changed_workflows -x` | ❌ Wave 0 |
| WATCH-01 | `count_workflows()` counts only `.yxmd`/`.yxwz` files | unit | `pytest tests/test_watch.py::test_count_workflows -x` | ❌ Wave 0 |
| WATCH-01 | `GET /api/watch/events` returns 200 with text/event-stream content-type | integration | `pytest tests/test_watch.py::test_sse_endpoint_headers -x` | ❌ Wave 0 |
| WATCH-01 | WatcherManager pushes badge_update to subscribers when rescan fires | unit | `pytest tests/test_watch.py::test_badge_push_on_rescan -x` | ❌ Wave 0 |
| WATCH-02 | `is_network_path()` returns True for UNC paths `\\server\share` | unit | `pytest tests/test_watch.py::test_is_network_path_unc -x` | ❌ Wave 0 |
| WATCH-02 | `is_network_path()` returns False for local absolute paths | unit | `pytest tests/test_watch.py::test_is_network_path_local -x` | ❌ Wave 0 |
| WATCH-02 | WatcherManager uses PollingObserver for network paths | unit (mock) | `pytest tests/test_watch.py::test_polling_observer_for_network -x` | ❌ Wave 0 |
| WATCH-03 | `GET /api/watch/status` returns `has_any_commits: false` for new repo | integration | `pytest tests/test_watch.py::test_watch_status_no_commits -x` | ❌ Wave 0 |
| WATCH-03 | `GET /api/watch/status` returns correct `total_workflows` count | integration | `pytest tests/test_watch.py::test_watch_status_total_workflows -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_watch.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_watch.py` — covers all WATCH-01, WATCH-02, WATCH-03 requirements
- [ ] `tests/test_git_ops_watch.py` — or extend `tests/test_projects.py` with new git_ops helpers (`git_changed_workflows`, `count_workflows`, `git_has_commits`)

*(No new framework install needed — pytest already configured)*

---

## Sources

### Primary (HIGH confidence)

- watchdog 6.0.0 (installed, pip show verified) — Observer classes, PollingObserver timeout param, PatternMatchingEventHandler
- [watchdog API Reference](https://python-watchdog.readthedocs.io/en/stable/api.html) — Observer.schedule(), start(), stop(), unschedule() APIs
- [Microsoft GetDriveTypeA docs](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypea) — DRIVE_REMOTE=4 constant, root path format with trailing backslash
- [Python asyncio docs — thread safety](https://docs.python.org/3/library/asyncio-dev.html) — `loop.call_soon_threadsafe()` for cross-thread queue operations
- [git-status --porcelain format](https://git-scm.com/docs/git-status) — Output format v1, XY codes
- sse-starlette 2.1.3 (installed, import verified) — `EventSourceResponse`, async generator pattern
- fastapi 0.115.12 (installed, confirmed `fastapi.sse` does NOT exist) — confirmed sse-starlette is the correct approach

### Secondary (MEDIUM confidence)

- [watchdog GitHub Issue #409](https://github.com/gorakhargosh/watchdog/issues/409) — Confirmed: use PollingObserver for SMB/CIFS, native observer fails on network filesystems
- [asyncio watchdog bridge gist](https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6) — `loop.call_soon_threadsafe(queue.put_nowait, event)` pattern
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) — Lifespan context manager replacing `on_event` decorator

### Tertiary (LOW confidence)

- macOS network mount detection via `/Volumes/` + `st_dev` — derived from Python os.path.ismount() behavior; not verified against all macOS SMB mount configurations

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both watchdog and sse-starlette installed and import-verified; FastAPI version confirmed
- Architecture: HIGH — watchdog API confirmed against official docs; asyncio thread-safety pattern confirmed against CPython docs; SSE pattern confirmed with installed library
- Pitfalls: HIGH — `fastapi.sse` import failure reproduced locally; thread-safety concern confirmed in asyncio docs; watchdog SMB limitation confirmed in official issue tracker
- Network path detection (macOS/Linux): MEDIUM — Windows GetDriveType is authoritative; macOS /Volumes heuristic is reasonable but not exhaustive

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (watchdog and FastAPI are stable; sse-starlette unlikely to change breaking APIs)
