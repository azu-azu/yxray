---
phase: 10-app-scaffold
plan: "03"
subsystem: infra
tags: [pyinstaller, github-actions, windows-exe, versioninfo, ico, release-workflow]

# Dependency graph
requires:
  - phase: 10-app-scaffold plan 01
    provides: app/main.py entry point and app/server.py with _static_dir() sys._MEIPASS branch
  - phase: 10-app-scaffold plan 02
    provides: app/frontend/dist (npm run build output consumed by PyInstaller datas)
provides:
  - "app.spec: PyInstaller onefile spec with bootloader_ignore_signals=True, pathex=['src'], datas for frontend+acd static, 12 uvicorn hiddenimports"
  - "version_info.yml: Windows VERSIONINFO source (FileDescription, ProductName, OriginalFilename) for pyinstaller-versionfile"
  - "assets/icon.ico: placeholder 16x16 ICO binary (286 bytes) for exe icon"
  - ".github/workflows/release.yml: v* tag push triggers windows-latest build and GitHub Release upload via softprops/action-gh-release@v2"
  - ".gitignore updated with build/ and file_version_info.txt exclusions"
affects: [15-system-tray, all phases that produce releases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PyInstaller onefile spec: Analysis pathex=['src'] ensures alteryx_diff package discoverable without being installed"
    - "bootloader_ignore_signals=True in EXE block prevents double-SIGINT crash in onefile mode"
    - "upx=False avoids UPX tool dependency on CI runners (not pre-installed on windows-latest)"
    - "console=True in Phase 10 scaffold for debug visibility; Phase 15 will flip to False for tray mode"
    - "GitHub Actions: env: variable for TAG_NAME avoids expression injection; Windows PowerShell env access via $env:TAG_NAME"
    - "quoted 'on': key in release.yml prevents PyYAML YAML 1.1 boolean parsing of bare 'on:' as True"

key-files:
  created:
    - app.spec
    - version_info.yml
    - assets/icon.ico
    - .github/workflows/release.yml
  modified:
    - .gitignore

key-decisions:
  - "upx=False: UPX is not pre-installed on GitHub-hosted windows-latest runners; setting upx=True would silently skip compression or fail; set False for reliable CI"
  - "console=True for Phase 10 scaffold: Phase 10 is debug-phase; console=False would silently swallow startup errors; Phase 15 flips this when background/tray operation is added"
  - "quoted 'on': key in release.yml: PyYAML 1.1 parses bare 'on:' as Python True boolean; quoting as '\"on\":' makes it a string key and allows correct programmatic parsing"
  - "env: variable for TAG_NAME: using env: instead of inline ${{ github.ref_name }} in run: avoids expression injection risk; GitHub Actions security best practice"

patterns-established:
  - "PyInstaller spec pathex: always add 'src' to pathex when project uses src/ layout so Analysis discovers packages without .pth files"
  - "release.yml YAML on: key: always quote as '\"on\":' when the file may be parsed by PyYAML tooling"

requirements-completed: [APP-01, APP-03, APP-04a]

# Metrics
duration: 1min
completed: "2026-03-13"
---

# Phase 10 Plan 03: PyInstaller Packaging and GitHub Actions Release Summary

**PyInstaller onefile spec with bootloader_ignore_signals=True and 12 uvicorn hiddenimports, plus GitHub Actions release workflow that builds AlterxyGitCompanion.exe on windows-latest and uploads to GitHub Releases on v* tag push**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-13T23:28:11Z
- **Completed:** 2026-03-13T23:29:48Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `app.spec` created with bootloader_ignore_signals=True (prevents double-SIGINT crash), pathex=['src'] (alteryx_diff acd CLI discoverable), both datas entries (frontend/dist + alteryx_diff/static), 12 uvicorn hiddenimports, upx=False, console=True (debug mode for Phase 10)
- `version_info.yml` defines FileDescription="Alteryx Git Companion" and ProductName="Alteryx Git Companion" for pyinstaller-versionfile Windows VERSIONINFO generation
- `assets/icon.ico` placeholder (286-byte valid ICO binary, 16x16) satisfies PyInstaller icon= reference
- `.github/workflows/release.yml` triggers on v* tag push, builds on windows-latest runner: checkout → Python 3.11 + uv → npm ci + npm run build → pyivf-make_version → pyinstaller → softprops/action-gh-release@v2 upload with SmartScreen bypass instructions in release body

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PyInstaller spec, version_info.yml, and placeholder icon** - `e534880` (feat)
2. **Task 2: Create GitHub Actions release workflow** - `d1cfce8` (feat)

## Files Created/Modified

- `app.spec` - PyInstaller onefile spec: entry app/main.py, pathex=['src'], datas bundles frontend/dist and alteryx_diff/static, 12 uvicorn hiddenimports, bootloader_ignore_signals=True, upx=False, console=True
- `version_info.yml` - Windows VERSIONINFO YAML source: FileDescription, ProductName, OriginalFilename for pyinstaller-versionfile
- `assets/icon.ico` - Placeholder 16x16 ICO binary (286 bytes) generated via pure Python struct packing
- `.github/workflows/release.yml` - CI workflow: v* tag push to windows-latest build to GitHub Release; SmartScreen bypass instructions in release body
- `.gitignore` - Added build/ and file_version_info.txt to exclusions

## Decisions Made

- **upx=False**: UPX is not pre-installed on GitHub-hosted windows-latest runners; setting `upx=True` would silently skip UPX or fail the build. Set to False for reliable CI; can be added explicitly later if exe size becomes a concern.
- **console=True for Phase 10**: This is the debug phase. `console=False` would silently swallow any startup errors. Phase 15 (system tray) will flip this to False when background operation and crash logging are in place.
- **Quoted `"on":` in release.yml**: PyYAML (Python's YAML parser) follows YAML 1.1 where bare `on` is a boolean True. Verification scripts that use PyYAML to validate the workflow file would incorrectly fail to find the trigger. Quoting as `"on":` makes it a string key while remaining valid for GitHub Actions parser (which uses a different YAML implementation).
- **env: variable for TAG_NAME**: Per GitHub Actions security best practices, expression values are passed via `env:` block rather than inline in `run:` to avoid expression injection. On Windows runners, the env var is accessed as `$env:TAG_NAME` in PowerShell.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PyYAML parses bare `on:` as boolean True, breaking verification**

- **Found during:** Task 2 verification
- **Issue:** The plan's automated verify script uses `data.get('on', {})` to check the GitHub Actions trigger. PyYAML (YAML 1.1) parses bare `on:` key as Python boolean `True`, so `data.get('on', {})` returns `None` while the actual data is at `data.get(True)`. First verification run returned `FAIL: trigger: push v* tag missing`.
- **Fix:** Changed the `on:` key in release.yml to `"on":` (quoted string). This makes PyYAML parse it as the string `"on"` matching `data.get('on', {})`. GitHub Actions' YAML parser correctly treats both forms identically.
- **Files modified:** .github/workflows/release.yml
- **Verification:** Re-ran automated verify script — all checks passed.
- **Committed in:** `d1cfce8` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix required for verification to pass; no behavior change for GitHub Actions. Quoted key is valid YAML and handled identically by the GitHub Actions runner.

## Issues Encountered

None beyond the PyYAML `on:` key parsing issue documented above.

## User Setup Required

None - all configuration is in committed files. GitHub Actions workflow runs automatically on v* tag push using the repository's default GITHUB_TOKEN (no additional secrets required for softprops/action-gh-release@v2 with public repos).

## Next Phase Readiness

- Phase 10 packaging layer complete: `make package` on a Windows machine with dist/ built will produce dist/AlterxyGitCompanion.exe
- GitHub Actions will produce a release automatically on any `git push --tags` with a v* pattern
- Phase 15 (system tray) will update app.spec with console=False and add crash logging before the tray background mode is activated
- assets/icon.ico placeholder should be replaced with a real icon before v1 public release

## Self-Check: PASSED

All key files present (app.spec, version_info.yml, assets/icon.ico, .github/workflows/release.yml, 10-03-SUMMARY.md) and both task commits verified (e534880, d1cfce8).

---
*Phase: 10-app-scaffold*
*Completed: 2026-03-13*
