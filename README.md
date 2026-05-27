# yxray

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Alteryx workflow inspector and diff tool. Reads `.yxmd` files as structured data and produces interactive HTML reports.

---

## Commands

| Command | Description |
|---|---|
| `acd inspect <workflow.yxmd>` | Visualize a single workflow as an interactive HTML graph |
| `acd diff <a.yxmd> <b.yxmd>` | Compare two workflows and report field-level differences |

---

## Usage

### inspect

Visualize a single workflow as a standalone HTML report:

```bash
acd inspect workflow.yxmd
# → workflow_report.html
```

Custom output path:

```bash
acd inspect workflow.yxmd -o report.html
```

Include `AlteryxGuiToolkit.*` UI nodes (filtered by default):

```bash
acd inspect workflow.yxmd --no-filter-ui-tools
```

The report contains an interactive vis-network graph. Click any node to view its configuration. Supports light/dark theme, zoom, pan, and fullscreen.

---

### diff

Compare two workflows and generate a diff report:

```bash
acd diff workflow_v1.yxmd workflow_v2.yxmd
# → diff_report.html
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
inspect → SingleGraphRenderer → standalone HTML
diff    → Normalizer → Matcher → Differ → HTML / JSON
```

**Normalization** strips Alteryx XML noise (attribute reordering, GUIDs, timestamps, TempFile paths) before comparing, eliminating false positives.

**Matching** uses exact ToolID lookup first, with a Hungarian algorithm fallback for workflows where Alteryx regenerated all ToolIDs on save.

---

## Development

```bash
pip install -e ".[dev]"

# Tests
pytest

# Type checking
mypy src/

# Lint / format
ruff check src/ tests/
ruff format src/ tests/
```

---

## Project Structure

```
yxray/
├── src/
│   └── alteryx_git_companion/
│       ├── cli.py              # Typer CLI (acd inspect / acd diff)
│       ├── parser.py           # lxml-based .yxmd loader
│       ├── exceptions.py       # ParseError hierarchy
│       ├── models/             # Frozen dataclasses (WorkflowDoc, DiffResult, ...)
│       ├── normalizer/         # C14N, GUID stripping, config hashing
│       ├── matcher/            # ToolID + Hungarian matcher
│       ├── differ/             # DeepDiff-based node + edge differ
│       ├── pipeline/           # pipeline.run() facade
│       ├── renderers/          # HTMLRenderer, GraphRenderer, JSONRenderer, SingleGraphRenderer
│       └── static/             # vis-network UMD bundle (vendored, zero CDN)
└── tests/
```

---

## License

MIT © 2026 Laxmikant Mukkawar, azu-azu — see [LICENSE](LICENSE) for details.
