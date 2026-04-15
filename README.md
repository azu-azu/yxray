# Alteryx Canvas Diff (ACD) + Git Companion

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub release](https://img.shields.io/github/v/release/Laxmi884/alteryx-git-companion)](https://github.com/Laxmi884/alteryx-git-companion/releases)

A two-part system that brings **version control and change visibility to Alteryx workflows** — something Alteryx Designer has never natively provided.

| Component | What it is |
|---|---|
| **ACD CLI** | A command-line tool that compares two `.yxmd`/`.yxwz` files and produces a structured HTML diff report or JSON output |
| **Git Companion** | A Windows desktop app (system tray) that wraps git and ACD into a point-and-click interface for analysts who have never used version control |

Built for analytics developers and governance teams who need to understand what changed between workflow versions without reading raw XML.

---

## Part 1 — ACD CLI

### Features

- **Zero false positives** — strips Alteryx XML noise (attribute reordering, whitespace, auto-generated GUIDs, timestamps, TempFile paths) before comparing
- **Field-level diffs** — reports before/after values for every changed configuration field, not just "this tool changed"
- **ToolID-regeneration safe** — two-pass matching (exact ToolID lookup → Hungarian algorithm fallback) prevents phantom add/remove pairs when Alteryx regenerates tool IDs on save
- **Interactive graph** — embedded vis-network graph with color-coded nodes (green=added, red=removed, yellow=modified, blue=connection change); click any node to see its inline diff
- **Self-contained HTML** — all CSS, JavaScript, and the graph library are inlined; report works offline and on air-gapped networks
- **ALCOA+ governance footer** — source file paths, SHA-256 hashes, and generation timestamp embedded in every report for audit compliance
- **CI/CD friendly** — `--json` flag writes machine-readable output to stdout; predictable exit codes (0/1/2)
- **Position-aware** — canvas X/Y positions are excluded from diff detection by default (layout noise); opt in with `--include-positions`
- **App file support** — `.yxwz` Alteryx App files are accepted as input; interface/UI-only tools (`AlteryxGuiToolkit.*` — tabs, text boxes, containers, actions) are filtered out by default to eliminate noise when comparing an app against a workflow; opt out with `--no-filter-ui-tools`

---

### Installation

#### Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip

#### With uv (recommended)

```bash
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx_diff

# Install and activate environment
uv sync

# The acd command is now available
uv run acd --help
```

To install as a global tool so `acd` is available anywhere:

```bash
uv tool install .
acd --help
```

#### With pip

```bash
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx_diff

pip install .

# The acd command is now available
acd --help
```

#### From source (editable install)

```bash
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx_diff

uv sync --all-groups   # includes dev dependencies
uv run acd --help
```

---

### Usage

#### Basic diff

```bash
acd workflow_v1.yxmd workflow_v2.yxmd
```

Produces `diff_report.html` in the current directory and exits with code `1` (differences found).

> **Paths with spaces:** quote the arguments in your shell:
> ```bash
> acd "My Workflow v1.yxmd" "My Workflow v2.yxmd"
> ```

#### Custom output path

```bash
acd workflow_v1.yxmd workflow_v2.yxmd --output reports/my_diff.html
```

#### JSON output (for CI/CD)

```bash
acd workflow_v1.yxmd workflow_v2.yxmd --json
```

Writes JSON to stdout. No HTML file is created.

```bash
# Pipe to a file
acd workflow_v1.yxmd workflow_v2.yxmd --json > diff.json

# Pipe to jq for inspection
acd workflow_v1.yxmd workflow_v2.yxmd --json | jq '.modified[].tool_type'
```

#### Include position changes

By default, canvas X/Y position changes are ignored (layout noise). To include them:

```bash
acd workflow_v1.yxmd workflow_v2.yxmd --include-positions
```

#### Canvas layout in graph

By default, the graph uses hierarchical left-to-right auto-layout (follows data flow order). To use Alteryx canvas X/Y coordinates for node positions instead:

```bash
acd workflow_v1.yxmd workflow_v2.yxmd --canvas-layout
```

#### Compare an app (.yxwz) against a workflow (.yxmd)

App files contain interface/UI-only tools (`AlteryxGuiToolkit.*` — tabs, text boxes, containers, actions) that have no counterpart in regular workflows. These are filtered out by default so only analytical tool changes are shown:

```bash
acd workflow.yxmd "My App.yxwz" --output review.html
```

To keep UI tools in the diff (e.g. comparing two apps where interface changes matter):

```bash
acd app_v1.yxwz app_v2.yxwz --no-filter-ui-tools --output review.html
```

#### Quiet mode (CI pipelines)

Suppress all terminal output — only the exit code is returned:

```bash
acd workflow_v1.yxmd workflow_v2.yxmd --quiet
echo $?   # 0 = no diff, 1 = diff found, 2 = error
```

#### Combine flags

```bash
# Canonical audit run: JSON output, positions included, quiet
acd workflow_v1.yxmd workflow_v2.yxmd --json --include-positions --quiet > audit.json

# Full HTML report with canvas layout
acd baseline.yxmd promoted.yxmd --output review.html --canvas-layout
```

---

### CLI Reference

```
acd [OPTIONS] WORKFLOW_A WORKFLOW_B
```

| Argument / Option | Default | Description |
|---|---|---|
| `WORKFLOW_A` | required | Baseline `.yxmd` or `.yxwz` file — quote paths that contain spaces |
| `WORKFLOW_B` | required | Changed `.yxmd` or `.yxwz` file — quote paths that contain spaces |
| `--output`, `-o` | `diff_report.html` | Output path for the HTML report (ignored when `--json` is set) |
| `--include-positions` | off | Include canvas X/Y position changes in diff detection (excluded by default to avoid layout noise) |
| `--canvas-layout` | off | Use Alteryx canvas X/Y coordinates for graph node positions (default: hierarchical auto-layout) |
| `--no-filter-ui-tools` | off | Keep `AlteryxGuiToolkit.*` interface tools in the diff (by default they are filtered out to reduce noise when comparing apps against workflows) |
| `--json` | off | Write JSON diff to stdout instead of HTML file (pipe-friendly) |
| `--quiet`, `-q` | off | Suppress all terminal output; exit code only (for CI pipelines) |
| `--help` | | Show help and exit |

---

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | No differences found |
| `1` | Differences detected |
| `2` | Error — missing file, malformed XML, unreadable input |

These codes are stable and suitable for CI/CD gating:

```bash
acd old.yxmd new.yxmd --quiet
if [ $? -eq 1 ]; then
  echo "Workflow changed — review required"
fi
```

---

### Output Formats

#### HTML Report

The default output is a single self-contained `.html` file with:

- **Summary panel** — counts of added (green), removed (red), modified (yellow), and connection changes (blue)
- **Per-tool detail** — expandable sections for each modified tool showing before/after values for every changed field
- **Interactive graph** — embedded vis-network graph; click any node to see its inline configuration diff; toggle to show only changed nodes
- **Governance footer** — collapsible `<details>` section with source file absolute paths, SHA-256 file hashes, and generation timestamp (ALCOA+ audit compliance)
- **Report header** — both compared file names and generation timestamp

The report has zero CDN references — all JavaScript and CSS are inlined. It opens correctly on air-gapped networks.

#### JSON Output (`--json`)

Schema written to stdout:

```json
{
  "added": [
    {
      "tool_id": 42,
      "tool_type": "AlteryxBasePluginsGui.Filter.Filter",
      "config": { "Expression": "Amount > 1000" }
    }
  ],
  "removed": [
    {
      "tool_id": 17,
      "tool_type": "AlteryxBasePluginsGui.DbFileInput.DbFileInput",
      "config": { "File": "sales_data.csv" }
    }
  ],
  "modified": [
    {
      "tool_id": 23,
      "tool_type": "AlteryxBasePluginsGui.Formula.Formula",
      "field_diffs": [
        {
          "field": "Expression",
          "before": "[Amount] * 1.05",
          "after": "[Amount] * 1.10"
        }
      ]
    }
  ],
  "metadata": {
    "file_a": "/absolute/path/to/workflow_v1.yxmd",
    "file_b": "/absolute/path/to/workflow_v2.yxmd",
    "sha256_a": "a3f2c1...",
    "sha256_b": "b7d9e4...",
    "generated_at": "2026-03-07T12:34:56.789123+00:00"
  }
}
```

When no differences are found, `added`, `removed`, and `modified` are empty arrays and the exit code is `0`.

---

### How It Works

ACD runs an immutable four-stage pipeline:

```
.yxmd files
    │
    ▼
┌─────────────┐
│   Parser    │  lxml — loads XML, validates structure, emits WorkflowDoc
└──────┬──────┘
       │ WorkflowDoc (nodes, connections, typed fields)
       ▼
┌─────────────┐
│ Normalizer  │  C14N canonicalization, GUID/timestamp stripping,
│             │  position separation, SHA-256 config hashing
└──────┬──────┘
       │ NormalizedWorkflowDoc (config_hash per node, position separate)
       ▼
┌─────────────┐
│   Matcher   │  Pass 1: exact ToolID lookup (O(n))
│             │  Pass 2: Hungarian algorithm fallback (scipy),
│             │          cost threshold 0.8 — rejects false matches
└──────┬──────┘
       │ MatchResult (paired nodes, unmatched additions/removals)
       ▼
┌─────────────┐
│   Differ    │  DeepDiff for field-level config changes,
│             │  frozenset symmetric difference for connections
└──────┬──────┘
       │ DiffResult
       ▼
  HTML / JSON renderer
```

**Why normalization matters:** Alteryx injects noise on every save — attribute ordering changes, auto-generated GUIDs, session timestamps, and TempFile paths. Without stripping these, every save would appear as a diff. The normalization layer eliminates all of this before any comparison happens.

**Why two-pass matching matters:** Alteryx can regenerate all ToolIDs when a workflow is re-saved in some versions. A naive ToolID-only matcher would report every tool as removed and re-added. The Hungarian algorithm fallback matches tools by configuration similarity and canvas proximity, preventing these phantom pairs.

---

## Part 2 — Git Companion (Desktop App)

The Git Companion is a Windows desktop application that makes version control invisible to non-developer Alteryx users. It wraps git and the ACD diff engine in a point-and-click UI — no terminal required.

### Overview

```
Windows .exe (PyInstaller onefile)
  ├── FastAPI server  (localhost:7433–7443, auto port probe)
  │     ├── /api/projects   — register/list workflow folders
  │     ├── /api/save       — commit, undo last, discard changes
  │     ├── /api/history    — list commits; render ACD diff for any two versions
  │     ├── /api/remote     — GitHub/GitLab auth, push, PR creation
  │     ├── /api/branch     — create, checkout, delete experiment branches
  │     ├── /api/settings   — launch-on-startup toggle
  │     └── /api/watch      — SSE stream of real-time badge updates
  └── React SPA  (served as static files from the same process)

System tray icon  (idle / watching / changes states)
```

The ACD pipeline is called directly from `/api/history` — no subprocess, no extra install.

---

### Installation (end users)

Download `AlteryxGitCompanion.exe` from the [Releases page](../../releases) and run it. No Python, no git, no dependencies — everything is bundled.

On first launch the app:
1. Binds to the first available port in the range `7433–7443`
2. Registers itself in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` so it starts automatically at login (in background mode)
3. Opens the UI in your default browser

If another instance is already running, the second launch simply opens the browser to the existing instance and exits.

---

### Features

#### Project registration

Add any folder containing `.yxmd` or `.yxwz` files as a project. The companion checks whether the folder is already a git repository and offers to initialise one if not — no prior git knowledge required.

#### Real-time file watching

A `watchdog` observer monitors every registered project folder for changes to workflow files (`.yxmd`, `.yxwz`, `.yxmc`, `.yxzp`, `.yxapp`). Changes are debounced (1.5 s) and pushed to the browser via SSE — the badge on each project updates instantly without polling.

Network paths (UNC `\\server\share`) automatically fall back to polling mode since filesystem events are not reliable over SMB.

#### Save a version (commit)

The Changes panel shows all modified workflow files with checkboxes. Select the files to version, write a plain-English description, and click Save. Under the hood this runs:

```
git add <selected files>
git commit -m "<message>"
```

If the folder has no git repository yet, `git init` runs automatically before the first commit.

#### Undo last version

Rolls back the most recent commit with `git reset --soft HEAD~1`, returning files to the staged state. The change badge is recalculated immediately via SSE.

#### Discard changes

Reverts selected files to their last committed state (`git checkout -- <files>`). Useful for throwing away accidental edits without rolling back the entire commit history.

#### Version history + inline diff

The History panel lists all commits for a project (author, date, message). Clicking any commit triggers the ACD pipeline against the previous version and renders the full HTML diff report inline — interactive graph, field-level changes, governance footer and all.

#### Remote push (GitHub / GitLab)

**GitHub** — uses the [Device Flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow) for authentication. No personal access token needed; the user visits `github.com/login/device` and enters a code. The token is stored in the OS keyring (Windows Credential Manager), never in a config file.

**GitLab** — authenticates with a personal access token (PAT), also stored in the OS keyring.

On first push the companion:
1. Resolves the authenticated user's username
2. Creates a private remote repository named after the local folder (slugified)
3. Sets the remote and pushes all branches

Subsequent pushes go directly to the existing remote.

#### Branch management (experiment branches)

Create experiment branches from HEAD with a plain-English description — the branch name is auto-formatted as `experiment/YYYY-MM-DD-<slug>`. Checkout is blocked if there are uncommitted changes, preventing accidental loss of work. Protected branches (`main`, `master`) cannot be deleted.

The merge-base endpoint returns the SHA where an experiment branch diverged from `main`/`master`, enabling the frontend to show exactly which commits belong to the experiment.

#### Pull request creation

After pushing a branch, the Remote panel offers a one-click PR creation flow: enter a title and description, and the companion creates a draft PR on GitHub or GitLab via their REST APIs.

#### System tray icon

Three icon states reflect the current watch status:

| State | Icon colour | Tooltip |
|---|---|---|
| Idle (no projects) | White | `Alteryx Git Companion` |
| Watching (no changes) | Green | `Alteryx Git Companion — watching` |
| Changes detected | Amber | `Alteryx Git Companion — N changes detected` |

The tray icon polls `/api/watch/status` every 5 seconds to stay current. Right-click menu: **Open** (opens browser) and **Quit** (graceful shutdown).

#### Launch on startup

Controlled via the Settings panel. Registers or removes the `HKCU Run` registry key. When launched via autostart the app runs in `--background` mode (no browser open, no window).

---

### Architecture details

#### Single-instance detection

On startup the app tries to bind port 7433. If the port is already taken, another instance is running — the new process opens the browser to `http://localhost:7433` and exits immediately.

#### Port probe

If port 7433 is unavailable (e.g., conflict with another application), the companion probes `7433–7443` in order and binds the first free port. The pre-bound socket is passed directly to uvicorn to eliminate the race condition between probing and binding.

#### SSE event bus

File-system events arrive on `watchdog` daemon threads. They are forwarded to asyncio subscriber queues via `loop.call_soon_threadsafe` — never called directly across the thread boundary. Each connected browser tab holds its own queue; the manager fans out to all subscribers. New subscribers receive the current badge state immediately on connect (seed event).

#### Credential storage

All tokens (GitHub OAuth, GitLab PAT) are stored exclusively in the OS keyring. In a PyInstaller frozen bundle, keyring backend discovery is broken by default; the companion explicitly selects `WinVaultKeyring` (Windows Credential Manager) at startup to ensure tokens survive process restarts.

#### PyInstaller bundle

Built as a Windows onefile `.exe`. The React frontend `dist/` directory and all static assets (tray icons) are bundled via `sys._MEIPASS`. `multiprocessing.freeze_support()` is called first in `main()` to prevent infinite spawn loops on Windows onefile bundles.

---

### Building from source

#### Prerequisites

- Python 3.11+ with `uv`
- Node.js 20+ with npm

#### Development setup

```bash
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx_diff

# Install Python dependencies
uv sync --all-groups

# Install frontend dependencies
cd app/frontend
npm install
cd ../..

# Install pre-commit hooks
uv run pre-commit install
```

#### Run in development mode

```bash
# Terminal 1 — Python backend
uv run python -m app.main

# Terminal 2 — React frontend (Vite dev server with HMR)
cd app/frontend
npm run dev
```

The Vite dev server proxies `/api/*` to `http://localhost:7433`.

#### Build the frontend

```bash
cd app/frontend
npm run build   # outputs to app/frontend/dist/
```

Or use the Makefile shortcut from the project root:

```bash
make build
```

#### Build the Windows .exe

Requires a Windows machine (or GitHub Actions Windows runner):

```bash
uv run pyinstaller app.spec
```

The spec file bundles the React `dist/`, tray icon assets, and all Python dependencies into a single `AlterxyGitCompanion.exe`.

---

### Releasing

Releases are built automatically by GitHub Actions on every `v*` tag push.

```bash
git tag v0.2.0
git push origin v0.2.0
```

The tag can be on any branch — the workflow reads whatever commit the tag points to. The built `.exe` is uploaded to GitHub Releases automatically.

---

### API Reference (Git Companion)

All endpoints are served on `http://localhost:<port>` (default 7433).

#### Projects

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/projects` | List all registered projects |
| `POST` | `/api/projects` | Register a new project folder |
| `DELETE` | `/api/projects/{project_id}` | Remove a project |
| `GET` | `/api/projects/check?path=...` | Pre-flight: check if folder is a git repo |

#### Save / Version control

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/save/commit` | Stage selected files and commit |
| `POST` | `/api/save/undo` | Undo last commit (soft reset) |
| `POST` | `/api/save/discard` | Discard changes to selected files |

#### History

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/history/{project_id}` | List commits for a project |
| `GET` | `/api/history/{project_id}/diff` | ACD HTML diff for a specific commit |

#### Remote (GitHub / GitLab)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/remote/github/device-code` | Start GitHub Device Flow — returns user_code + verification_uri |
| `POST` | `/api/remote/github/poll-token` | Poll for OAuth token after user authorises |
| `POST` | `/api/remote/github/logout` | Remove GitHub token from keyring |
| `GET` | `/api/remote/github/status` | Check if GitHub token is stored |
| `POST` | `/api/remote/gitlab/token` | Store GitLab PAT in keyring |
| `POST` | `/api/remote/gitlab/logout` | Remove GitLab token from keyring |
| `GET` | `/api/remote/gitlab/status` | Check if GitLab token is stored |
| `POST` | `/api/remote/push` | Push to remote (creates repo on first push) |
| `POST` | `/api/remote/pr` | Create a pull/merge request |

#### Branches

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/branch/{project_id}` | List branches |
| `POST` | `/api/branch/{project_id}/create` | Create experiment branch |
| `POST` | `/api/branch/{project_id}/checkout` | Checkout branch (blocked if dirty) |
| `DELETE` | `/api/branch/{project_id}/delete` | Delete branch (main/master protected) |
| `GET` | `/api/branch/{project_id}/merge-base` | SHA where branch diverged from main |

#### Watch / SSE

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/watch/events` | SSE stream — `badge_update` events for all projects |
| `GET` | `/api/watch/status` | Current change counts for all (or one) project |

#### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/settings` | Get current settings (launch_on_startup) |
| `POST` | `/api/settings` | Update settings |

#### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Server health check + app version |

---

## Development (ACD CLI)

### Setup

```bash
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx_diff

# Install all dependencies (runtime + dev)
uv sync --all-groups

# Install pre-commit hooks (ruff, mypy, trailing whitespace checks)
uv run pre-commit install
```

### Run tests

```bash
uv run pytest

# With verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_differ.py
```

### Type checking

```bash
uv run mypy src/
```

### Linting and formatting

```bash
# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Fix auto-fixable lint issues
uv run ruff check --fix src/ tests/
```

### Project structure

```
alteryx_diff/
├── src/
│   └── alteryx_diff/
│       ├── cli.py              # Typer CLI adapter over pipeline.run()
│       ├── parser.py           # lxml-based .yxmd loader
│       ├── exceptions.py       # ParseError hierarchy (MalformedXMLError, etc.)
│       ├── models/             # Frozen dataclasses (WorkflowDoc, DiffResult, ...)
│       ├── normalizer/         # C14N, GUID stripping, config hashing
│       ├── matcher/            # Two-pass ToolID + Hungarian matcher
│       ├── differ/             # DeepDiff-based node + edge differ
│       ├── pipeline/           # pipeline.run(DiffRequest) → DiffResponse facade
│       ├── renderers/          # HTMLRenderer, GraphRenderer, JSONRenderer
│       └── static/             # vis-network 9.1.4 UMD bundle (vendored)
├── app/
│   ├── main.py                 # Entry point: port probe, single-instance, tray, uvicorn
│   ├── server.py               # FastAPI app definition + SPA static file mount
│   ├── tray.py                 # System tray icon (pystray, three icon states)
│   ├── routers/
│   │   ├── projects.py         # /api/projects — register/list/delete folders
│   │   ├── save.py             # /api/save — commit / undo / discard
│   │   ├── history.py          # /api/history — list commits, ACD diff
│   │   ├── remote.py           # /api/remote — GitHub/GitLab auth and push
│   │   ├── branch.py           # /api/branch — branch CRUD
│   │   ├── watch.py            # /api/watch — SSE badge events
│   │   ├── settings.py         # /api/settings — autostart toggle
│   │   ├── folder_picker.py    # /api/folder-picker — native folder dialog
│   │   └── git_identity.py     # /api/git-identity — global git user config
│   └── services/
│       ├── git_ops.py          # subprocess wrappers for all git commands
│       ├── watcher_manager.py  # watchdog observer lifecycle + SSE fan-out
│       ├── watcher_utils.py    # network path detection
│       ├── config_store.py     # JSON config persistence (~/.alteryx_git_companion/)
│       ├── autostart.py        # Windows HKCU Run key registration
│       ├── remote_auth.py      # GitHub Device Flow + GitLab PAT + keyring storage
│       ├── github_api.py       # GitHub REST API (repo creation, user info, PR)
│       └── gitlab_api.py       # GitLab REST API (repo creation, user info, MR)
├── app/frontend/               # React + TypeScript + Vite SPA
├── assets/                     # Tray icon images (.ico)
├── tests/
│   ├── fixtures/               # Typed fixture libraries per phase (ToolID-allocated)
│   └── test_*.py               # 105 tests, 1 intentional xfail
├── app.spec                    # PyInstaller onefile spec
└── pyproject.toml
```

### Running as a module

```bash
uv run python -m alteryx_diff workflow_v1.yxmd workflow_v2.yxmd
```

---

## Known Limitations

- **GUID stripping** — the GUID field name registry (`GUID_VALUE_KEYS`) is not yet populated with confirmed field names from real `.yxmd` files. If Alteryx embeds session GUIDs inside tool configuration fields, those may appear as false-positive config_hash differences. The stripping mechanism is in place; the field names need real-file validation.
- **Browser-interactive behaviors** — the HTML graph's click-to-diff panel, show-only-changes toggle, and fit-to-screen animation are structurally correct but require manual browser testing to confirm rendering.
- **`.yxmc` / `.yxapp` formats** — not supported; only `.yxmd` and `.yxwz` files.
- **Macro recursion** — tools that reference macros are diffed as opaque nodes; internal macro changes are not surfaced.
- **macOS / Linux** — the Git Companion desktop app (tray, autostart, keyring) targets Windows. The ACD CLI runs on any platform.

---

## Roadmap

| Version | Scope |
|---|---|
| v1.0 ✅ | CLI diff, HTML report, interactive graph, JSON output, ALCOA+ governance |
| v1.1 | Resolve JSON schema divergence; populate GUID field registry from real files |
| v1.2 | Git Companion: diff viewer improvements, PR description templates |
| v2.0 | REST API (`POST /diff`), `.yxmc` / `.yxapp` support, macro recursion |

---

## Contributing

Contributions are welcome! Please open an issue to discuss what you'd like to change before submitting a pull request.

1. Fork the repo and create a branch from `main`
2. Install dev dependencies: `uv sync --all-groups`
3. Make your changes and add tests where applicable
4. Ensure all checks pass: `uv run pre-commit run --all-files` and `uv run pytest`
5. Open a pull request against `main`

Please keep PRs focused — one feature or fix per PR makes review faster.

---

## License

MIT © 2026 Laxmikant Mukkawar — see [LICENSE](LICENSE) for details.
