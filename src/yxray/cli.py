from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import webbrowser
from typing import Any

import typer
from rich.console import Console

from yxray.exceptions import MalformedXMLError, ParseError
from yxray.models import DiffResult
from yxray.parser import parse_one
from yxray.pipeline import DiffRequest, run
from yxray.renderers import (
    DiffGraphRenderer,
    HTMLRenderer,
    SingleGraphRenderer,
)
from yxray.summarizer import extract_key_insights, summarize

app = typer.Typer(no_args_is_help=True)
# Spinner + summary go to stderr so stdout stays clean for --json
_err_console = Console(stderr=True)

_WORKFLOW_EXTS = {".yxmd", ".yxmc"}
_DEFAULT_SINGLE_DIR = pathlib.Path("input")
_DEFAULT_DIFF_DIR = pathlib.Path("input_diff")


def _pick_single_default() -> pathlib.Path:
    folder = _DEFAULT_SINGLE_DIR
    if not folder.is_dir():
        typer.echo(
            f"Error: no file given and default folder not found: {folder}", err=True
        )
        raise typer.Exit(code=2)
    files = sorted(f for f in folder.iterdir() if f.suffix in _WORKFLOW_EXTS)
    if len(files) == 0:
        typer.echo(f"Error: no .yxmd/.yxmc file found in {folder}/", err=True)
        raise typer.Exit(code=2)
    if len(files) > 1:
        typer.echo(
            f"Error: multiple files in {folder}/ — specify one explicitly: "
            + ", ".join(f.name for f in files),
            err=True,
        )
        raise typer.Exit(code=2)
    return files[0]


def _pick_diff_default() -> tuple[pathlib.Path, pathlib.Path]:
    folder = _DEFAULT_DIFF_DIR
    if not folder.is_dir():
        typer.echo(
            f"Error: no files given and default folder not found: {folder}", err=True
        )
        raise typer.Exit(code=2)
    files = sorted(f for f in folder.iterdir() if f.suffix in _WORKFLOW_EXTS)
    if len(files) != 2:
        typer.echo(
            f"Error: {folder}/ must contain exactly 2 .yxmd/.yxmc files, "
            f"found {len(files)}",
            err=True,
        )
        raise typer.Exit(code=2)
    return files[0], files[1]


def _resolve_output(path: pathlib.Path | None, default_name: str) -> pathlib.Path:
    out = path if path is not None else pathlib.Path("output") / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _diff_impl(  # noqa: B008
    workflow_a: pathlib.Path | None = typer.Argument(  # noqa: B008
        None, help="Baseline .yxmd/.yxmc file (omit to use input_diff/ folder)"
    ),
    workflow_b: pathlib.Path | None = typer.Argument(  # noqa: B008
        None, help="Changed .yxmd/.yxmc file (omit to use input_diff/ folder)"
    ),
    output: pathlib.Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        "-o",
        help=(
            "Output path for the HTML report "
            "(default: output/diff_report.html; ignored when --json is set)"
        ),
    ),
    include_positions: bool = typer.Option(  # noqa: B008
        False,
        "--include-positions",
        help=(
            "Include canvas X/Y position changes in diff detection"
            " (excluded by default to avoid layout noise)"
        ),
    ),
    canvas_layout: bool = typer.Option(  # noqa: B008
        False,
        "--canvas-layout",
        help=(
            "Use Alteryx canvas X/Y coordinates for graph node positions"
            " (default: hierarchical auto-layout following data flow)"
        ),
    ),
    filter_ui_tools: bool = typer.Option(  # noqa: B008
        True,
        "--no-filter-ui-tools",
        help=(
            "Include AlteryxGuiToolkit.* app interface nodes"
            " (Tab, TextBox, Action, etc.) filtered by default"
            " when comparing .yxwz apps against .yxmd workflows"
        ),
    ),
    quiet: bool = typer.Option(  # noqa: B008
        False,
        "--quiet",
        "-q",
        help="Suppress all terminal output; exit code only (for CI pipelines)",
    ),
    json_output: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Write JSON diff to stdout instead of HTML file (pipe-friendly)",
    ),
) -> None:
    """Compare two Alteryx .yxmd or .yxmc workflow files and report differences.

    Omit both paths to use the two files in input_diff/.
    Paths that contain spaces must be quoted in the shell, e.g.:

      acd diff "My Workflow A.yxmd" "My Workflow B.yxmd"
    """
    if workflow_a is None and workflow_b is None:
        workflow_a, workflow_b = _pick_diff_default()
    elif workflow_a is None or workflow_b is None:
        typer.echo("Error: provide both workflow files or neither", err=True)
        raise typer.Exit(code=2)

    # Compute governance metadata upfront — single timestamp for audit consistency
    # Guard here: missing file raises FileNotFoundError before pipeline even starts
    try:
        hash_a = _file_sha256(workflow_a)
        hash_b = _file_sha256(workflow_b)
    except OSError as e:
        typer.echo(f"Error: {e.strerror}: {e.filename}", err=True)
        raise typer.Exit(code=2) from None
    metadata = _build_governance_metadata(workflow_a, workflow_b, hash_a, hash_b)

    # Run pipeline (spinner goes to stderr; stdout stays clean for --json)
    request = DiffRequest(
        path_a=workflow_a,
        path_b=workflow_b,
        filter_ui_tools=filter_ui_tools,
    )
    try:
        if quiet or json_output:
            response = run(request, include_positions=include_positions)
        else:
            with _err_console.status("Running diff...", spinner="dots"):
                response = run(request, include_positions=include_positions)
    except MalformedXMLError as e:
        typer.echo(f"Error: Invalid XML in {e.filepath}: {e.message}", err=True)
        raise typer.Exit(code=2) from None
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        raise typer.Exit(code=2) from None

    result = response.result

    if result.is_empty:
        if json_output:
            # Emit empty JSON for consistent downstream tool behaviour
            json_str = _cli_json_output(result, metadata)
            typer.echo(json_str)
        if not quiet:
            typer.echo("No differences found", err=True)
        raise typer.Exit(code=0)

    # Render output
    if json_output:
        json_str = _cli_json_output(result, metadata)
        typer.echo(json_str)  # stdout — pipe-friendly
    else:
        file_a_str = str(workflow_a.resolve())
        file_b_str = str(workflow_b.resolve())
        all_connections = response.doc_a.connections + response.doc_b.connections
        graph_html = DiffGraphRenderer().render(
            result,
            all_connections=all_connections,
            nodes_old=response.doc_a.nodes,
            nodes_new=response.doc_b.nodes,
            canvas_layout=canvas_layout,
        )
        added_ids = frozenset(int(n.tool_id) for n in result.added_nodes)
        modified_ids = frozenset(int(nd.tool_id) for nd in result.modified_nodes)
        steps = summarize(
            response.doc_b, added_ids=added_ids, modified_ids=modified_ids
        )
        insights = extract_key_insights(response.doc_b)
        html = HTMLRenderer().render(
            result,
            file_a=file_a_str,
            file_b=file_b_str,
            graph_html=graph_html,
            metadata=metadata,
            workflow_steps=steps,
            key_insights=insights,
        )
        out_path = _resolve_output(output, "diff_report.html")
        out_path.write_text(html, encoding="utf-8")
        webbrowser.open(out_path.resolve().as_uri())
        if not quiet:
            change_count = (
                len(result.added_nodes)
                + len(result.removed_nodes)
                + len(result.modified_nodes)
                + len(result.edge_diffs)
            )
            typer.echo(
                f"Report written to {out_path} ({change_count} changes detected)",
                err=True,
            )

    raise typer.Exit(code=1)


app.command("diff")(_diff_impl)
app.command("d", hidden=True)(_diff_impl)


def _inspect_impl(  # noqa: B008
    workflow: pathlib.Path | None = typer.Argument(  # noqa: B008
        None, help=".yxmd/.yxmc workflow file to inspect (omit to use input/ folder)"
    ),
    output: pathlib.Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        "-o",
        help="Output path for the HTML report (default: output/<workflow>_report.html)",
    ),
    filter_ui_tools: bool = typer.Option(  # noqa: B008
        True,
        "--no-filter-ui-tools",
        help=(
            "Include AlteryxGuiToolkit.* app interface nodes"
            " (Tab, TextBox, Action, etc.) filtered by default"
        ),
    ),
) -> None:
    """Inspect a single Alteryx workflow and generate an interactive HTML report.

    Omit the path to use the single file in input/.
    Produces a standalone vis-network graph showing all tools and connections.
    Click any node to view its configuration. No diff — single-workflow view only.
    """
    if workflow is None:
        workflow = _pick_single_default()
    try:
        with _err_console.status("Parsing workflow...", spinner="dots"):
            doc = parse_one(workflow, filter_ui_tools=filter_ui_tools)
    except MalformedXMLError as e:
        typer.echo(f"Error: Invalid XML in {e.filepath}: {e.message}", err=True)
        raise typer.Exit(code=2) from None
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        raise typer.Exit(code=2) from None

    out_path = _resolve_output(output, workflow.stem + "_report.html")
    steps = summarize(doc)
    insights = extract_key_insights(doc)
    html = SingleGraphRenderer().render(
        doc, workflow_steps=steps, key_insights=insights
    )
    out_path.write_text(html, encoding="utf-8")
    typer.echo(
        f"Report written to {out_path}"
        f" ({len(doc.nodes)} nodes, {len(doc.connections)} connections)",
        err=True,
    )
    webbrowser.open(out_path.resolve().as_uri())


app.command("inspect")(_inspect_impl)
app.command("i", hidden=True)(_inspect_impl)


def _collect_deps(code: str) -> list[str]:
    deps = ["pandas"]
    if "read_excel" in code or "to_excel" in code:
        deps.append("openpyxl")
    return deps


def _build_pyproject(workflow: pathlib.Path, code: str) -> str:
    deps = _collect_deps(code)
    dep_lines = "\n".join(f'    "{dep}",' for dep in deps)
    return (
        "[project]\n"
        'name = "<your-project-name>"\n'
        'version = "0.1.0"\n'
        f'description = "Generated from {workflow.name}"\n'
        'requires-python = ">=3.11"\n'
        "dependencies = [\n"
        f"{dep_lines}\n"
        "]\n"
        "\n"
        "[project.scripts]\n"
        f'"{workflow.stem}" = "<package>.main:main"\n'
        "\n"
        "[tool.hatch.build.targets.wheel]\n"
        'packages = ["src/"]\n'
    )


def _extract_template_context(code: str) -> dict[str, Any]:
    """Extract paths and column names per category, with source attribution."""
    sections = re.split(r"# [─]{10,}\n", code)

    inputs: list[tuple[str, str]] = []
    outputs: list[tuple[str, str]] = []
    select_cols: list[tuple[list[str], str]] = []
    group_keys: list[tuple[list[str], str]] = []
    join_keys: list[tuple[list[str], str]] = []
    derived_cols: list[tuple[list[str], str]] = []
    input_key_counts: dict[str, int] = {}
    output_key_counts: dict[str, int] = {}

    for section in sections:
        m = re.search(r"# ToolID (\d+): (\w+)", section)
        if not m:
            continue
        source = f"Tool #{m.group(1)} / {m.group(2)}"

        for path in re.findall(r'pd\.read_(?:csv|excel)\("([^"]+)"\)', section):
            stem = pathlib.Path(path).stem
            n = input_key_counts.get(stem, 0)
            input_key_counts[stem] = n + 1
            inputs.append((stem if n == 0 else f"{stem}_{n + 1}", path))

        for path in re.findall(r'\.to_(?:csv|excel)\("([^"]+)"', section):
            stem = pathlib.Path(path).stem
            n = output_key_counts.get(stem, 0)
            output_key_counts[stem] = n + 1
            outputs.append((stem if n == 0 else f"{stem}_{n + 1}", path))

        blocks = re.findall(r"\[\[([^\]]+)\]", section)
        cols = [c for b in blocks for c in re.findall(r'"([^"]+)"', b)]
        if cols:
            select_cols.append((cols, source))

        blocks = re.findall(r"\.groupby\(\[([^\]]+)\]\)", section)
        cols = [c for b in blocks for c in re.findall(r'"([^"]+)"', b)]
        if cols:
            group_keys.append((cols, source))

        blocks = re.findall(r"(?:on|left_on|right_on)=\[([^\]]+)\]", section)
        cols = list(dict.fromkeys(c for b in blocks for c in re.findall(r'"([^"]+)"', b)))
        if cols:
            join_keys.append((cols, source))

        cols = re.findall(r"\.assign\((\w+)=", section)
        if cols:
            derived_cols.append((cols, source))

    return {
        "inputs": inputs,
        "outputs": outputs,
        "select_cols": select_cols,
        "group_keys": group_keys,
        "join_keys": join_keys,
        "derived_cols": derived_cols,
    }


def _build_py_lines(workflow: pathlib.Path, code: str) -> list[str]:
    ctx = _extract_template_context(code)
    inputs: list[tuple[str, str]] = ctx["inputs"]
    outputs: list[tuple[str, str]] = ctx["outputs"]

    def _flat_sorted(groups: list[tuple[list[str], str]]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for cols, _ in groups:
            for c in cols:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return sorted(out)

    def _col_block(var: str, groups: list[tuple[list[str], str]]) -> list[str]:
        if not groups:
            return [f"{var} = []"]
        block: list[str] = [f"# Source: {src}" for _, src in groups]
        block.append(f"{var} = [")
        for col in _flat_sorted(groups):
            block.append(f'    "{col}",')
        block.append("]")
        return block

    lines: list[str] = [
        f'"""{workflow.stem}.py — generated from {workflow.name}',
        "",
        "Edit main() to implement your logic.",
        '"""',
        "from __future__ import annotations",
        "",
        "from pathlib import Path",
        "",
        "import pandas as pd",
        "",
    ]

    if inputs or outputs:
        lines.append("# ── Paths ─────────────────────────────────────────────────────────────")
        if inputs:
            lines.append("INPUTS = {")
            for key, path in inputs:
                lines.append(f'    "{key}": Path("{path}"),')
            lines.append("}")
        if outputs:
            lines.append("OUTPUTS = {")
            for key, path in outputs:
                lines.append(f'    "{key}": Path("{path}"),')
            lines.append("}")
        lines.append("")

    lines.append("# ── Detected columns ──────────────────────────────────────────────────")
    for var, groups in (
        ("SELECT_COLUMNS", ctx["select_cols"]),
        ("GROUP_KEYS", ctx["group_keys"]),
        ("JOIN_KEYS", ctx["join_keys"]),
        ("DERIVED_COLUMNS", ctx["derived_cols"]),
    ):
        lines += _col_block(var, groups)
        lines.append("")

    first_in = f'INPUTS["{inputs[0][0]}"]' if inputs else "...  # TODO: set input"
    first_out = f'OUTPUTS["{outputs[0][0]}"]' if outputs else "...  # TODO: set output"
    lines += [
        "",
        "def main() -> None:",
        f"    df = pd.read_csv({first_in})",
        "",
        "    # TODO: Apply filters",
        "",
        "    # TODO: Create derived columns",
        "    # df = df.assign(...)",
        "",
        "    # TODO: Aggregate or join data",
        "",
        "    # TODO: Select output columns",
        "    # result = df[SELECT_COLUMNS]",
        "",
        "    # TODO: Write output",
        f"    # result.to_csv({first_out}, index=False)",
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    return lines


def _write_explain_outputs(
    workflow: pathlib.Path,
    steps: list[Any],
    code: str,
) -> None:
    out_dir = pathlib.Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{workflow.stem}.md"
    py_path = out_dir / f"{workflow.stem}.py"
    pyproject_path = out_dir / "pyproject.toml"

    md_lines: list[str] = [
        f"# {workflow.name}",
        "",
        "## Tool Summary",
        "",
        "| ToolID | Type | Category | Description | Python Hint | Supported |",
        "|--------|------|----------|-------------|-------------|-----------|",
    ]
    for step in steps:
        desc = (step.description or "").replace("|", "\\|")
        hint = step.python_hint.replace("|", "\\|")
        supported = "yes" if step.supported else "no"
        md_lines.append(
            f"| {step.tool_id} | {step.short_type} | {step.category}"
            f" | {desc} | `{hint}` | {supported} |"
        )
    md_lines += [
        "",
        "## Python Scaffold",
        "",
        "```python",
        code.rstrip("\n"),
        "```",
        "",
    ]

    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    py_path.write_text("\n".join(_build_py_lines(workflow, code)), encoding="utf-8")
    pyproject_path.write_text(_build_pyproject(workflow, code), encoding="utf-8")
    typer.echo(f"Report     → {out_path}", err=True)
    typer.echo(f"Template   → {py_path}", err=True)
    typer.echo(f"Pyproject  → {pyproject_path}", err=True)


def _explain_impl(  # noqa: B008
    workflow: pathlib.Path | None = typer.Argument(  # noqa: B008
        None, help=".yxmd/.yxmc workflow file (omit to use input/ folder)"
    ),
) -> None:
    """Explain each tool and generate a Python scaffold, written to output/.

    Omit the path to use the single file in input/.
    Creates three files in output/:
      <workflow_stem>.md    — tool summary table + Python scaffold code block
      <workflow_stem>.py    — minimal Python template (main() stub)
      pyproject.toml        — project scaffold with detected dependencies
    Unsupported tools are flagged TODO.

      acd explain workflow.yxmd
      acd ex workflow.yxmd
    """
    from yxray.explain import explain
    from yxray.scaffold import scaffold

    if workflow is None:
        workflow = _pick_single_default()
    try:
        doc = parse_one(workflow)
    except MalformedXMLError as e:
        typer.echo(f"Error: Invalid XML in {e.filepath}: {e.message}", err=True)
        raise typer.Exit(code=2) from None
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        raise typer.Exit(code=2) from None

    _write_explain_outputs(workflow, explain(doc), scaffold(doc))


app.command("explain")(_explain_impl)
app.command("ex", hidden=True)(_explain_impl)


def _file_sha256(path: pathlib.Path) -> str:
    """Return 64-char SHA-256 hex digest. Uses hashlib.file_digest (Python 3.11+)."""
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return digest.hexdigest()


def _build_governance_metadata(
    path_a: pathlib.Path,
    path_b: pathlib.Path,
    hash_a: str,
    hash_b: str,
) -> dict[str, Any]:
    return {
        "file_a": str(path_a.resolve()),
        "file_b": str(path_b.resolve()),
        "sha256_a": hash_a,
        "sha256_b": hash_b,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


def _cli_json_output(result: DiffResult, metadata: dict[str, Any]) -> str:
    """Produce CLI --json schema: {added, removed, modified, metadata}.

    Distinct from JSONRenderer output ({summary, tools, connections}).
    Kept separate to avoid breaking existing JSONRenderer tests (5 passing).
    """
    payload: dict[str, Any] = {
        "added": [
            {
                "tool_id": int(n.tool_id),
                "tool_type": n.tool_type,
                "config": dict(n.config),
            }
            for n in result.added_nodes
        ],
        "removed": [
            {
                "tool_id": int(n.tool_id),
                "tool_type": n.tool_type,
                "config": dict(n.config),
            }
            for n in result.removed_nodes
        ],
        "modified": [
            {
                "tool_id": int(nd.tool_id),
                "tool_type": nd.old_node.tool_type,
                "field_diffs": [
                    {"field": k, "before": v[0], "after": v[1]}
                    for k, v in nd.field_diffs.items()
                ],
            }
            for nd in result.modified_nodes
        ],
        "metadata": metadata,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
