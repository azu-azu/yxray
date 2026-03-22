---
phase: 16-remote-auth-and-push
plan: "04"
subsystem: frontend
tags: [remote, github, gitlab, device-flow, pat, tabs, shadcn]
dependency_graph:
  requires:
    - 16-02
    - 16-03
  provides:
    - RemotePanel UI component
    - Sidebar Cloud icon nav
    - AppShell remote view routing
  affects:
    - app/frontend/src/components/AppShell.tsx
    - app/frontend/src/components/Sidebar.tsx
tech_stack:
  added:
    - "@radix-ui/react-tabs (via shadcn Tabs)"
  patterns:
    - "Self-fetching panel with useEffect on activeProjectId"
    - "setInterval polling with ref cleanup on unmount"
    - "GSD shadcn @/→src/ move pattern"
key_files:
  created:
    - app/frontend/src/components/RemotePanel.tsx
    - app/frontend/src/components/ui/tabs.tsx
  modified:
    - app/frontend/src/components/AppShell.tsx
    - app/frontend/src/components/Sidebar.tsx
decisions:
  - "shadcn Tabs installed then moved from @/components/ui/ to src/components/ui/ per Phase 11 pattern"
  - "GitHub PAT fallback calls POST /api/remote/github/connect (SERVICE_GITHUB keyring), not the GitLab endpoint"
  - "Poll interval stored in useRef to allow cleanup on unmount or project switch"
  - "renderAheadBehind() only shown when repo_url is non-null (upstream exists)"
metrics:
  duration: "3 min 16 sec"
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_changed: 4
requirements_met:
  - REMOTE-01
  - REMOTE-02
  - REMOTE-03
  - REMOTE-04
  - REMOTE-05
  - REMOTE-06
---

# Phase 16 Plan 04: Remote Panel Frontend Summary

**One-liner:** RemotePanel with GitHub device flow + GitLab PAT form, ahead/behind display, and push button — wired into AppShell/Sidebar via Cloud icon nav.

## What Was Built

The complete user-facing frontend for Phase 16 remote auth and push. All backend work from Plans 02 and 03 now surfaces in the UI.

### Files Created

**app/frontend/src/components/RemotePanel.tsx** (278 lines)
- Self-fetching: loads `/api/remote/status` on mount using `activeProjectId` from `useProjectStore`
- GitHub Device Flow: POST `/api/remote/github/start` → shows `user_code` in monospace pill, [Copy Code], [Open github.com/login/device], then `setInterval` polling every 3000ms on `/api/remote/github/status`
- GitHub PAT fallback: "Use a token instead" link reveals PAT input calling POST `/api/remote/github/connect` (SERVICE_GITHUB keyring endpoint — not GitLab)
- GitLab: numbered 1-2-3 instructions with PAT input calling POST `/api/remote/gitlab/connect`
- Connected state: green dot + "Connected" badge replaces connect flow
- Ahead/behind: `↑ N ahead · ↓ N behind` shown when `repo_url` exists
- Push button: POST `/api/remote/push`, inline error messages for auth-expired vs generic failure
- Loading state while fetching initial status
- No-project guard state

**app/frontend/src/components/ui/tabs.tsx**
- shadcn Tabs component installed via `npx shadcn@latest add tabs` then moved from `@/components/ui/` to `src/components/ui/` per project alias convention

### Files Modified

**app/frontend/src/components/AppShell.tsx**
- Added `import { RemotePanel }`
- `activeView` type extended: `'default' | 'settings' | 'remote'`
- `renderMainContent()` gains `remote` branch (before `settings`)
- Sidebar receives `onOpenRemote={() => setActiveView('remote')}` prop

**app/frontend/src/components/Sidebar.tsx**
- `SidebarProps` gains `onOpenRemote?: () => void`
- `Cloud` icon imported from lucide-react
- Cloud icon button added in bottom nav area before Settings gear

## Verification

- `npm run build` exits 0, no TypeScript errors (both tasks)
- `python -m pytest tests/test_remote.py` — 29/29 passed
- Pre-existing `test_find_available_port_returns_7433` failure is environment-specific (port 7433 occupied in dev); documented as deferred in STATE.md from Phase 15

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- FOUND: app/frontend/src/components/RemotePanel.tsx
- FOUND: app/frontend/src/components/ui/tabs.tsx
- FOUND: app/frontend/src/components/AppShell.tsx (modified)
- FOUND: app/frontend/src/components/Sidebar.tsx (modified)

Commits exist:
- FOUND: b2919d2 — feat(16-04): install shadcn Tabs and implement RemotePanel.tsx
- FOUND: 9476007 — feat(16-04): wire RemotePanel into AppShell and Sidebar
