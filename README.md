# yxray

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Alteryx workflow inspector and diff tool. Reads `.yxmd` files as structured data and produces interactive HTML reports, diffs, and Python scaffolds.

---

## Commands

| Command | Alias | Description |
|---|---|---|
| `acd inspect <workflow.yxmd>` | `i` | Visualize a single workflow as an interactive HTML graph |
| `acd diff <a.yxmd> <b.yxmd>` | `d` | Compare two workflows and report field-level differences |
| `acd explain <workflow.yxmd>` | `ex` | Show each tool's Python/pandas equivalent in topological order |
| `acd scaffold <workflow.yxmd>` | `sc` | Generate a Python/pandas skeleton from a workflow |
| `acd cluster backup <clusters.json>` | — | Back up manual cluster JSON before editing or reuse |

---

## Usage

### inspect

Visualize a single workflow as a standalone HTML report:

```bash
acd inspect workflow.yxmd
# → output/workflow_report.html
```

Custom output path:

```bash
acd inspect workflow.yxmd -o report.html
```

Include `AlteryxGuiToolkit.*` UI nodes (filtered by default):

```bash
acd inspect workflow.yxmd --no-filter-ui-tools
```

Start from a previously exported manual cluster file:

```bash
acd inspect workflow.yxmd --cluster-file manual_clusters_workflow_20260705_153012.json
```

The report contains an interactive vis-network graph. Click any node to view its configuration and Python/pandas equivalent. Supports light/dark theme, zoom, pan, and fullscreen.

For **Select** and **AlteryxSelect** nodes, a **Copy Python** button appears in the panel action bar. Clicking it writes a ready-to-paste `SelectColumnEdit` snippet to the clipboard — the same format that `scaffold` emits.

#### Manual clusters

Use manual clusters when a large workflow needs human-defined grouping beyond the automatic same-type clusters and ToolContainer grouping.

In the generated HTML report:

1. Ctrl/Cmd-click two or more real tool nodes to multi-select them.
2. Click **Cluster**.
3. Enter a cluster name and save.
4. Use **Export Clusters** to download the manual cluster JSON.

Manual clusters are saved in browser `localStorage` while you work, keyed by a workflow fingerprint. They are not automatically written into the project directory. Exporting creates a JSON file through the browser download flow, usually in your Downloads folder.

You can later reuse that JSON with:

```bash
acd inspect workflow.yxmd --cluster-file manual_clusters_workflow_20260705_153012.json
```

The report also supports **Import Clusters** to load an exported JSON back into browser `localStorage`. Imported files must match the current workflow fingerprint. When a report is generated with `--cluster-file`, that embedded file seeds `localStorage` on first load; later browser edits and imports take precedence for the same workflow.

Current limitations:

- ToolContainer member nodes cannot be manual-clustered yet.
- Automatic cluster members cannot be added to manual clusters from the expanded live view yet.
- Rectangle/rubber-band drag selection is not implemented; use Ctrl/Cmd-click.

#### Manual cluster backups

Manual cluster JSON files can be backed up and restored from the CLI:

```bash
acd cluster backup manual_clusters_workflow.json
acd cluster list-backups manual_clusters_workflow.json
acd cluster restore manual_clusters_workflow.json
```

Backups are written next to the JSON file:

```text
manual_clusters_workflow.json
manual_clusters_workflow.backups/
  manual_clusters_workflow_20260705_153012.json
```

To restore a specific backup:

```bash
acd cluster restore manual_clusters_workflow.json manual_clusters_workflow.backups/manual_clusters_workflow_20260705_153012.json
```

---

### diff

Compare two workflows and generate a diff report:

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd
# → output/diff_report.html
```

Custom output path:

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd -o review.html
```

JSON output (for CI/CD):

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd --json
acd diff workflow_v1.yxmd workflow_v2.yxmd --json | jq '.modified[].tool_type'
```

Include canvas X/Y position changes (excluded by default):

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd --include-positions
```

Use Alteryx canvas coordinates for graph node positions:

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd --canvas-layout
```

Quiet mode (exit code only, for CI pipelines):

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd --quiet
echo $?   # 0 = no diff, 1 = diff found, 2 = error
```

---

### explain

Show each tool's nearest Python/pandas equivalent in topological order:

```bash
acd explain workflow.yxmd
```

JSON output:

```bash
acd explain workflow.yxmd --json
acd explain workflow.yxmd --json | jq '.[].python_hint'
```

Unsupported tools are flagged with a `# TODO` comment.

The `.md` report follows each ToolID's Python snippet with the original Alteryx `<Node>…</Node>` XML, so generated code and its source configuration can be compared per tool. The inspect report's right pane shows the same XML as a **source (Node XML)** section at the bottom.

Also writes `output/pyproject.toml` — a `[project]` scaffold with detected dependencies (`pandas`, `openpyxl` when Excel I/O is present) and a `[project.scripts]` entry keyed by the workflow filename.

Use `--output`/`-o` to write the `.md`/`.py`/`pyproject.toml` trio into a different directory instead of `output/` (created if missing):

```bash
acd explain workflow.yxmd -o build/
```

---

### scaffold

Generate a Python/pandas skeleton from a workflow:

```bash
acd scaffold workflow.yxmd
# → prints scaffold to stdout
```

Write to a file:

```bash
acd scaffold workflow.yxmd -o workflow.py
```

The generated file is structured as a runnable Python module:

- **Preamble**: imports and `ENV = os.getenv("APP_ENV", "test")`. The `SelectColumnEdit` / `apply_select_edits` helper definitions are **not** embedded — Select blocks carry a NOTE comment pointing to the reference implementation in `scripts/apply_select_edits.py`, which you copy into your project
- **Paths block**: `INPUTS` / `OUTPUTS` dicts gated by `ENV`. `test` mode resolves paths relative to `BASE_DIR`; `prod` mode uses the original absolute paths from the workflow
- **`main()` body**: one annotated code block per tool in topological order — supported tools get semi-concrete pandas code, unsupported tools get a `# TODO` comment
- **Entry point**: `if __name__ == "__main__": logging.basicConfig(...); main()`

---

## Exit Codes (diff)

| Code | Meaning |
|---|---|
| `0` | No differences found |
| `1` | Differences detected |
| `2` | Error — missing file, malformed XML, unreadable input |

---

## How It Works

`.yxmd` files are XML. yxray parses them as structured data:

```
.yxmd
  ↓
Parser (lxml)
  ↓
WorkflowDoc
  nodes: (tool_id, tool_type, config, x, y)
  connections: (src_tool, dst_tool)
  ↓
inspect  → Summarizer → SingleGraphRenderer → standalone HTML
diff     → Normalizer → Matcher → Differ → HTMLRenderer / JSONRenderer
explain  → Explain engine → plain text / JSON
scaffold → Scaffold generator → .py skeleton
```

**Normalization** strips Alteryx XML noise (attribute reordering, GUIDs, timestamps, TempFile paths) before comparing, eliminating false positives.

**Matching** uses exact ToolID lookup first, with a Hungarian algorithm fallback for workflows where Alteryx regenerated all ToolIDs on save.

**Explain** maps each tool type to its nearest pandas/Python equivalent and embeds the hint directly into the inspect HTML node panel.

**Scaffold** generates executable Python code in topological order. Supported tools produce real (if partial) pandas code; unsupported tools get a `# TODO` placeholder.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# Enable the pre-commit hook (runs ruff on every commit)
pre-commit install

# Tests
python -m pytest

# Type checking
python -m mypy src/yxray

# Lint / format
python -m ruff check .
python -m ruff format src tests
```

CI runs the same lint, type-check, and test suite on Python 3.11, 3.12, and
3.13.

> **Note**: The git history was rewritten on 2026-07-01. If an old clone's
> `main` shares no common ancestor with `origin/main`, that is expected —
> see [Docs/history-rewrite-2026-07-01.md](Docs/history-rewrite-2026-07-01.md).

---

## Project Structure

```
yxray/
├── src/
│   └── yxray/
│       ├── cli.py              # Typer CLI (acd inspect / diff / explain / scaffold)
│       ├── parser.py           # lxml-based .yxmd loader
│       ├── exceptions.py       # ParseError hierarchy
│       ├── config_utils.py     # XML config helpers (as_list, get_text, ...)
│       ├── topology.py         # Graph helpers (topo_order, compute_node_layer)
│       ├── summarizer.py       # Rule-based tool descriptions + key insights
│       ├── explain.py          # Alteryx → Python/pandas hint engine
│       ├── manual_clusters.py  # Manual cluster JSON validation and backups
│       ├── scaffold.py         # Python/pandas skeleton generator
│       ├── models/             # Frozen dataclasses (WorkflowDoc, DiffResult, ...)
│       ├── normalizer/         # C14N, GUID stripping, config hashing
│       ├── matcher/            # ToolID + Hungarian matcher
│       ├── differ/             # DeepDiff-based node + edge differ
│       ├── pipeline/           # pipeline.run() facade
│       ├── renderers/          # SingleGraphRenderer, DiffGraphRenderer, HTMLRenderer, JSONRenderer
│       └── static/             # vis-network UMD bundle (vendored, zero CDN)
└── tests/
```

---

## License

MIT © 2026 azu-azu — see [LICENSE](LICENSE) for details.
