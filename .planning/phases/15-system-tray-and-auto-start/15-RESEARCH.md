# Phase 15: System Tray and Auto-start - Research

**Researched:** 2026-03-14
**Domain:** Python system tray (pystray), Windows Registry (winreg), PyInstaller silent-mode, React Settings UI (shadcn Switch)
**Confidence:** HIGH

## Summary

Phase 15 converts the Alteryx Git Companion from a console app into a proper background service: it registers itself to start on Windows boot, runs without a visible console window, and exposes its current state (idle / watching / changes detected) through a system tray icon. The scope is narrow and the tech stack is well-understood — pystray for the tray icon, winreg (stdlib) for the Registry Run key, shadcn Switch for the Settings panel toggle.

The two critical threading decisions drive the entire backend architecture. On Windows, `pystray.Icon.run()` is safe to call from a non-main thread, so uvicorn keeps its existing `asyncio.run(server.serve(...))` in the main thread and pystray runs in a daemon thread. This is the opposite of the macOS-required pattern (where pystray must run on the main thread) and is the correct approach for this Windows-only app. Second, `GET /api/watch/status` already returns all the data the tray icon needs (changed_count per project); no new backend plumbing is required for the polling loop.

The frontend change is modest: a gear icon at the bottom of the sidebar opens a Settings view in `AppShell.renderMainContent()`, containing a single Switch component backed by `GET/POST /api/settings`. The router reads/writes the HKCU Run key via winreg.

**Primary recommendation:** Run uvicorn in the main thread (current) and pystray in a daemon thread. Poll `GET /api/watch/status` every 5 seconds from inside the tray thread. Use winreg context manager pattern for all registry operations. Install pystray + Pillow.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Auto-start mechanism**
- Windows Registry Run key: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- No admin rights required — user-space registration
- Display name: `Alteryx Git Companion`
- Registration happens on first app launch automatically (no separate installer step needed)
- If registration fails (registry write error): silent fail + log warning — auto-start is a convenience, not a blocker

**Silent startup behavior**
- Registry Run key entry includes `--background` flag in the command
- Manual `.exe` double-click has no `--background` flag — app checks `sys.argv` to decide whether to open browser
- `--background` mode: no browser open, no console window, just the server + tray icon
- Manual launch mode: browser opens (existing Phase 10 behavior preserved)
- `console=False` in PyInstaller spec — flip from Phase 10's `console=True` debug setting
- Second-instance handling: detect existing running instance via port probe/lockfile → open browser to running instance → exit. Feels like Slack — clicking again focuses the app.

**Tray icon UX**
- Left-click: opens browser UI at `localhost:PORT` (satisfies APP-04b)
- Right-click: context menu with two entries — "Open Alteryx Git Companion" + "Quit"
- Three icon states, shown via distinct icon files (not overlay badges):
  - **Idle** — default icon (no active projects watching)
  - **Watching** — active/distinct icon variant (watcher running, no changes)
  - **Changes detected** — amber/highlighted icon variant (changedCount > 0 for any project)
- Tooltip text updates with state (e.g. "Alteryx Git Companion — 2 changes detected")
- Tray state sync: system tray polls `GET /api/watch/status` every few seconds — consistent with SSE pattern from Phase 12, no new plumbing

**Auto-start toggle (Settings panel)**
- Settings gear icon at the bottom of the left sidebar (below project list) — VS Code / Slack pattern
- Clicking gear opens a Settings panel in the main content area
- Phase 15 scope: single toggle only — "Launch on startup" (on/off)
- Toggle reads and writes the Registry Run key — on = key present, off = key absent
- No other settings in Phase 15; more settings added in future phases as needed

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| APP-02 | App starts automatically when Windows boots, running silently in the background | winreg HKCU Run key write on first launch; `--background` argv flag suppresses browser open and keeps console=False; second-instance detection exits cleanly |
| APP-04b | User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT) | pystray MenuItem with `default=True` fires `webbrowser.open(f"http://localhost:{port}")` on left-click |
| APP-05 | System tray icon shows app status (watching / changes detected / idle) | pystray `icon.icon` property swap between three PIL Image objects; daemon thread polls `/api/watch/status` every 5s to compute state |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pystray | 0.19.5 | System tray icon — Windows native backend, full feature set | Only maintained cross-platform Python tray library; Windows backend uses Win32 natively |
| Pillow (PIL) | existing (bundled with app) | Load PNG/ICO files as `Image` objects for pystray | pystray requires PIL Image; already a transitive dependency via acd CLI |
| winreg | stdlib | Read/write HKCU Registry Run key | Built-in on Windows, no install needed; zero extra bundle size |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @radix-ui/react-switch | bundled via shadcn | Accessible toggle Switch component | Settings panel "Launch on startup" toggle |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pystray | infi.systray | infi.systray is Windows-only and unmaintained since 2020; pystray is actively maintained and cross-platform |
| pystray | wx.TaskBarIcon | wxPython adds 30MB+ to bundle; pystray adds ~200KB |
| polling /api/watch/status | SSE subscription from tray thread | SSE from a non-async daemon thread requires a persistent aiohttp/httpx session; polling is simpler and 5-second latency is acceptable for a tray icon |
| winreg direct | config_store.py | Registry is the standard Windows auto-start mechanism; config_store.py is for app data, not OS integration |

**Installation:**
```bash
# Python backend
pip install pystray

# Frontend (shadcn Switch — follow established project pattern)
npx shadcn@latest add switch
# Move component from @/components/ui/ to src/components/ui/ per vite alias (Phase 11/13 precedent)
```

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── main.py                  # MODIFIED: --background flag, second-instance check, pystray thread start
├── tray.py                  # NEW: TrayIcon class — daemon thread, state polling, icon swap
├── routers/
│   └── settings.py          # NEW: GET/POST /api/settings (auto-start read/write)
├── services/
│   └── autostart.py         # NEW: register_autostart(), unregister_autostart(), is_autostart_enabled()
assets/
├── icon.ico                 # EXISTING — used as idle state icon
├── icon-watching.ico        # NEW — distinct color/variant for watching state
├── icon-changes.ico         # NEW — amber/highlighted for changes-detected state
app/frontend/src/
├── components/
│   ├── Sidebar.tsx          # MODIFIED: gear icon at bottom
│   ├── AppShell.tsx         # MODIFIED: Settings branch in renderMainContent()
│   └── SettingsPanel.tsx    # NEW: single Switch + label
```

### Pattern 1: Threading Architecture (Windows-specific)

**What:** Uvicorn holds the main thread (via `asyncio.run`); pystray runs in a daemon thread. This is the correct Windows architecture because `pystray.Icon.run()` is safe to call from non-main threads on Windows (unlike macOS where it must be main thread).

**When to use:** Always — this is the only viable pattern for combining asyncio uvicorn with pystray on Windows without restructuring `main.py`.

**Example:**
```python
# Source: pystray docs — "If you only target Windows, calling run() from a thread
# other than the main thread is safe."
# https://pystray.readthedocs.io/en/latest/usage.html

import threading
import pystray

def start_tray(port: int) -> None:
    """Run in daemon thread. Safe on Windows (non-main-thread ok)."""
    icon = build_tray_icon(port)
    icon.run()  # blocking; exits when icon.stop() is called

tray_thread = threading.Thread(target=start_tray, args=(port,), daemon=True)
tray_thread.start()

# Main thread keeps running uvicorn
asyncio.run(server.serve(sockets=[sock]))
```

### Pattern 2: pystray Icon Construction

**What:** Create Icon with name, initial PIL Image, title (tooltip), and Menu. Swap `icon.icon` property to change state. Update `icon.title` for tooltip text.

**When to use:** Every tray state transition.

**Example:**
```python
# Source: pystray 0.19.5 reference
# https://pystray.readthedocs.io/en/latest/reference.html

import pystray
from PIL import Image

def build_tray_icon(port: int) -> pystray.Icon:
    idle_image = Image.open("assets/icon.ico")

    def on_open(icon, item):
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")

    def on_quit(icon, item):
        icon.stop()
        # uvicorn will exit when the daemon thread ends and main thread exits

    menu = pystray.Menu(
        pystray.MenuItem("Open Alteryx Git Companion", on_open, default=True),
        pystray.MenuItem("Quit", on_quit),
    )

    return pystray.Icon(
        name="AlterxyGitCompanion",
        icon=idle_image,
        title="Alteryx Git Companion",
        menu=menu,
    )

# State update (called from polling loop inside tray thread):
def update_icon_state(icon: pystray.Icon, state: str, tooltip: str) -> None:
    icon.icon = IMAGE_MAP[state]   # swap PIL Image
    icon.title = tooltip           # update tooltip
```

### Pattern 3: Tray State Polling Loop

**What:** A simple polling loop inside `TrayIcon.run()` uses `requests.get` (synchronous, no asyncio) to call `GET /api/watch/status` every 5 seconds, computes the aggregate state, and swaps the icon.

**When to use:** Inside the daemon thread that runs pystray.

**Example:**
```python
import time
import requests

POLL_INTERVAL = 5  # seconds

def _poll_loop(icon: pystray.Icon, port: int) -> None:
    """Runs in pystray setup callback (separate thread from icon.run)."""
    while icon.visible:
        try:
            resp = requests.get(
                f"http://localhost:{port}/api/watch/status", timeout=3
            )
            if resp.ok:
                all_status = resp.json()
                # Aggregate: any project has changes? → changes-detected
                total_changes = sum(
                    v.get("changed_count", 0) for v in all_status.values()
                )
                any_watching = bool(all_status)
                if total_changes > 0:
                    state = "changes"
                    tooltip = f"Alteryx Git Companion — {total_changes} change{'s' if total_changes != 1 else ''} detected"
                elif any_watching:
                    state = "watching"
                    tooltip = "Alteryx Git Companion — watching"
                else:
                    state = "idle"
                    tooltip = "Alteryx Git Companion"
                update_icon_state(icon, state, tooltip)
        except Exception:
            pass  # server not up yet on first poll; ignore
        time.sleep(POLL_INTERVAL)
```

### Pattern 4: winreg Auto-start Registration

**What:** Use stdlib `winreg` with context manager to write/read/delete the HKCU Run key entry. Conditional import guards cross-platform safety for tests.

**When to use:** `autostart.py` service module — called on first launch and from `POST /api/settings`.

**Example:**
```python
# Source: https://docs.python.org/3/library/winreg.html

from __future__ import annotations
import sys
import logging

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "Alteryx Git Companion"

logger = logging.getLogger(__name__)


def _get_exe_path() -> str:
    """Return the path to register — exe path + ' --background' flag."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
    else:
        # dev mode: use python interpreter + module path (tests only)
        exe = f'"{sys.executable}" -m app.main'
    return f'"{exe}" --background'


def register_autostart() -> bool:
    """Write HKCU Run key. Returns True on success, False on failure (silent)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        return True
    except OSError:
        logger.warning("Failed to register auto-start in Windows Registry")
        return False


def unregister_autostart() -> bool:
    """Delete HKCU Run key entry. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY,
            access=winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return True  # already absent — success
    except OSError:
        logger.warning("Failed to unregister auto-start from Windows Registry")
        return False


def is_autostart_enabled() -> bool:
    """Check if Run key entry exists for this app."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
```

### Pattern 5: Second-Instance Detection via Port Probe

**What:** `find_available_port()` in `main.py` already tries to bind port 7433. If binding fails, the port is in use — another instance is running. Open the browser to the running instance and exit immediately.

**When to use:** At the start of `main()`, before the uvicorn server starts.

**Example:**
```python
import socket
import sys
import webbrowser

PRIMARY_PORT = 7433

def is_instance_running() -> bool:
    """Return True if port 7433 is already bound (another instance running)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PRIMARY_PORT))
        sock.close()
        return False  # port was free — no other instance
    except OSError:
        sock.close()
        return True  # port in use — instance already running

def main() -> None:
    if is_instance_running():
        webbrowser.open(f"http://localhost:{PRIMARY_PORT}")
        sys.exit(0)
    # ... rest of startup
```

### Pattern 6: `--background` Flag Handling in main()

**What:** Check `sys.argv` for `--background` before the existing `webbrowser.open` call. `--background` suppresses browser open; without it, existing Phase 10 behavior is preserved.

**When to use:** In `main()`, top of function.

**Example:**
```python
def main() -> None:
    background_mode = "--background" in sys.argv

    # Second-instance check — always first
    if is_instance_running():
        if not background_mode:
            webbrowser.open(f"http://localhost:{PRIMARY_PORT}")
        sys.exit(0)

    port, sock = find_available_port()

    if not background_mode:
        # Existing Phase 10 behavior — open browser on manual launch
        timer = threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}"))
        timer.daemon = True
        timer.start()

    # Register auto-start on first launch (silent fail)
    _maybe_register_autostart()

    # Start tray in daemon thread
    tray_thread = threading.Thread(target=start_tray, args=(port,), daemon=True)
    tray_thread.start()

    # Main thread runs uvicorn (existing)
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    asyncio.run(server.serve(sockets=[sock]))
```

### Anti-Patterns to Avoid

- **Running pystray on the main thread (wrong pattern for Windows):** On macOS this is required, but on Windows it blocks the uvicorn asyncio event loop. Since this is Windows-only, keep pystray in the daemon thread.
- **SSE subscription from the tray daemon thread:** Async SSE requires an async event loop; the tray thread has none. Use synchronous `requests.get` polling instead.
- **Importing winreg at module level without a platform guard:** winreg does not exist on macOS/Linux. Always import inside `if sys.platform == "win32":` or inside the function body — allows tests to run on macOS CI.
- **Not setting `daemon=True` on the tray thread:** If the thread is non-daemon, the process will hang on quit when `icon.stop()` has not been called.
- **Calling `asyncio.run()` from the tray thread:** The tray daemon thread must remain synchronous; `requests` (sync HTTP) is the correct choice for polling.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System tray icon rendering on Windows | Custom Win32 NOTIFYICONDATA wrapper | pystray 0.19.5 | Win32 tray icon API is complex; pystray handles WM_TRAYICON messages, menu pump, icon invalidation |
| Image manipulation for icons | Custom ICO/PNG loader | Pillow (PIL) `Image.open()` | Already bundled; pystray requires PIL Image; ICO format handling is non-trivial |
| Auto-start detection | File sentinel / pid file | winreg `QueryValueEx` | Registry Run key IS the OS auto-start mechanism; a file sentinel is redundant and error-prone after crashes |
| Single-instance guard | Named mutex / pid file | Port probe (bind to 7433) | Port probe reuses existing `find_available_port()` logic; named mutexes require win32api which is not bundled |

**Key insight:** The only custom logic in this phase is the 5-second polling loop and the `--background` argv check — everything else delegates to well-maintained libraries.

---

## Common Pitfalls

### Pitfall 1: winreg import on non-Windows
**What goes wrong:** `import winreg` raises `ModuleNotFoundError` on macOS/Linux CI.
**Why it happens:** winreg is a Windows-only stdlib module. CI typically runs on Linux/macOS.
**How to avoid:** Defer the import inside the function body behind `if sys.platform != "win32": return False`. Use `unittest.mock.patch` in tests to substitute a mock.
**Warning signs:** Tests fail on CI with `ModuleNotFoundError: No module named 'winreg'`.

### Pitfall 2: pystray icon not appearing (PyInstaller bundle)
**What goes wrong:** Tray icon is invisible in the bundled .exe; no error is raised.
**Why it happens:** pystray on Windows uses the Win32 backend which requires Pillow. If PIL Image load fails (asset path wrong inside bundle), the icon is silently None.
**How to avoid:** Load icon PNGs via `_get_asset_path()` using `sys._MEIPASS` for frozen bundles (same pattern as `_static_dir()` in server.py). Add all three icon files to `datas` in app.spec.
**Warning signs:** Icon never appears in tray when running the .exe; works fine in `python -m app.main`.

### Pitfall 3: console window flashes briefly on boot (console=False not set)
**What goes wrong:** A black console window appears for ~1 second on Windows boot then disappears.
**Why it happens:** app.spec still has `console=True` from Phase 10 debug setting.
**How to avoid:** Flip `console=True` to `console=False` in app.spec as part of Plan 1.
**Warning signs:** Console window visible on startup even in --background mode.

### Pitfall 4: Second-instance check uses wrong port after fallback
**What goes wrong:** If another app has bound 7433, the Companion starts on 7434. A second Companion instance then also starts on 7435. Both run simultaneously.
**Why it happens:** The "port in use" check only tests 7433, but another Companion may have started on 7434+.
**How to avoid:** For the second-instance probe, only check the primary port (7433). If 7433 is not bound, it is not a Companion instance — start normally. The port fallback (7434–7443) exists for edge cases, not for distinguishing instances.
**Warning signs:** Multiple system tray icons visible for the same app.

### Pitfall 5: Quit from tray hangs the process
**What goes wrong:** Clicking "Quit" in the tray menu calls `icon.stop()` but the process does not exit because uvicorn's asyncio loop is still running.
**Why it happens:** `icon.stop()` halts the pystray event loop but does not signal uvicorn to shut down.
**How to avoid:** After `icon.stop()`, call `uvicorn_server.should_exit = True` (the UvicornServer instance is accessible from the tray thread via closure or module-level ref). Uvicorn checks this flag in its event loop and exits gracefully.
**Warning signs:** Process remains in Task Manager after clicking Quit; tray icon disappears but port stays bound.

### Pitfall 6: pystray menu item `default=True` (left-click) not firing on Windows
**What goes wrong:** Left-clicking the tray icon does nothing; only right-click context menu works.
**Why it happens:** On Windows, left-click activates the *default* menu item (the one with `default=True` in MenuItem). If no item has `default=True`, left-click does nothing.
**How to avoid:** Set `default=True` on the "Open Alteryx Git Companion" MenuItem.
**Warning signs:** Left-click is a no-op; right-click works fine.

---

## Code Examples

Verified patterns from official sources:

### pystray Icon with Menu and Left-Click Default
```python
# Source: https://pystray.readthedocs.io/en/latest/reference.html
import pystray
from PIL import Image

icon = pystray.Icon(
    name="AlterxyGitCompanion",
    icon=Image.open("assets/icon.ico"),
    title="Alteryx Git Companion",
    menu=pystray.Menu(
        pystray.MenuItem("Open Alteryx Git Companion", on_open, default=True),
        pystray.MenuItem("Quit", on_quit),
    ),
)
icon.run()  # blocking — safe in non-main thread on Windows
```

### winreg Context Manager Pattern (verified)
```python
# Source: https://docs.python.org/3/library/winreg.html
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Write
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
    winreg.SetValueEx(key, "Alteryx Git Companion", 0, winreg.REG_SZ, exe_path)

# Read/check presence
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.QueryValueEx(key, "Alteryx Git Companion")
    enabled = True
except FileNotFoundError:
    enabled = False

# Delete
with winreg.OpenKey(
    winreg.HKEY_CURRENT_USER, RUN_KEY, access=winreg.KEY_SET_VALUE
) as key:
    winreg.DeleteValue(key, "Alteryx Git Companion")
```

### shadcn Switch in Settings Panel
```tsx
// Source: https://ui.shadcn.com/docs/components/radix/switch
// Install: npx shadcn@latest add switch
// Move from @/components/ui/switch.tsx to src/components/ui/switch.tsx (Phase 11/13 pattern)

import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

export function SettingsPanel() {
  const [launchOnStartup, setLaunchOnStartup] = useState(false)

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(d => setLaunchOnStartup(d.launch_on_startup))
  }, [])

  async function handleToggle(checked: boolean) {
    setLaunchOnStartup(checked)  // optimistic update
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ launch_on_startup: checked }),
    })
  }

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-lg font-semibold">Settings</h2>
      <div className="flex items-center space-x-2">
        <Switch id="launch-on-startup" checked={launchOnStartup} onCheckedChange={handleToggle} />
        <Label htmlFor="launch-on-startup">Launch on startup</Label>
      </div>
    </div>
  )
}
```

### Gear Icon in Sidebar (lucide-react)
```tsx
// lucide-react is already installed (used in Sidebar.tsx for Plus icon)
import { Settings } from 'lucide-react'

// Add at the bottom of Sidebar's flex column:
<div className="mt-auto pt-2 border-t">
  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onOpenSettings}>
    <Settings className="h-4 w-4" />
    <span className="sr-only">Settings</span>
  </Button>
</div>
```

### FastAPI Settings Router
```python
# Pattern: module-level import for mock.patch compatibility (Phase 11-14 convention)
from app.services import autostart  # noqa: F401

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
def get_settings() -> dict:
    return {"launch_on_startup": autostart.is_autostart_enabled()}

@router.post("")
def post_settings(body: SettingsBody) -> dict:
    if body.launch_on_startup:
        autostart.register_autostart()
    else:
        autostart.unregister_autostart()
    return {"launch_on_startup": autostart.is_autostart_enabled()}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| console=True (Phase 10) | console=False | Phase 15 | No console window in production; flip was explicitly planned in Phase 10 notes |
| Browser opens on every launch | --background suppresses browser open | Phase 15 | Enables boot-time silent start without disrupting user |
| No tray icon | pystray daemon thread | Phase 15 | App state visible in taskbar area at all times |

**Deprecated/outdated:**
- infi.systray: unmaintained since 2020, Windows-only, no PyPI updates
- Phase 10 `console=True`: intentional debug setting, replaced in Phase 15

---

## Open Questions

1. **Auto-first-launch registration timing**
   - What we know: CONTEXT.md says "registration happens on first app launch automatically"
   - What's unclear: Should registration happen before uvicorn starts (risky: port not yet bound) or after the server is up (inside lifespan startup)?
   - Recommendation: Register in `main()` after `find_available_port()` succeeds, before starting uvicorn — keeps `autostart.py` independent of the server lifecycle. Silent fail if registry write fails.

2. **Three icon asset files — production quality**
   - What we know: `assets/icon.ico` exists (Phase 10); `icon-watching.ico` and `icon-changes.ico` are needed
   - What's unclear: Should Phase 15 generate placeholder colored squares programmatically (using Pillow's ImageDraw) or require hand-crafted ICO files?
   - Recommendation: Generate programmatically in `tray.py` as a fallback if files are missing — keeps CI from failing if assets aren't checked in; replace with real icons before release.

3. **Quit behavior and uvicorn shutdown signal**
   - What we know: `icon.stop()` halts the pystray loop; uvicorn needs `server.should_exit = True`
   - What's unclear: The `uvicorn.Server` instance is created inside `main()`; the tray thread needs a reference to it
   - Recommendation: Store `server` in a module-level variable or pass it to `TrayIcon.__init__` so the Quit handler can set `server.should_exit = True` cleanly.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, 156 tests passing) |
| Config file | pytest.ini (pythonpath=['.']) |
| Quick run command | `python -m pytest tests/test_settings.py tests/test_autostart.py -x -q` |
| Full suite command | `python -m pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-02 | `register_autostart()` writes HKCU Run key with `--background` flag | unit (mock winreg) | `pytest tests/test_autostart.py::test_register_writes_run_key -x` | ❌ Wave 0 |
| APP-02 | `is_autostart_enabled()` returns False when key absent | unit (mock winreg) | `pytest tests/test_autostart.py::test_is_enabled_false -x` | ❌ Wave 0 |
| APP-02 | `unregister_autostart()` deletes Run key | unit (mock winreg) | `pytest tests/test_autostart.py::test_unregister_removes_key -x` | ❌ Wave 0 |
| APP-02 | `--background` flag in sys.argv suppresses webbrowser.open | unit (mock webbrowser) | `pytest tests/test_main.py::test_background_flag_suppresses_browser -x` | ❌ Wave 0 |
| APP-02 | Second-instance detection: port bound → returns True | unit | `pytest tests/test_main.py::test_is_instance_running_true -x` | ❌ Wave 0 |
| APP-04b | `GET /api/settings` returns `{"launch_on_startup": bool}` | unit (mock autostart) | `pytest tests/test_settings.py::test_get_settings -x` | ❌ Wave 0 |
| APP-04b | `POST /api/settings` with `launch_on_startup: true` calls `register_autostart()` | unit (mock autostart) | `pytest tests/test_settings.py::test_post_settings_enable -x` | ❌ Wave 0 |
| APP-05 | tray state = "changes" when any project has changed_count > 0 | unit | `pytest tests/test_tray.py::test_state_changes_detected -x` | ❌ Wave 0 |
| APP-05 | tray state = "watching" when projects exist and no changes | unit | `pytest tests/test_tray.py::test_state_watching -x` | ❌ Wave 0 |
| APP-05 | tray state = "idle" when no projects registered | unit | `pytest tests/test_tray.py::test_state_idle -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_settings.py tests/test_autostart.py tests/test_tray.py -x -q`
- **Per wave merge:** `python -m pytest -x -q` (full 156+ test suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_autostart.py` — covers APP-02 autostart service (register/unregister/is_enabled), all with mocked winreg
- [ ] `tests/test_settings.py` — covers APP-04b GET/POST /api/settings router with mocked autostart module
- [ ] `tests/test_tray.py` — covers APP-05 tray state computation logic (`_compute_state()` pure function) with no pystray/OS dependency
- [ ] `tests/test_main.py` — covers APP-02 --background flag behavior and second-instance detection (mock socket + webbrowser)
- [ ] Framework already installed; no new test infrastructure needed

---

## Sources

### Primary (HIGH confidence)
- pystray 0.19.5 official docs (usage + reference) — threading model, Icon API, MenuItem signatures, Windows-specific threading note
  - https://pystray.readthedocs.io/en/latest/usage.html
  - https://pystray.readthedocs.io/en/latest/reference.html
- Python stdlib docs (winreg) — CreateKey, SetValueEx, OpenKey, QueryValueEx, DeleteValue, context manager pattern
  - https://docs.python.org/3/library/winreg.html
- shadcn/ui Switch component docs — install command, controlled pattern
  - https://ui.shadcn.com/docs/components/radix/switch

### Secondary (MEDIUM confidence)
- pystray PyPI page — version 0.19.5 confirmed, Pillow dependency, Windows backend
  - https://pypi.org/project/pystray/
- pystray FAQ (threading/framework integration) — confirmed "Windows: calling run() from non-main thread is safe"
  - https://pystray.readthedocs.io/en/latest/faq.html
- winreg patterns cross-verified across Python docs + multiple code examples

### Tertiary (LOW confidence)
- WebSearch community findings on pystray + uvicorn threading — confirmed main/daemon thread split; specific `server.should_exit` flag pattern from uvicorn internals (verify in uvicorn source)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pystray 0.19.5 confirmed on PyPI; winreg is stdlib; shadcn Switch is established project pattern
- Architecture (threading): HIGH — Windows-specific pystray threading behavior confirmed in official docs
- winreg patterns: HIGH — verified against Python stdlib docs with context manager pattern
- Pitfalls: HIGH — most derived from existing project patterns (Phase 10/11/13/14 decisions) and pystray docs
- Quit/shutdown (uvicorn server.should_exit): MEDIUM — pattern is commonly used in community examples; verify exact attribute name against uvicorn source before implementing

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (stable libraries; pystray releases infrequently)
