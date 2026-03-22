# Phase 10: App Scaffold - Research

**Researched:** 2026-03-13
**Domain:** PyInstaller onefile exe, FastAPI + uvicorn, React + Vite + shadcn/ui, GitHub Actions CI
**Confidence:** HIGH (core stack), MEDIUM (PyInstaller uvicorn onefile edge cases)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Frontend Stack**
- React + Vite + TypeScript
- shadcn/ui + Tailwind CSS for UI components
- Monorepo layout: `app/frontend/` for React, `app/` root (or `app/server.py`) for FastAPI backend
- FastAPI serves the compiled React `dist/` as StaticFiles in production — one server, no extra processes

**Distribution Format**
- PyInstaller **onefile** — single self-contained `.exe`, fully portable
- Distributed via GitHub Releases (direct download)
- GitHub Actions CI workflow: on tag push, builds the `.exe` on a Windows runner and uploads to GitHub Releases automatically (no local Windows build required)

**Windows Defender / Signing**
- No code signing for now — add bypass instructions to README and GitHub Release notes: "Click More info -> Run anyway"
- `.exe` must include Windows version info metadata: `FileDescription`, `ProductName`, `CompanyName`, plus a `.ico` icon — reduces AV suspicion and looks professional

**Dev Workflow**
- Two terminals: Vite dev server on port 5173 (with HMR) + uvicorn on port 7433, Vite proxies `/api` to FastAPI
- FastAPI includes a `GET /health` endpoint returning `{status: "ok", version: "x.x.x"}` and prints startup log: `Alteryx Git Companion running at http://localhost:7433`
- Makefile with targets:
  - `make dev` — starts both Vite and uvicorn
  - `make build` — compiles React to `dist/`
  - `make package` — runs PyInstaller to produce the `.exe`

### Claude's Discretion

- Exact PyInstaller `.spec` file structure (hidden imports, excludes, UPX settings)
- Specific Vite proxy configuration details
- GitHub Actions runner version and caching strategy
- Port fallback implementation details (socket binding loop)
- Icon design/source for `.ico`

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| APP-01 | User can install the app on Windows without installing Python (.exe installer, PyInstaller bundle) | PyInstaller onefile mode — entire Python runtime embedded; `multiprocessing.freeze_support()` required; `--bootloader-ignore-signals` for clean shutdown |
| APP-03 | App runs on port 7433 with automatic fallback to ports 7434–7443 if already in use | Socket bind loop pattern using `socket.bind()` + `OSError` catch; fallback list `range(7433, 7444)`; uvicorn.Config + uvicorn.Server programmatic start passes the bound socket |
| APP-04 | User can open the app UI by clicking the system tray icon (opens browser at localhost:PORT) | This phase scopes to: exe startup opens `webbrowser.open(f"http://localhost:{port}")` automatically; system tray icon click is Phase 15 |
</phase_requirements>

---

## Summary

Phase 10 builds the distributable skeleton: a single Windows `.exe` that starts a FastAPI/uvicorn web server, serves the compiled React frontend as StaticFiles, handles port conflicts on startup, opens a browser tab, and is built automatically by GitHub Actions on tag push.

The core technical challenge is PyInstaller onefile mode with uvicorn. There is a known documented issue: in `--onefile` mode PyInstaller spawns two processes (bootloader parent + Python child), and Ctrl+C signals are forwarded twice, causing uvicorn shutdown errors. The fix is `--bootloader-ignore-signals` in the spec file. Additionally, uvicorn uses lazy module imports that PyInstaller misses — a known set of hidden imports must be declared explicitly.

The React frontend is a standard Vite + TypeScript + shadcn/ui project. In dev mode, Vite proxies `/api` to `localhost:7433`. In production (inside the exe), FastAPI mounts the compiled `dist/` folder via `StaticFiles(directory=..., html=True)` — this handles SPA client-side routing correctly. Static asset path resolution inside the exe uses `sys._MEIPASS` (or equivalently `Path(__file__).parent`) to locate the bundled `dist/` folder.

**Primary recommendation:** Use a `.spec` file (not CLI flags) to control the full build — it is the only way to reliably configure datas, hiddenimports, version info, icon, and `--bootloader-ignore-signals` together.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.111 | HTTP API + StaticFiles server | Standard async Python web framework; StaticFiles built-in |
| uvicorn | >=0.29 | ASGI server (runs FastAPI) | Only production-grade ASGI server for FastAPI |
| PyInstaller | >=6.6 | Package Python + assets into onefile .exe | Mature, Windows-native, no separate Python install needed |
| React 18 | 18.x | Frontend UI framework | Locked decision |
| Vite | 5.x | Frontend build tool + dev HMR server | Locked decision |
| TypeScript | 5.x | Frontend language | Locked decision |
| shadcn/ui | latest | React component library | Locked decision |
| Tailwind CSS | 4.x | Utility CSS | shadcn/ui v2+ ships with Tailwind v4 support |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyinstaller-versionfile | >=3.0 | Generate Windows VERSIONINFO resource from YAML | Simplifies adding FileDescription, ProductName, CompanyName to .exe metadata |
| webbrowser (stdlib) | stdlib | Open browser tab to localhost:PORT on startup | No extra dependency needed |
| socket (stdlib) | stdlib | Port-availability probe before starting uvicorn | Lightweight; try `socket.bind(("127.0.0.1", port))` in loop |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyInstaller | Nuitka | Nuitka produces faster code but is significantly more complex to configure and has less community support for FastAPI+uvicorn |
| PyInstaller | cx_Freeze | Less maintained; worse Windows AV heuristics result |
| uvicorn programmatic | subprocess uvicorn | Subprocess approach breaks in onefile mode reliably; programmatic is required |
| pyinstaller-versionfile | Manual version_info.txt | Manual format is error-prone; YAML tool is simpler |

**Installation (backend):**
```bash
uv add fastapi uvicorn pyinstaller pyinstaller-versionfile
```

**Installation (frontend scaffold):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npx shadcn@latest init -t vite
```

---

## Architecture Patterns

### Recommended Project Structure

```
alteryx_diff/                   # existing repo root
├── app/
│   ├── server.py               # FastAPI app definition + StaticFiles mount + /health
│   ├── main.py                 # Entry point: port probe, uvicorn.run(), webbrowser.open()
│   └── frontend/               # Vite project (greenfield)
│       ├── src/
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   └── components/ui/  # shadcn/ui components live here
│       ├── dist/               # built output (gitignored) — bundled into exe
│       ├── index.html
│       ├── vite.config.ts
│       ├── package.json
│       └── tsconfig.json
├── app.spec                    # PyInstaller spec file
├── version_info.yml            # VERSIONINFO resource source
├── assets/
│   └── icon.ico                # Windows exe icon
├── Makefile                    # dev / build / package targets
├── .github/
│   └── workflows/
│       └── release.yml         # tag-push → Windows build → GitHub Release upload
├── src/alteryx_diff/           # existing acd CLI package (unchanged)
└── pyproject.toml              # adds fastapi, uvicorn, pyinstaller deps
```

### Pattern 1: Port Probe Loop

**What:** Try `socket.bind()` on each port in order; first successful bind wins. Pass the bound socket directly to uvicorn to avoid a race condition between probe and bind.

**When to use:** Always — avoids race condition of probe-then-start.

```python
# Source: socket stdlib docs + uvicorn.Config/Server API
import socket
import uvicorn
from app.server import app as fastapi_app

def find_port(start: int = 7433, end: int = 7443) -> tuple[int, socket.socket]:
    for port in range(start, end + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return port, sock
        except OSError:
            sock.close()
    raise RuntimeError(f"No available port in range {start}–{end}")

def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()   # required for PyInstaller onefile on Windows

    port, sock = find_port()
    print(f"Alteryx Git Companion running at http://localhost:{port}")

    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()   # blocks

if __name__ == "__main__":
    main()
```

### Pattern 2: FastAPI App with StaticFiles

**What:** FastAPI server, `/health` endpoint, React dist/ mounted at root.

**When to use:** Production mode (inside exe). Path resolution uses `sys._MEIPASS` / `Path(__file__).parent` to handle both dev and bundled contexts.

```python
# Source: FastAPI StaticFiles docs — https://fastapi.tiangolo.com/tutorial/static-files/
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

@app.get("/health")
def health() -> dict[str, str]:
    from importlib.metadata import version
    return {"status": "ok", "version": version("alteryx-diff")}

# Locate dist/ whether running from source or inside onefile exe
def _static_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Inside PyInstaller bundle — _MEIPASS is the temp extraction dir
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent
    return base / "frontend" / "dist"

app.mount("/", StaticFiles(directory=str(_static_dir()), html=True), name="frontend")
```

### Pattern 3: Vite Dev Proxy

**What:** Vite dev server proxies `/api` to FastAPI on 7433 during development; irrelevant at runtime.

```typescript
// Source: https://vite.dev/config/server-options
// app/frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:7433',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:7433',
        changeOrigin: true,
      },
    },
  },
})
```

### Pattern 4: PyInstaller Spec File

**What:** Single `.spec` file controls all build options — datas, hiddenimports, icon, version info, bootloader signal behavior.

```python
# Source: PyInstaller spec-files docs — https://pyinstaller.org/en/stable/spec-files.html
# app.spec
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the compiled React frontend
        ('app/frontend/dist', 'frontend/dist'),
        # Bundle acd package static assets (vis-network.min.js etc.)
        ('src/alteryx_diff/static', 'alteryx_diff/static'),
    ],
    hiddenimports=[
        # uvicorn lazy imports not auto-detected by PyInstaller
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AlterxyGitCompanion',
    debug=False,
    bootloader_ignore_signals=True,   # REQUIRED: prevents double-signal on Ctrl+C in onefile mode
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                    # no console window for end users
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version='file_version_info.txt',  # generated from version_info.yml
)
```

### Pattern 5: GitHub Actions Release Workflow

**What:** On `v*` tag push, build exe on `windows-latest` runner, upload to GitHub Release.

```yaml
# Source: multiple GitHub Actions examples — https://data-dive.com/multi-os-deployment-in-cloud-using-pyinstaller-and-github-actions/
# .github/workflows/release.yml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build-windows:
    name: Build Windows EXE
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install uv
        run: pip install uv

      - name: Install Python dependencies
        run: uv sync

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: app/frontend/package-lock.json

      - name: Build React frontend
        working-directory: app/frontend
        run: |
          npm ci
          npm run build

      - name: Generate version info
        run: uv run pyivf-make_version --source-format yaml --metadata-source version_info.yml --outfile file_version_info.txt --version ${{ github.ref_name }}

      - name: Build EXE
        run: uv run pyinstaller app.spec

      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/AlterxyGitCompanion.exe
```

### Anti-Patterns to Avoid

- **Using `pyinstaller` CLI flags instead of `.spec` file:** Cannot set `bootloader_ignore_signals`, version resource, and datas reliably via CLI alone. Always use a spec file.
- **Not calling `multiprocessing.freeze_support()`:** Windows onefile exes re-execute the entry point for each worker process. Without this call the exe spawns infinite child processes at startup.
- **Probing port then starting uvicorn separately:** Race condition — another process can grab the port between probe and bind. Pass the already-bound socket to uvicorn.Config instead.
- **`console=False` without error logging:** When the console window is hidden, uncaught exceptions are silently swallowed. Add file-based logging in production.
- **Mounting `StaticFiles` before API routes:** FastAPI's `app.mount("/", ...)` is a catch-all — it must be the LAST mount/include. Define all `/api` and `/health` routes before the static mount.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Windows VERSIONINFO resource | Custom binary struct packing | `pyinstaller-versionfile` + YAML | VERSIONINFO format is a complex binary structure; the tool handles all fields correctly |
| Frontend component primitives | Custom modal/button/input components | shadcn/ui + Radix UI | Accessibility, keyboard navigation, focus trapping are hard to get right; Radix handles all ARIA patterns |
| Port discovery and binding | Custom TCP polling loop | `socket.bind()` in try/except loop | The bind approach atomically claims the port; polling without binding is a race condition |
| SPA 404 fallback | Custom Starlette response class override | `StaticFiles(html=True)` | The `html=True` flag handles the index.html fallback natively |

**Key insight:** PyInstaller onefile + uvicorn has several non-obvious pitfalls (double-signal, missing lazy imports, freeze_support). The spec file pattern + known hidden imports list + `bootloader_ignore_signals=True` is the established solution — don't deviate.

---

## Common Pitfalls

### Pitfall 1: Infinite Process Spawning on Windows (Missing freeze_support)

**What goes wrong:** The exe launches, immediately spawns dozens of child processes, and the machine slows to a halt.
**Why it happens:** On Windows, `multiprocessing` uses `spawn` mode — the child process re-imports `__main__`. In onefile mode this re-runs the entry point. Without `freeze_support()` the protection guard is absent.
**How to avoid:** Call `multiprocessing.freeze_support()` as the very first statement in `if __name__ == "__main__":` block.
**Warning signs:** Task Manager shows N+1 processes of the exe; CPU spikes immediately on launch.

### Pitfall 2: Double-Signal Ctrl+C Crash (Missing bootloader_ignore_signals)

**What goes wrong:** Pressing Ctrl+C in the terminal causes uvicorn to print an asyncio `CancelledError` traceback instead of shutting down cleanly.
**Why it happens:** In onefile mode there are two processes: bootloader parent and Python child. Both receive SIGINT. Parent by default forwards the signal to child — child receives it twice.
**How to avoid:** Set `bootloader_ignore_signals=True` in the EXE section of the spec file (not available as a CLI flag).
**Warning signs:** Dirty shutdown errors on Ctrl+C; no graceful lifespan shutdown.

### Pitfall 3: uvicorn ModuleNotFoundError at Runtime

**What goes wrong:** Exe starts, uvicorn import fails with `ModuleNotFoundError: No module named 'uvicorn.protocols.http.auto'`.
**Why it happens:** uvicorn uses string-based dynamic imports for its protocol handlers. PyInstaller's static import analysis cannot detect them.
**How to avoid:** Include the full `hiddenimports` list in the spec file (see Pattern 4 above).
**Warning signs:** `ModuleNotFoundError` for any `uvicorn.*` submodule after packaging; works fine when running `python app/main.py` directly.

### Pitfall 4: StaticFiles Path Wrong Inside Bundle

**What goes wrong:** Exe starts, browser opens, but returns 500 or 404 for all pages.
**Why it happens:** `Path(__file__).parent` inside a frozen bundle points to a different location than expected (the temp extraction dir, not the project root). If hardcoded relative paths like `"app/frontend/dist"` are used they won't exist in the bundle.
**How to avoid:** Use `sys._MEIPASS` to anchor paths inside the bundle. The spec file `datas` tuple `('app/frontend/dist', 'frontend/dist')` places dist at `{_MEIPASS}/frontend/dist` — match this in the server code.
**Warning signs:** 404/500 on all frontend routes; directory not found errors in logs.

### Pitfall 5: StaticFiles Catch-All Shadows API Routes

**What goes wrong:** `/health` or `/api` routes return 404 because StaticFiles intercepts the request.
**Why it happens:** `app.mount("/", StaticFiles(...), ...)` is a prefix match on everything. FastAPI evaluates routes in declaration order; `mount("/")` catches everything if declared first.
**How to avoid:** Declare all API routes (including `/health`) before the final `app.mount("/", StaticFiles(...))`.
**Warning signs:** All API endpoints return 404; frontend loads fine; worked in dev with Vite proxy active.

### Pitfall 6: console=False Hides Startup Errors

**What goes wrong:** Exe double-clicks, nothing happens, no error shown.
**Why it happens:** `console=False` suppresses the console window. Any exception in startup is silently swallowed.
**How to avoid:** During development build with `console=True`. Add a try/except around startup that writes to `%TEMP%/agc-crash.log` before hiding the window.
**Warning signs:** Exe silently exits on double-click with no window or error.

---

## Code Examples

Verified patterns from official and community sources:

### Port Probe Without Race Condition

```python
# Source: socket stdlib docs
import socket

def find_available_port(start: int = 7433, count: int = 11) -> tuple[int, socket.socket]:
    """Returns (port, bound_socket). Caller must pass socket to uvicorn.Config."""
    for port in range(start, start + count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return port, sock
        except OSError:
            sock.close()
    raise OSError(f"All ports {start}–{start + count - 1} are in use")
```

### Uvicorn Programmatic Start with Pre-Bound Socket

```python
# Source: uvicorn docs — https://www.uvicorn.org/
import uvicorn

config = uvicorn.Config(app=fastapi_app, host="127.0.0.1", port=port, log_level="warning")
server = uvicorn.Server(config)
# Pass the already-bound socket to avoid race condition
import asyncio
asyncio.run(server.serve(sockets=[sock]))
```

### Version Info YAML (pyinstaller-versionfile)

```yaml
# version_info.yml
# Source: https://github.com/DudeNr33/pyinstaller-versionfile
Version: "1.0.0.0"
CompanyName: ""
FileDescription: "Alteryx Git Companion"
InternalName: "AlterxyGitCompanion"
LegalCopyright: ""
OriginalFilename: "AlterxyGitCompanion.exe"
ProductName: "Alteryx Git Companion"
```

Generate before pyinstaller run:
```bash
pyivf-make_version --source-format yaml --metadata-source version_info.yml --outfile file_version_info.txt --version 1.0.0
```

### Makefile Targets

```makefile
.PHONY: dev build package

dev:
	@echo "Starting dev servers..."
	@(cd app/frontend && npm run dev) & uvicorn app.server:app --port 7433 --reload

build:
	cd app/frontend && npm run build

package: build
	pyivf-make_version --source-format yaml --metadata-source version_info.yml \
	  --outfile file_version_info.txt --version $(shell uv run python -c "from importlib.metadata import version; print(version('alteryx-diff'))")
	uv run pyinstaller app.spec --noconfirm
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requirements.txt` + `pip` | `pyproject.toml` + `uv` | 2024 | Faster installs; project already uses uv |
| `create-react-app` | Vite | 2022-2023 | CRA is deprecated; Vite is the standard |
| Manual Tailwind config | `shadcn init` auto-configures | 2023-2024 | CLI handles tsconfig paths, tailwind config, components.json |
| Tailwind CSS v3 | Tailwind CSS v4 | 2025 | shadcn/ui ships Tailwind v4 support; use v4 |
| `actions/create-release@v1` + `actions/upload-release-asset@v1` | `softprops/action-gh-release@v2` | 2022+ | `actions/create-release` is deprecated; softprops combines create + upload in one action |
| `sys._MEIPASS` explicit access | `Path(__file__).parent` | PyInstaller 4.x+ | `__file__` is always set to absolute path in bundle; cleaner API |

**Deprecated/outdated:**
- `actions/create-release@v1`: GitHub deprecated — use `softprops/action-gh-release@v2` instead
- Tailwind CSS v3 `tailwind.config.js`: shadcn/ui v2 recommends Tailwind v4 with `@theme` directive

---

## Open Questions

1. **UPX availability on GitHub Actions windows-latest runner**
   - What we know: UPX is not pre-installed on GitHub-hosted Windows runners
   - What's unclear: Whether `upx=True` in spec causes a build failure or just a warning
   - Recommendation: Set `upx=False` initially; add UPX install step to CI only if exe size is a concern

2. **`console=False` vs `console=True` for initial build**
   - What we know: `console=False` hides all output; `console=True` shows a terminal window
   - What's unclear: User preference for alpha; crash log approach not yet decided
   - Recommendation: Use `console=True` for the Phase 10 scaffold; flip to `False` in Phase 15 (system tray) when background operation is expected

3. **Icon source**
   - What we know: Must be a `.ico` file; referenced in spec and version_info.yml
   - What's unclear: No icon asset exists yet
   - Recommendation: Create a minimal placeholder `assets/icon.ico` (16x16, 32x32 multi-size) using ImageMagick or online converter; replace before v1 release

4. **`uvicorn.Server.serve()` async vs `uvicorn.run()` sync**
   - What we know: `uvicorn.run()` is simpler but `uvicorn.Server` gives access to sockets parameter for pre-bound socket
   - What's unclear: Whether `uvicorn.run(app, host=..., port=..., fd=sock.fileno())` is the simpler equivalent
   - Recommendation: Use `uvicorn.Config` + `uvicorn.Server.run()` pattern; it is explicitly documented and more predictable

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (already configured in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-01 | PyInstaller spec file produces a valid exe (CI validates) | smoke (CI only) | `pyinstaller app.spec --noconfirm` exits 0 | Wave 0 |
| APP-03 | Port probe loop returns first available port and a bound socket | unit | `uv run pytest tests/test_port_probe.py -x` | Wave 0 |
| APP-03 | Port probe raises when all ports occupied | unit | `uv run pytest tests/test_port_probe.py::test_no_available_port -x` | Wave 0 |
| APP-04 | FastAPI /health endpoint returns `{status, version}` JSON | unit | `uv run pytest tests/test_server.py::test_health -x` | Wave 0 |
| APP-04 | StaticFiles serves index.html for unknown SPA routes | integration | `uv run pytest tests/test_server.py::test_spa_fallback -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_port_probe.py tests/test_server.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_port_probe.py` — covers APP-03: port selection logic
- [ ] `tests/test_server.py` — covers APP-04: /health endpoint + StaticFiles SPA fallback
- [ ] `tests/conftest.py` — shared FastAPI TestClient fixture (if not already present)
- [ ] `assets/icon.ico` — placeholder icon required before PyInstaller can run
- [ ] Framework already installed (pytest in dev deps) — no install step needed

---

## Sources

### Primary (HIGH confidence)

- PyInstaller spec-files docs — https://pyinstaller.org/en/stable/spec-files.html
- PyInstaller runtime-information docs — https://pyinstaller.org/en/stable/runtime-information.html
- FastAPI StaticFiles docs — https://fastapi.tiangolo.com/tutorial/static-files/
- Vite server proxy docs — https://vite.dev/config/server-options
- shadcn/ui Vite installation — https://ui.shadcn.com/docs/installation/vite

### Secondary (MEDIUM confidence)

- PyInstaller onefile + uvicorn double-signal issue — https://github.com/pyinstaller/pyinstaller/issues/8817 — verified: `bootloader_ignore_signals=True` is the fix
- pyinstaller-fastapi reference implementation — https://github.com/iancleary/pyinstaller-fastapi — confirmed hidden imports pattern
- GitHub Actions multi-OS PyInstaller workflow — https://data-dive.com/multi-os-deployment-in-cloud-using-pyinstaller-and-github-actions/ — YAML structure verified; actions versions updated to current
- pyinstaller-versionfile PyPI — https://pypi.org/project/pyinstaller_versionfile/ — YAML format confirmed

### Tertiary (LOW confidence)

- uvicorn hidden imports list — from community discussion; should be verified by running `pyinstaller --debug=imports` during Wave 0 to catch any missed submodules

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — FastAPI, uvicorn, Vite, shadcn/ui, PyInstaller are all well-documented with official sources
- Architecture: HIGH — spec file structure from official docs; StaticFiles pattern from official FastAPI docs; Vite proxy from official Vite docs
- PyInstaller uvicorn onefile: MEDIUM — known issues documented in GitHub issues; solutions community-verified but hidden imports list should be validated by running debug build
- GitHub Actions workflow: MEDIUM — pattern verified from multiple sources; action versions are current (checkout@v4, setup-python@v5, softprops/action-gh-release@v2)
- Pitfalls: HIGH — all pitfalls are grounded in official docs or tracked GitHub issues with reproduced fixes

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (30 days — stable ecosystem; PyInstaller releases infrequently)
