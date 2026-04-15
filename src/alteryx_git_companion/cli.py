from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
from typing import Any

import typer
from rich.console import Console

from alteryx_git_companion.exceptions import MalformedXMLError, ParseError
from alteryx_git_companion.pipeline import DiffRequest, run
from alteryx_git_companion.renderers import GraphRenderer, HTMLRenderer

app = typer.Typer(no_args_is_help=True)
# Spinner + summary go to stderr so stdout stays clean for --json
_err_console = Console(stderr=True)


@app.command()
def diff(  # noqa: B008
    workflow_a: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help="Baseline .yxmd or .yxwz file (quote paths that contain spaces)"
    ),
    workflow_b: pathlib.Path = typer.Argument(  # noqa: B008
        ..., help="Changed .yxmd or .yxwz file (quote paths that contain spaces)"
    ),
    output: pathlib.Path = typer.Option(  # noqa: B008
        pathlib.Path("diff_report.html"),
        "--output",
        "-o",
        help="Output path for the HTML report (ignored when --json is set)",
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

      alteryx-diff "My Workflow A.yxmd" "My Workflow B.yxmd"
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
    try:
        if quiet or json_output:
            response = run(
                DiffRequest(
                    path_a=workflow_a,
                    path_b=workflow_b,
                    filter_ui_tools=filter_ui_tools,
                ),
                include_positions=include_positions,
            )
        else:
            with _err_console.status("Running diff...", spinner="dots"):
                response = run(
                    DiffRequest(
                        path_a=workflow_a,
                        path_b=workflow_b,
                        filter_ui_tools=filter_ui_tools,
                    ),
                    include_positions=include_positions,
                )
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
        graph_renderer = GraphRenderer()
        graph_html = graph_renderer.render(
            result,
            all_connections=(response.doc_a.connections + response.doc_b.connections),
            nodes_old=response.doc_a.nodes,
            nodes_new=response.doc_b.nodes,
            canvas_layout=canvas_layout,
        )
        html = HTMLRenderer().render(
            result,
            file_a=str(workflow_a.resolve()),
            file_b=str(workflow_b.resolve()),
            graph_html=graph_html,
            metadata=metadata,  # CLI-04: governance footer in HTML report
        )
        output.write_text(html, encoding="utf-8")
        if not quiet:
            change_count = (
                len(result.added_nodes)
                + len(result.removed_nodes)
                + len(result.modified_nodes)
                + len(result.edge_diffs)
            )
            typer.echo(
                f"Report written to {output} ({change_count} changes detected)",
                err=True,
            )

    raise typer.Exit(code=1)


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


def _cli_json_output(result: Any, metadata: dict[str, Any]) -> str:
    """Produce CLI --json schema: {added, removed, modified, metadata}.

    Distinct from JSONRenderer output ({summary, tools, connections}).
    Kept separate to avoid breaking existing JSONRenderer tests (5 passing).
    """
    # local import: avoids circular at module level
    from alteryx_git_companion.models import (
        DiffResult,
    )

    r: DiffResult = result
    payload: dict[str, Any] = {
        "added": [
            {
                "tool_id": int(n.tool_id),
                "tool_type": n.tool_type,
                "config": dict(n.config),
            }
            for n in r.added_nodes
        ],
        "removed": [
            {
                "tool_id": int(n.tool_id),
                "tool_type": n.tool_type,
                "config": dict(n.config),
            }
            for n in r.removed_nodes
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
            for nd in r.modified_nodes
        ],
        "metadata": metadata,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
