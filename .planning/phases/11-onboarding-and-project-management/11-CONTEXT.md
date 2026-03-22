# Phase 11: Onboarding and Project Management - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Guide new users through first-run setup (welcome screen, folder registration, git identity) and enable switching between multiple registered workflow project folders via a persistent left-panel sidebar. File watching, save version, history, and remote features are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Welcome Screen
- Single splash screen (centered card) — NOT a multi-step wizard
- Shows only when zero project folders are registered; never shown again after first folder is added
- Content: app name + tagline + brief bullet list (3-4 bullets: save versions, view history, compare changes, push to GitHub)
- Single CTA button that immediately opens the OS native folder picker dialog

### App Shell Layout
- Always-visible fixed-width left sidebar (e.g. 220px) — not collapsible
- Each project entry shows folder name (basename) only — no path, no badge in Phase 11 (badges added in Phase 12)
- Main content area shows an empty-state guidance card when a project has no saved versions: "No saved versions yet — make a change in Alteryx and come back to save a version"
- '+' icon button pinned at the top of the sidebar to add additional folders (accessible at all times once at least one project exists)
- Right-click context menu on a sidebar project item shows "Remove project" — removes from list only, does NOT delete files or git history, requires confirmation dialog

### Add Folder Flow
- OS native folder picker dialog (backend opens via Python — tkinter.filedialog or equivalent Windows API)
- If folder has no git history: show a brief plain-language confirmation before running git init ("This folder isn't a git repo yet. We'll set it up for version control. Continue?")
- If folder already has git history: add silently, no confirmation needed
- Project metadata (registered folders, active project) persisted in JSON config at `%APPDATA%\AlteryxGitCompanion\config.json` (Windows) / equivalent on macOS for dev

### Git Identity Prompt
- Check global git config (user.name / user.email) immediately after a folder is successfully added
- If missing: show an inline setup card in the main content area — "Almost done — enter your name and email for version control attribution" — two text fields (Name, Email) + Save button
- Save to global git config (`git config --global user.name` / `git config --global user.email`)
- After saving: dismiss the card, replace with the standard empty-state guidance panel
- If git identity already set: skip the prompt entirely, go straight to empty state

### Claude's Discretion
- Exact folder picker Python implementation (tkinter vs win32api vs subprocess)
- JSON config schema details (keys, versioning)
- Sidebar component styling details (hover states, active indicator, spacing)
- Exact copy for empty state and welcome screen bullets
- Error handling for edge cases (permission denied on folder, git not installed)

</decisions>

<specifics>
## Specific Ideas

- The app should feel like a desktop tool non-technical Alteryx analysts would be comfortable with — plain language throughout, no git jargon exposed unless necessary
- "This folder isn't a git repo yet. We'll set it up for version control." is the exact level of plain-language explanation for the git init confirmation
- The welcome screen CTA flows directly into adding the first folder — no intermediate step

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/server.py` (FastAPI): New API endpoints for folder management go here — `/api/projects` (list, add, remove), `/api/git/identity` (get, set), `/api/folder-picker` (trigger OS dialog)
- `app/frontend/src/lib/utils.ts`: `cn()` utility available for component className merging
- `app/frontend/src/App.tsx`: Currently just a scaffold — Phase 11 replaces this with the full app shell (sidebar + main content routing)

### Established Patterns
- FastAPI backend + React frontend with Vite proxy to `/api` for dev
- shadcn/ui + Tailwind CSS for UI components — all new components should follow this pattern
- No existing state management — Phase 11 needs to introduce a state solution (React Context or Zustand) for active project and project list

### Integration Points
- `app/main.py`: Entry point unchanged — server starts and opens browser; Phase 11 adds API routes to `server.py`
- `%APPDATA%` config path: use `platformdirs` or `pathlib` with `os.environ.get("APPDATA")` for Windows-safe path resolution
- Phase 12 (Watch) will read the registered folders list from the same config.json; the schema must support a `projects: [{path, name}]` structure

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-onboarding-and-project-management*
*Context gathered: 2026-03-13*
