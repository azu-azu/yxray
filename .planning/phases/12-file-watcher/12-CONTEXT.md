# Phase 12: File Watcher - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Continuously monitor all registered project folders for `.yxmd` and `.yxwz` file changes. Show a change badge on each sidebar project item. Auto-select native OS observer (local drives) or polling observer (5-second interval for network/SMB/UNC paths) without user configuration. Expose a watch status API used by Phase 13 (Save Version) to determine if the initial commit warning is needed. The warning itself is displayed in Phase 13 — Phase 12 only needs to supply the counts.

</domain>

<decisions>
## Implementation Decisions

### Change badge design
- Count badge showing number of changed `.yxmd`/`.yxwz` files (e.g. "3")
- Positioned on the far right of the sidebar project row (float right)
- Amber/orange color — signals "attention needed" without alarm; consistent with yellow=modified in ACD diff graph
- Badge clears after the user saves a version (wired in Phase 13)

### Watcher state persistence
- On startup, re-scan all registered projects using `git status --porcelain` against git HEAD to determine pending changes — badges restore accurately without storing stale state
- "Changed" means files modified vs git HEAD (not filesystem timestamps)
- Badge updates near-real-time with ~1–2 second debounce after OS event fires — avoids flicker during rapid Alteryx saves
- Frontend receives badge updates via Server-Sent Events (SSE) push from backend — no frontend polling

### Watcher lifecycle
- All registered projects watched simultaneously — not just the active one
- Watcher starts immediately when a new project folder is added (dynamic registration, no restart required)
- Watcher stops immediately when a project is removed
- If native observer fails on a network drive, auto-retry with polling fallback silently — no error shown to user unless both modes fail repeatedly

### Observer selection (WATCH-02)
- Auto-detect path type at watcher startup per project:
  - UNC paths (`\\server\share`) → polling observer (5-second interval)
  - Paths on network drives (detected via drive type / mount check) → polling observer
  - Local drives → native OS observer (watchdog's FSEventsObserver on macOS, ReadDirectoryChangesW on Windows)
  - No manual configuration required

### Watch status API (for WATCH-03 / Phase 13)
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
- Initial commit warning is triggered and displayed in Phase 13 (Save Version), not Phase 12

### SSE endpoint
- `GET /api/watch/events` — SSE stream that pushes badge update events to the React frontend
- Event format: `{type: "badge_update", project_id: "...", changed_count: N}`
- Frontend subscribes on mount, updates `useProjectStore` with change counts per project

### Claude's Discretion
- Exact watchdog observer class selection and threading model
- Debounce implementation details (asyncio vs threading.Timer)
- SMB/network drive detection mechanism (platform-specific)
- SSE connection reconnect logic on frontend
- How change counts are stored in-process between events

</decisions>

<specifics>
## Specific Ideas

- The badge should feel like Slack's unread indicator — clear count, amber tone, right-aligned. Non-alarming but actionable.
- "Auto-retry with polling fallback" is silent resilience — the user should never need to think about whether they're on a network drive.
- The `GET /api/watch/status` response shape is designed so Phase 13 can call it at save-time to decide whether to show the warning modal without any additional API design.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/config_store.py`: `load_config()` returns `{projects: [{id, path, name}]}` — watcher service reads this on startup to know which folders to observe
- `app/server.py`: Router registration pattern — new `watch` router added here alongside `projects`, `git_identity`, `folder_picker`
- `app/frontend/src/store/useProjectStore.ts`: `Project` interface needs a `changedCount?: number` field added — badge reads from store
- `app/frontend/src/components/Sidebar.tsx`: Badge rendered inside the existing project row button — far-right position using flex layout

### Established Patterns
- FastAPI + router modules in `app/routers/` — new `watch.py` router follows same pattern
- Zustand store in `app/frontend/src/store/` — add `setChangedCount(id, count)` action alongside existing `addProject`, `removeProject`
- SSE in FastAPI: `from fastapi.responses import StreamingResponse` with `EventSourceResponse` or custom async generator

### Integration Points
- `app/routers/projects.py`: POST `/api/projects` (add folder) must notify the watcher manager to start watching the new path
- Phase 13 (Save Version): calls `GET /api/watch/status` to read `has_any_commits` and `total_workflows` before showing the save dialog
- Phase 13: clears change badge by calling a watch manager method after successful commit (or watcher re-scans automatically post-commit)

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-file-watcher*
*Context gathered: 2026-03-14*
