---
phase: 15-system-tray-and-auto-start
verified: 2026-03-14T00:00:00Z
status: human_needed
score: 17/18 must-haves verified
human_verification:
  - test: "Run app on Windows: python -m app.main and confirm tray icon appears in taskbar notification area"
    expected: "Icon visible in Windows system tray; hover tooltip reads 'Alteryx Git Companion'"
    why_human: "pystray requires a Windows display; not testable on macOS CI"
  - test: "Left-click the tray icon"
    expected: "Browser opens at localhost:PORT (APP-04b requirement)"
    why_human: "Interactive OS event; pystray default=True click handler requires real display"
  - test: "Right-click tray icon and confirm menu shows 'Open Alteryx Git Companion' and 'Quit'"
    expected: "Both menu items visible; Quit kills the process; Open opens browser"
    why_human: "Context menu rendering requires real Windows tray"
  - test: "Run python -m app.main --background and confirm no browser opens"
    expected: "Process starts silently; tray icon appears; browser NOT opened"
    why_human: "Timer suppression only observable at runtime; no automated assertion"
  - test: "After first launch, check regedit at HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    expected: "Key 'Alteryx Git Companion' present with value ending in '--background'"
    why_human: "Windows registry write; winreg is mocked in tests; real registry requires Windows"
  - test: "Toggle 'Launch on startup' ON in Settings panel then check regedit"
    expected: "Registry key written; toggle OFF removes it"
    why_human: "End-to-end registry write from UI is Windows-only"
  - test: "Register a project, modify a .yxmd file, wait up to 10 seconds"
    expected: "Tray tooltip changes from 'watching' to '1 change detected' and icon turns amber"
    why_human: "Polling loop and tray icon image swap require real pystray + Windows display"
---

# Phase 15: System Tray and Auto-Start — Verification Report

**Phase Goal:** Implement system tray icon and auto-start functionality so the app can run silently in the background and launch on Windows startup.
**Verified:** 2026-03-14
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `register_autostart()` writes HKCU Run key containing `--background` flag | VERIFIED | `app/services/autostart.py` L45-46: `winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, value)` where value comes from `_get_exe_path()` returning `f'"{sys.executable}" --background'`; `test_register_writes_run_key` PASSES |
| 2  | `is_autostart_enabled()` returns True when key present, False when absent | VERIFIED | L64-68: `OpenKey` + `QueryValueEx`; `FileNotFoundError` returns False; 2 tests GREEN |
| 3  | `unregister_autostart()` deletes Run key (idempotent — absent key returns True) | VERIFIED | L85-91: `DeleteValue`; `FileNotFoundError` branch returns True; 2 tests GREEN |
| 4  | `main()` with `--background` does NOT call `webbrowser.open` | VERIFIED | `app/main.py` L74+L108-113: `background_mode` flag gates timer; `test_background_flag_suppresses_browser` PASSES |
| 5  | `is_instance_running()` returns True when port 7433 bound, False when free | VERIFIED | `app/main.py` L56-69: delegates to `find_available_port(start=7433, count=1)`; 2 tests GREEN |
| 6  | Second instance with manual launch opens browser and exits | VERIFIED | `app/main.py` L77-80: `if is_instance_running(): if not background_mode: webbrowser.open(...); sys.exit(0)` |
| 7  | `_compute_state({})` returns `('idle', 'Alteryx Git Companion')` | VERIFIED | `app/tray.py` L58-67: `any_watching = bool({}) = False`; `test_state_idle` PASSES |
| 8  | `_compute_state({'p': {'changed_count': 0}})` returns `('watching', '...')` | VERIFIED | `app/tray.py` L64-65: `total_changes==0` + `any_watching==True`; `test_state_watching` PASSES |
| 9  | `_compute_state({'p': {'changed_count': 3}})` returns `('changes', '... 3 changes detected')` | VERIFIED | `app/tray.py` L58-63: plural branch; `test_state_changes_detected` PASSES |
| 10 | Multiple projects: changed_count aggregated correctly | VERIFIED | `app/tray.py` L55: `sum(v.get("changed_count", 0) for v in status_data.values())`; `test_state_multiple_projects_aggregates` PASSES |
| 11 | Singular/plural handled correctly ('1 change detected' not '1 changes detected') | VERIFIED | `app/tray.py` L59: `word = "change" if total_changes == 1 else "changes"`; `test_state_singular_change` PASSES |
| 12 | GET /api/settings returns `{launch_on_startup: bool}` with 200 | VERIFIED | `app/routers/settings.py` L17-20: `autostart.is_autostart_enabled()`; 2 tests GREEN |
| 13 | POST /api/settings `{launch_on_startup: true}` calls `register_autostart()` | VERIFIED | `app/routers/settings.py` L26-27; `test_post_settings_enable` PASSES |
| 14 | POST /api/settings `{launch_on_startup: false}` calls `unregister_autostart()` | VERIFIED | `app/routers/settings.py` L28-29; `test_post_settings_disable` PASSES |
| 15 | Settings router registered in server.py | VERIFIED | `app/server.py` L23-24 import + L60: `app.include_router(settings.router)` |
| 16 | Gear icon in Sidebar opens Settings panel in AppShell | VERIFIED | `Sidebar.tsx` L25+L91: `onOpenSettings` prop + Button; `AppShell.tsx` L145: `onOpenSettings={() => setActiveView('settings')}` + L87-89: `if (activeView === 'settings') return <SettingsPanel />` |
| 17 | SettingsPanel fetches GET /api/settings on mount and POSTs on toggle | VERIFIED | `SettingsPanel.tsx` L9-17: `useEffect` fetch; L19-30: `handleToggle` with optimistic update POST |
| 18 | System tray icon visible in Windows taskbar with state polling | HUMAN NEEDED | Code wired correctly (`TrayIcon._poll_loop` + `start_tray` called from `app/main.py` daemon thread) but display requires Windows hardware |

**Score:** 17/18 truths verified automatically; 1 requires Windows hardware

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/autostart.py` | register/unregister/is_autostart_enabled | VERIFIED | 95 lines; winreg deferred inside function bodies after `sys.platform != "win32"` guard |
| `app/main.py` | is_instance_running(), --background, tray thread | VERIFIED | All three features present; autostart registered at line 87; tray thread starts at line 100-105 |
| `app/tray.py` | _compute_state, TrayIcon, start_tray | VERIFIED | 211 lines; pystray guarded by try/except; _compute_state is pure function at module level |
| `app/routers/settings.py` | GET/POST /api/settings | VERIFIED | 31 lines; module-level autostart import for mock.patch compatibility |
| `app/server.py` | settings router registered | VERIFIED | L23+L60: import and include_router call present |
| `app/frontend/src/components/SettingsPanel.tsx` | Settings view with Switch toggle | VERIFIED | 52 lines; fetches /api/settings on mount; optimistic toggle POST |
| `app/frontend/src/components/Sidebar.tsx` | Gear icon at bottom | VERIFIED | L25: onOpenSettings prop; L86-97: mt-auto section with Settings Button |
| `app/frontend/src/components/AppShell.tsx` | activeView state, settings branch | VERIFIED | L21: activeView state; L87-89: settings branch first in renderMainContent(); L145: onOpenSettings wired |
| `app/frontend/src/components/ui/switch.tsx` | shadcn Switch component | VERIFIED | File exists |
| `app/frontend/src/components/ui/label.tsx` | shadcn Label component | VERIFIED | File exists |
| `assets/icon-watching.ico` | Green placeholder icon | VERIFIED | File exists (64x64 green PIL-generated) |
| `assets/icon-changes.ico` | Amber placeholder icon | VERIFIED | File exists (64x64 amber PIL-generated) |
| `app.spec` | console=False, pystray hiddenimports, icon assets | VERIFIED | L60: `console=False`; L29-31: pystray/PIL/PIL.Image/PIL.ImageDraw in hiddenimports; L12-14: three icon ICO datas entries |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app/services/autostart.py` | `from app.services import autostart; autostart.register_autostart()` | WIRED | L85-87 of main.py |
| `app/main.py` | `app/tray.py` | `from app import tray; threading.Thread(target=tray.start_tray, ...)` | WIRED | L98-105 of main.py |
| `app/tray.py` | `GET /api/watch/status` | `requests.get(f'http://localhost:{port}/api/watch/status', timeout=3)` | WIRED | L129-133 of tray.py |
| `app/tray.py` | `uvicorn.Server` | `server.should_exit = True` in on_quit handler | WIRED | L171 of tray.py |
| `app/routers/settings.py` | `app/services/autostart.py` | `from app.services import autostart` at module level | WIRED | L8 of settings.py |
| `app/server.py` | `app/routers/settings.py` | `app.include_router(settings.router)` | WIRED | L60 of server.py |
| `AppShell.tsx` | `SettingsPanel.tsx` | `import SettingsPanel` + `renderMainContent()` settings branch | WIRED | L9 import + L87-89 render |
| `AppShell.tsx` | `Sidebar.tsx` | `onOpenSettings={() => setActiveView('settings')}` | WIRED | L145 |
| `SettingsPanel.tsx` | `GET /api/settings` | `fetch('/api/settings')` in useEffect | WIRED | L10 |
| `app.spec` | `assets/icon*.ico` | Three datas entries for ICO files | WIRED | L12-14 of app.spec |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| APP-02 | 15-01, 15-02, 15-05 | App starts automatically when Windows boots, running silently in the background | SATISFIED | `app/services/autostart.py` writes HKCU Run key; `--background` flag in `app/main.py` suppresses browser; `is_instance_running()` handles second-instance; 9 tests GREEN |
| APP-05 | 15-01, 15-03, 15-04, 15-05 | System tray icon shows app status (watching / changes detected / idle) | SATISFIED | `app/tray.py` with `_compute_state()` + `TrayIcon` polling loop; `app/routers/settings.py` GET/POST /api/settings; Settings panel in frontend with Launch on startup toggle; 9 tests GREEN |
| APP-04b | Not in any plan `requirements` field | User can open the app UI by clicking the system tray icon | ORPHANED — see note below |

**APP-04b Note:** REQUIREMENTS.md maps APP-04b to Phase 15 and marks it "Pending". The implementation exists in `app/tray.py` L166-167: `on_open` handler calls `webbrowser.open(f"http://localhost:{self.port}")` with `default=True` on the `PystrayMenuItem`, which makes left-click trigger `on_open`. However, no PLAN in Phase 15 declares APP-04b in its `requirements:` frontmatter field — it appears incidentally implemented as part of the tray menu. The behavior is implemented but not formally claimed by any plan, and it cannot be automated-tested (requires Windows display). It is flagged as human verification item #2.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/tray.py` | 127, 136 | `return {}` | Info | These are legitimate error-path fallbacks in `_get_status_data()` (no requests library, or HTTP failure) — not stubs. Correct behavior. |

No blockers or warnings found. The `return {}` instances are proper error handling, not empty implementations.

---

## Test Results

All 18 Phase 15 automated tests pass:

- `tests/test_autostart.py` — 6/6 PASSED (register, is_enabled false/true, unregister, unregister absent, non-Windows)
- `tests/test_settings.py` — 4/4 PASSED (GET enabled, GET disabled, POST enable, POST disable)
- `tests/test_tray.py` — 5/5 PASSED (changes, watching, idle, multi-project, singular)
- `tests/test_main.py` — 3/3 PASSED (background flag, instance running true/false)

Full suite (excluding pre-existing `test_port_probe` environment failure from Phase 10): **170 passed, 1 xfailed**.

All 9 documented commits verified in git history: `ff0f3c8`, `e081a6f`, `7b6d544`, `1ad5f60`, `edb2b30`, `a9bc466`, `12fe216`, `db00473`, `d67ccad`.

---

## Human Verification Required

### 1. System Tray Icon Visible on Windows

**Test:** Run `python -m app.main` on a Windows machine
**Expected:** Tray icon appears in taskbar notification area; hover tooltip reads "Alteryx Git Companion"
**Why human:** pystray renders to a real OS tray; macOS CI cannot verify this

### 2. Left-Click Opens Browser (APP-04b)

**Test:** Left-click the tray icon
**Expected:** Browser opens at `http://localhost:PORT` (the running app URL)
**Why human:** Interactive OS click event on pystray `default=True` MenuItem; requires Windows display

### 3. Right-Click Menu Entries

**Test:** Right-click the tray icon
**Expected:** Menu shows "Open Alteryx Git Companion" and "Quit"; Quit terminates process cleanly; Open opens browser
**Why human:** Context menu rendering is OS-native; requires live tray instance

### 4. Background Mode Suppresses Browser

**Test:** Run `python -m app.main --background`
**Expected:** Process starts; no browser window opens; tray icon still appears; app accessible at localhost:PORT
**Why human:** Timer suppression only visible by observing browser; tray still requires Windows

### 5. Windows Registry Key Written on Launch

**Test:** Open regedit after first launch; navigate to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
**Expected:** Key "Alteryx Git Companion" present with value ending in `--background`
**Why human:** winreg is mocked in tests; actual write requires Windows OS

### 6. Settings Panel Toggle Writes/Removes Registry Key

**Test:** Open app in browser; click gear icon; toggle "Launch on startup" ON then OFF; check regedit
**Expected:** Toggle ON writes registry key; Toggle OFF removes it
**Why human:** End-to-end registry write from browser UI to Windows registry; Windows-only path

### 7. Tray State Changes Reflect Watch Activity

**Test:** Register a project folder; modify a .yxmd file inside it; wait up to 10 seconds
**Expected:** Tray tooltip changes from "Alteryx Git Companion — watching" to "Alteryx Git Companion — 1 change detected"; icon turns amber
**Why human:** 5-second polling loop + pystray icon.icon/icon.title swap requires live Windows tray

---

## Gaps Summary

No automated gaps found. All code artifacts exist, are substantive, and are wired correctly. The phase is blocked only on Windows hardware human verification for:

1. Physical tray icon display (pystray OS dependency)
2. APP-04b formal requirement status — implemented but not claimed in any plan's `requirements:` field and marked "Pending" in REQUIREMENTS.md; the implementation exists in `on_open` with `default=True` but needs human sign-off on Windows to close

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
