# Phase 15: System Tray and Auto-start - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

The app runs silently in the background on Windows boot and communicates its status through a system tray icon. No new features — this phase is purely deployment UX: silent startup, tray icon with 3 states, and an in-app toggle to enable/disable auto-start. File watching, save, and history (Phases 12–14) are already complete.

</domain>

<decisions>
## Implementation Decisions

### Auto-start mechanism
- Windows Registry Run key: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- No admin rights required — user-space registration
- Display name: `Alteryx Git Companion`
- Registration happens on first app launch automatically (no separate installer step needed)
- If registration fails (registry write error): silent fail + log warning — auto-start is a convenience, not a blocker

### Silent startup behavior
- Registry Run key entry includes `--background` flag in the command
- Manual `.exe` double-click has no `--background` flag — app checks `sys.argv` to decide whether to open browser
- `--background` mode: no browser open, no console window, just the server + tray icon
- Manual launch mode: browser opens (existing Phase 10 behavior preserved)
- `console=False` in PyInstaller spec — flip from Phase 10's `console=True` debug setting
- Second-instance handling: detect existing running instance via port probe/lockfile → open browser to running instance → exit. Feels like Slack — clicking again focuses the app.

### Tray icon UX
- Left-click: opens browser UI at `localhost:PORT` (satisfies APP-04b)
- Right-click: context menu with two entries — "Open Alteryx Git Companion" + "Quit"
- Three icon states, shown via distinct icon files (not overlay badges):
  - **Idle** — default icon (no active projects watching)
  - **Watching** — active/distinct icon variant (watcher running, no changes)
  - **Changes detected** — amber/highlighted icon variant (changedCount > 0 for any project)
- Tooltip text updates with state (e.g. "Alteryx Git Companion — 2 changes detected")
- Tray state sync: system tray polls `GET /api/watch/status` every few seconds — consistent with SSE pattern from Phase 12, no new plumbing

### Auto-start toggle (Settings panel)
- Settings gear icon at the bottom of the left sidebar (below project list) — VS Code / Slack pattern
- Clicking gear opens a Settings panel in the main content area
- Phase 15 scope: single toggle only — "Launch on startup" (on/off)
- Toggle reads and writes the Registry Run key — on = key present, off = key absent
- No other settings in Phase 15; more settings added in future phases as needed

</decisions>

<specifics>
## Specific Ideas

- `--background` flag is the clean, testable way to distinguish boot launch from manual launch — explicit contract in `sys.argv`
- Second-instance UX should feel like Slack: clicking the exe again just surfaces the already-running app in the browser, never shows an error
- Settings gear at the bottom of the sidebar keeps the main nav uncluttered — users who never touch settings won't see it prominently

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/main.py`: `main()` function — Phase 15 extends it with `--background` flag check and single-instance detection before the existing `webbrowser.open` call
- `app/main.py`: `find_available_port()` — port probe can double as single-instance detection (if port 7433 is already bound, another instance is running)
- `app/frontend/src/components/Sidebar.tsx`: Phase 15 adds a settings gear icon at the bottom — follows existing sidebar pattern
- `app/frontend/src/components/AppShell.tsx`: `renderMainContent()` — add `Settings` as a new view branch alongside `ChangesPanel`, `HistoryPanel`, `EmptyState`

### Established Patterns
- shadcn/ui + Tailwind for all UI — Toggle/Switch component available in shadcn for the auto-start toggle
- FastAPI routers in `app/routers/` — new `settings.py` router for `GET/POST /api/settings` (read/write auto-start state)
- Module-level service imports in routers for `unittest.mock.patch` compatibility (Phases 11–14 pattern)
- Plain-language copy: "Launch on startup" not "Register HKCU Run key"
- AppShell owns all fetch/state; child components receive data as props

### Integration Points
- `app/main.py`: entry point — add `--background` handling and single-instance check here before uvicorn starts
- `app/spec/app.spec` (PyInstaller): flip `console=True` → `console=False` (explicitly flagged in Phase 10 notes)
- Windows Registry: `winreg` module (stdlib, Windows-only) — conditionally imported with platform check for cross-platform safety in tests
- `pystray` library: standard Python system tray library — runs in a daemon thread alongside uvicorn; polls `/api/watch/status` every 3–5 seconds to sync icon state

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-system-tray-and-auto-start*
*Context gathered: 2026-03-14*
