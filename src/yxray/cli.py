from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
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


def _resolve_output(path: pathlib.Path | None, default_name: str) -> pathlib.Path:
    out = path if path is not None else pathlib.Path("output") / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _diff_impl(  # noqa: B008
    workflow_a: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help="Baseline .yxmd or .yxwz file (quote paths that contain spaces)"
    ),
    workflow_b: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help="Changed .yxmd or .yxwz file (quote paths that contain spaces)"
    ),
    output: pathlib.Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        "-o",
        help="Output path for the HTML report (default: output/diff_report.html; ignored when --json is set)",
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
    """Compare two Alteryx .yxmd or .yxwz workflow/app files and report differences.

    Paths that contain spaces must be quoted in the shell, e.g.:

      acd diff "My Workflow A.yxmd" "My Workflow B.yxmd"
    """
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
    workflow: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help=".yxmd or .yxwz workflow file to inspect"
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

    Produces a standalone vis-network graph showing all tools and connections.
    Click any node to view its configuration. No diff — single-workflow view only.
    """
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


def _explain_impl(  # noqa: B008
    workflow: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help=".yxmd or .yxwz workflow file"
    ),
    json_output: bool = typer.Option(  # noqa: B008
        False,
        "--json",
        help="Write JSON to stdout instead of plain text",
    ),
) -> None:
    """Show each tool's Python/pandas equivalent in topological order.

    Outputs a plain-text report (or JSON with --json) mapping every
    Alteryx tool to its nearest pandas equivalent.  Unsupported tools
    are flagged with a TODO comment.

      acd explain workflow.yxmd
      acd explain workflow.yxmd --json
    """
    from yxray.explain import explain

    try:
        doc = parse_one(workflow)
    except MalformedXMLError as e:
        typer.echo(f"Error: Invalid XML in {e.filepath}: {e.message}", err=True)
        raise typer.Exit(code=2) from None
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        raise typer.Exit(code=2) from None

    steps = explain(doc)

    if json_output:
        typer.echo(json.dumps([s.to_dict() for s in steps], indent=2, ensure_ascii=False))
        return

    for step in steps:
        tag = " [unsupported]" if not step.supported else ""
        typer.echo(f"ToolID {step.tool_id}: {step.short_type}{tag}")
        if step.description:
            typer.echo(f"  description: {step.description}")
        typer.echo(f"  python_hint: {step.python_hint}")
        typer.echo("")


app.command("explain")(_explain_impl)
app.command("ex", hidden=True)(_explain_impl)


def _scaffold_impl(  # noqa: B008
    workflow: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help=".yxmd or .yxwz workflow file"
    ),
    output: pathlib.Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        "-o",
        help="Write Python scaffold to file instead of stdout",
    ),
) -> None:
    """Generate a Python/pandas scaffold from an Alteryx workflow.

    Produces a .py skeleton with one code block per tool in topological
    order. Supported tools get semi-concrete pandas code; unsupported
    tools get a TODO comment.

      acd scaffold workflow.yxmd
      acd scaffold workflow.yxmd -o workflow.py
    """
    from yxray.scaffold import scaffold

    try:
        doc = parse_one(workflow)
    except MalformedXMLError as e:
        typer.echo(f"Error: Invalid XML in {e.filepath}: {e.message}", err=True)
        raise typer.Exit(code=2) from None
    except ParseError as e:
        typer.echo(f"Error: {e.message}", err=True)
        raise typer.Exit(code=2) from None

    code = scaffold(doc)

    if output:
        output.write_text(code, encoding="utf-8")
        typer.echo(f"Scaffold written to {output}", err=True)
    else:
        typer.echo(code)


app.command("scaffold")(_scaffold_impl)
app.command("sc", hidden=True)(_scaffold_impl)


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
