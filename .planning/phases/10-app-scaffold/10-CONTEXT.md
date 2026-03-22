# Phase 10: App Scaffold - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Distributable Windows .exe that starts a local FastAPI web server on port 7433 (with fallback to 7434–7443) and opens the app UI in the user's browser. Includes the full React frontend scaffold, PyInstaller packaging, GitHub Actions CI for automated .exe builds on tag push, and local dev workflow setup. System tray, auto-start, and onboarding are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Frontend Stack
- React + Vite + TypeScript
- shadcn/ui + Tailwind CSS for UI components
- Monorepo layout: `app/frontend/` for React, `app/` root (or `app/server.py`) for FastAPI backend
- FastAPI serves the compiled React `dist/` as StaticFiles in production — one server, no extra processes

### Distribution Format
- PyInstaller **onefile** — single self-contained `.exe`, fully portable
- Distributed via GitHub Releases (direct download)
- GitHub Actions CI workflow: on tag push, builds the `.exe` on a Windows runner and uploads to GitHub Releases automatically (no local Windows build required)

### Windows Defender / Signing
- **No code signing for now** — add bypass instructions to README and GitHub Release notes: "Click More info → Run anyway"
- `.exe` must include Windows version info metadata: `FileDescription`, `ProductName`, `CompanyName`, plus a `.ico` icon — reduces AV suspicion and looks professional

### Dev Workflow
- **Two terminals**: Vite dev server on port 5173 (with HMR) + uvicorn on port 7433, Vite proxies `/api` to FastAPI
- FastAPI includes a `GET /health` endpoint returning `{status: "ok", version: "x.x.x"}` and prints startup log: `Alteryx Git Companion running at http://localhost:7433`
- **Makefile** with targets:
  - `make dev` — starts both Vite and uvicorn
  - `make build` — compiles React to `dist/`
  - `make package` — runs PyInstaller to produce the `.exe`

### Claude's Discretion
- Exact PyInstaller `.spec` file structure (hidden imports, excludes, UPX settings)
- Specific Vite proxy configuration details
- GitHub Actions runner version and caching strategy
- Port fallback implementation details (socket binding loop)
- Icon design/source for `.ico`

</decisions>

<specifics>
## Specific Ideas

- The acd CLI (v1.0) is bundled inside the `.exe` and accessible to the FastAPI backend at runtime — PyInstaller must include it as a data file or bundled script
- Health endpoint is also useful for Phase 15 (system tray) health checks — design it with that in mind
- The `/health` startup log should print the exact port actually in use (important since 7433 may fall back to 7434+)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/alteryx_diff/` (Python package): The acd CLI — bundled as a dependency inside the `.exe`; FastAPI backend calls it via `pipeline.run()` facade
- `pyproject.toml` + `uv`: Existing dependency management; FastAPI and uvicorn will be added as new dependencies here
- `src/alteryx_diff/static/vis-network.min.js`: Vendored static asset pattern already established — same pattern applies to React `dist/`

### Established Patterns
- Python package uses `uv` for dependency management — new backend dependencies (fastapi, uvicorn, pyinstaller) added to `pyproject.toml`
- No existing frontend; `app/frontend/` is a greenfield Vite project

### Integration Points
- `pipeline.run()` in `src/alteryx_diff/pipeline/pipeline.py` — the entry point FastAPI will call for diff operations in later phases
- GitHub repo already exists (project uses git) — GitHub Actions CI workflow goes in `.github/workflows/`

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-app-scaffold*
*Context gathered: 2026-03-13*
