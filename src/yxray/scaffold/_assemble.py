"""Alteryx → Python scaffold generator.

scaffold(doc) returns a .py file string with one code block per tool,
in topological order. Supported tools get real (if partial) pandas code;
unsupported tools get a TODO comment.

Variable naming: each tool's output is named df<tool_id> (e.g. df34, df108),
matching the ToolID comment above each block so the mapping is unambiguous.
"""

from __future__ import annotations

import pathlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yxray.config_utils import (
    comment_safe,
    first_text,
)
from yxray.models.workflow import WorkflowDoc
from yxray.scaffold._aggregate import gen_summarize
from yxray.scaffold._combine import gen_appendfields, gen_join, gen_union
from yxray.scaffold._common import frame_name
from yxray.scaffold._filter import gen_filter
from yxray.scaffold._findreplace import gen_findreplace
from yxray.scaffold._io import (
    SHX_NOTE_LINES,
    SHX_RESTORE_LINE,
    SPATIAL_EXTS,
    gen_input,
    gen_output,
    is_shp,
    read_stmt,
    write_stmt,
)
from yxray.scaffold._select import gen_select
from yxray.scaffold._source import gen_browse, gen_text_input
from yxray.scaffold._spatial import gen_createpoints, gen_spatialmatch
from yxray.scaffold._transform import gen_formula, gen_sample, gen_sort, gen_unique
from yxray.tool_registry import (
    SCAFFOLD_APPENDFIELDS_SEGMENTS,
    SCAFFOLD_BROWSE_SEGMENTS,
    SCAFFOLD_CREATEPOINTS_SEGMENTS,
    SCAFFOLD_FILTER_SEGMENTS,
    SCAFFOLD_FINDREPLACE_SEGMENTS,
    SCAFFOLD_FORMULA_SEGMENTS,
    SCAFFOLD_INPUT_SEGMENTS,
    SCAFFOLD_JOIN_SEGMENTS,
    SCAFFOLD_OUTPUT_SEGMENTS,
    SCAFFOLD_SAMPLE_SEGMENTS,
    SCAFFOLD_SELECT_SEGMENTS,
    SCAFFOLD_SORT_SEGMENTS,
    SCAFFOLD_SPATIAL_SEGMENTS,
    SCAFFOLD_SPATIALMATCH_SEGMENTS,
    SCAFFOLD_SUMMARIZE_SEGMENTS,
    SCAFFOLD_TEXTINPUT_SEGMENTS,
    SCAFFOLD_UNION_SEGMENTS,
    SCAFFOLD_UNIQUE_SEGMENTS,
    tool_segment,
)
from yxray.topology import build_predecessor_map, topo_order

__all__ = [
    "ScaffoldBlock",
    "node_code_snippets",
    "scaffold",
    "scaffold_simple",
    "scaffold_simple_blocks",
]

# Emissions of alteryx_expr that need "import numpy as np" in the preamble.
_NUMPY_RE = re.compile(r"\bnp\.(where|select|nan)\b")


# ── Connection helpers ─────────────────────────────────────────────────────


def _build_anchor_map(doc: WorkflowDoc) -> dict[int, dict[str, int]]:
    """For each dst tool, map anchor name → src tool_id."""
    anchors: dict[int, dict[str, int]] = {}
    for c in doc.connections:
        dst = int(c.dst_tool)
        anchors.setdefault(dst, {})[c.dst_anchor] = int(c.src_tool)
    return anchors


def _assign_frame_names(
    order: list[int],
    node_map: dict[int, Any],
) -> dict[int, str]:
    """Name each tool's output frame df<tool_id> (e.g. df34, df108).

    One-to-one with ToolIDs so variable names are stable, unambiguous,
    and never collide between inputs and outputs of the same operation.
    """
    return {tool_id: f"df{tool_id}" for tool_id in order if tool_id in node_map}


# ── Generator registry ─────────────────────────────────────────────────────

_Generator = Callable[
    [int, str, dict[str, Any], list[int], dict[str, int], dict[int, str]], str
]

_GENERATORS: dict[str, _Generator] = {
    **dict.fromkeys(SCAFFOLD_BROWSE_SEGMENTS, gen_browse),
    **dict.fromkeys(SCAFFOLD_FILTER_SEGMENTS, gen_filter),
    **dict.fromkeys(SCAFFOLD_SELECT_SEGMENTS, gen_select),
    **dict.fromkeys(SCAFFOLD_FORMULA_SEGMENTS, gen_formula),
    **dict.fromkeys(SCAFFOLD_JOIN_SEGMENTS, gen_join),
    **dict.fromkeys(SCAFFOLD_UNION_SEGMENTS, gen_union),
    **dict.fromkeys(SCAFFOLD_SUMMARIZE_SEGMENTS, gen_summarize),
    **dict.fromkeys(SCAFFOLD_SORT_SEGMENTS, gen_sort),
    **dict.fromkeys(SCAFFOLD_SAMPLE_SEGMENTS, gen_sample),
    **dict.fromkeys(SCAFFOLD_UNIQUE_SEGMENTS, gen_unique),
    **dict.fromkeys(SCAFFOLD_TEXTINPUT_SEGMENTS, gen_text_input),
    **dict.fromkeys(SCAFFOLD_FINDREPLACE_SEGMENTS, gen_findreplace),
    **dict.fromkeys(SCAFFOLD_APPENDFIELDS_SEGMENTS, gen_appendfields),
    **dict.fromkeys(SCAFFOLD_CREATEPOINTS_SEGMENTS, gen_createpoints),
    **dict.fromkeys(SCAFFOLD_SPATIALMATCH_SEGMENTS, gen_spatialmatch),
}

# Segments whose scaffold snippet is self-contained enough to show as a
# single node's "python hint" (used by the inspect report's right pane).
# Excludes Input/Output (depend on file paths, which the panel already shows
# separately) and Text Input (would enumerate every data row — the panel
# shows the data).
_DETAIL_HINT_SEGMENTS = frozenset(_GENERATORS) - SCAFFOLD_TEXTINPUT_SEGMENTS


def node_code_snippets(doc: WorkflowDoc) -> dict[int, str]:
    """Per-node pandas code, identical to the .md Python Scaffold section.

    Only returns entries for tool_ids whose segment is in
    _DETAIL_HINT_SEGMENTS; callers should fall back to the generic
    python_hint for everything else.
    """
    node_map = {
        int(n.tool_id): n for n in doc.nodes if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    names = _assign_frame_names(topo_order(doc), node_map)

    snippets: dict[int, str] = {}
    for tool_id, node in node_map.items():
        segment = tool_segment(node.tool_type)
        if segment not in _DETAIL_HINT_SEGMENTS:
            continue
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})
        snippets[tool_id] = _GENERATORS[segment](
            tool_id, segment, node.config, preds, anchors, names
        )
    return snippets


# ── Scaffold section builders ──────────────────────────────────────────────


def _collect_metadata(
    node_map: dict[int, Any],
    order: list[int],
) -> tuple[dict[int, str], dict[int, str], bool]:
    """Pre-pass: collect input/output paths and which helper imports are needed."""
    input_paths: dict[int, str] = {}
    output_paths: dict[int, str] = {}
    has_spatial = False

    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        segment = tool_segment(node.tool_type)
        if segment in SCAFFOLD_INPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if path:
                input_paths[tool_id] = path
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if path:
                output_paths[tool_id] = path
        elif segment in SCAFFOLD_SPATIAL_SEGMENTS:
            has_spatial = True

    # Spatial file I/O emits gpd.read_file/to_file even without spatial tools.
    if not has_spatial:
        has_spatial = any(
            pathlib.Path(p).suffix.lower() in SPATIAL_EXTS
            for p in (*input_paths.values(), *output_paths.values())
        )

    return input_paths, output_paths, has_spatial


def _emit_preamble(
    source: str,
    has_spatial: bool,
    uses_numpy: bool,
    has_shp: bool,
) -> list[str]:
    lines: list[str] = [
        f'"""Scaffold generated by yxray from {source}"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    lines += [
        "import logging",
        "import os",
        "from pathlib import Path",
        "",
    ]
    if has_spatial:
        lines.append("import geopandas as gpd")
    if uses_numpy:
        lines.append("import numpy as np")
    lines += [
        "import pandas as pd",
        "",
        "logger = logging.getLogger(__name__)",
    ]
    if has_shp:
        lines += ["", SHX_RESTORE_LINE]
    return lines


def _emit_paths_block(
    input_paths: dict[int, str],
    output_paths: dict[int, str],
) -> list[str]:
    if not (input_paths or output_paths):
        return []

    lines: list[str] = [
        "",
        'ENV = os.getenv("APP_ENV", "test")',
        "",
        "# ── Paths ─────────────────────────────────────────────────────────────",
        "",
        'if ENV == "test":',
        "    BASE_DIR = Path(__file__).resolve().parents[2]",
    ]
    if input_paths:
        lines += ["", "    INPUTS = {"]
        for tid, path in input_paths.items():
            fname = pathlib.PureWindowsPath(path).name
            lines.append(f'        "input_{tid}": BASE_DIR / "input" / "{fname}",')
        lines.append("    }")
    if output_paths:
        lines += ["", "    OUTPUTS = {"]
        for tid, path in output_paths.items():
            fname = pathlib.PureWindowsPath(path).name
            lines.append(f'        "output_{tid}": BASE_DIR / "output" / "{fname}",')
        lines.append("    }")
    lines += ["", 'elif ENV == "prod":']
    if input_paths:
        lines.append("    INPUTS = {")
        for tid, path in input_paths.items():
            lines.append(f'        "input_{tid}": Path(r"{path}"),')
        lines.append("    }")
    if output_paths:
        if input_paths:
            lines.append("")
        lines.append("    OUTPUTS = {")
        for tid, path in output_paths.items():
            lines.append(f'        "output_{tid}": Path(r"{path}"),')
        lines.append("    }")
    lines += [
        "",
        "else:",
        '    raise ValueError(f"Unknown ENV: {ENV}")',
    ]
    return lines


def _tool_context(
    tool_id: int,
    node_map: dict[int, Any],
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
) -> tuple[Any, str, list[int], dict[str, int]] | None:
    """(node, segment, preds, anchors) for a tool, or None if it has no node.

    Shared by _emit_main_body() (.py) and scaffold_simple_blocks() (.md) so
    the per-tool lookup stays in one place even though the two callers emit
    different output shapes.
    """
    node = node_map.get(tool_id)
    if node is None:
        return None
    segment = tool_segment(node.tool_type)
    return node, segment, pred_map.get(tool_id, []), anchor_map.get(tool_id, {})


def _header_comment_lines(
    tool_id: int,
    segment: str,
    warnings_by_tool: dict[int, list[str]] | None,
) -> list[str]:
    """The "# ─── / # ToolID N: segment / # WARNING: ..." block above a tool."""
    lines = [f"# {'─' * 68}", f"# ToolID {tool_id}: {segment}"]
    for msg in (warnings_by_tool or {}).get(tool_id, []):
        lines.append(f"# WARNING: {comment_safe(msg)}")
    return lines


def _gen_code_for_segment(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str | None:
    """Code for a non-Input/Output segment via the generator registry.

    None means the segment has no registered generator (unsupported tool);
    callers append their own TODO fallback in that case.
    """
    gen = _GENERATORS.get(segment)
    if gen is None:
        return None
    return gen(tool_id, segment, config, preds, anchors, names)


def _emit_main_body(
    order: list[int],
    node_map: dict[int, Any],
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
    input_paths: dict[int, str],
    output_paths: dict[int, str],
    names: dict[int, str],
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> list[str]:
    body: list[str] = []
    for tool_id in order:
        ctx = _tool_context(tool_id, node_map, pred_map, anchor_map)
        if ctx is None:
            continue
        node, segment, preds, anchors = ctx

        body += _header_comment_lines(tool_id, segment, warnings_by_tool)

        code: str | None
        if segment in SCAFFOLD_INPUT_SEGMENTS:
            code = gen_input(
                tool_id, segment, node.config, preds, anchors, input_paths, names
            )
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            code = gen_output(
                tool_id, segment, node.config, preds, anchors, output_paths, names
            )
        else:
            code = _gen_code_for_segment(
                tool_id, segment, node.config, preds, anchors, names
            )
            if code is None:
                body.append("# TODO: unsupported tool type — review manually")
                body.append(f"# {names[tool_id]} = ...")
                body.append("")
                continue

        body.extend(code.split("\n"))
        body.append("")

    return ["    " + line if line else "" for line in body]


# ── Public API ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScaffoldBlock:
    """One tool's chunk of the simple scaffold: header comments + code."""

    tool_id: int
    segment: str
    lines: list[str]


def scaffold_simple_blocks(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> tuple[list[str], list[ScaffoldBlock]]:
    """Return (header_lines, per-tool blocks) for the flat scaffold.

    Same content as scaffold_simple(), but structured per tool so callers
    (the .md writer) can interleave other material — e.g. the original
    <Node> XML — between tool blocks.
    """
    node_map = {
        int(n.tool_id): n for n in doc.nodes if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    order = topo_order(doc)
    source = pathlib.Path(doc.filepath).name
    names = _assign_frame_names(order, node_map)
    has_spatial = any(
        tool_segment(node.tool_type) in SCAFFOLD_SPATIAL_SEGMENTS
        for node in node_map.values()
    )
    has_browse = any(
        tool_segment(node.tool_type) in SCAFFOLD_BROWSE_SEGMENTS
        for node in node_map.values()
    )

    blocks: list[ScaffoldBlock] = []

    for tool_id in order:
        ctx = _tool_context(tool_id, node_map, pred_map, anchor_map)
        if ctx is None:
            continue
        node, segment, preds, anchors = ctx

        lines = _header_comment_lines(tool_id, segment, warnings_by_tool)

        code: str | None
        if segment in SCAFFOLD_INPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if is_shp(path):
                lines += SHX_NOTE_LINES
            code = read_stmt(names[tool_id], path, f'r"{path}"' if path else "")
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            src = preds[0] if preds else None
            df_in = frame_name(names, src)
            path = first_text(node.config, "File", "FileName")
            code = write_stmt(df_in, path, f'r"{path}"' if path else "")
        else:
            code = _gen_code_for_segment(
                tool_id, segment, node.config, preds, anchors, names
            )
            if code is None:
                lines.append("# TODO: unsupported tool type — review manually")
                lines.append(f"# {names[tool_id]} = ...")
                blocks.append(ScaffoldBlock(tool_id, segment, lines))
                continue

        lines.append(code)
        blocks.append(ScaffoldBlock(tool_id, segment, lines))

    header: list[str] = [
        f'"""Scaffold generated by yxray from {source}"""',
        "",
    ]
    if has_browse:
        header += ["import logging", ""]
    if has_spatial or any("gpd." in line for block in blocks for line in block.lines):
        header.append("import geopandas as gpd")
    if any(_NUMPY_RE.search(line) for block in blocks for line in block.lines):
        header.append("import numpy as np")
    header += [
        "import pandas as pd",
        "",
    ]
    if has_browse:
        header += ["logger = logging.getLogger(__name__)", ""]
    return header, blocks


def scaffold_simple(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> str:
    """Return a flat Python scaffold without ENV/paths block or main() wrapper.

    Used for .md display: shows tool-by-tool code in topological order with
    raw file paths, without the project-level boilerplate added to .py files.
    """
    header, blocks = scaffold_simple_blocks(doc, warnings_by_tool=warnings_by_tool)
    lines = list(header)
    for block in blocks:
        lines.extend(block.lines)
        lines.append("")
    return "\n".join(lines)


def scaffold(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> str:
    """Return a Python scaffold string for the given workflow.

    Each tool becomes one annotated code block in topological order.
    Supported tools get semi-concrete pandas code; unsupported tools get
    a TODO comment block.
    """
    node_map = {
        int(n.tool_id): n for n in doc.nodes if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    order = topo_order(doc)
    source = pathlib.Path(doc.filepath).name

    input_paths, output_paths, has_spatial = _collect_metadata(node_map, order)

    names = _assign_frame_names(order, node_map)
    body = _emit_main_body(
        order,
        node_map,
        pred_map,
        anchor_map,
        input_paths,
        output_paths,
        names,
        warnings_by_tool=warnings_by_tool,
    )
    uses_numpy = any(_NUMPY_RE.search(line) for line in body)
    has_shp = any(is_shp(p) for p in input_paths.values())

    lines = _emit_preamble(source, has_spatial, uses_numpy, has_shp)
    lines += _emit_paths_block(input_paths, output_paths)
    lines += ["", "", "def main() -> None:"]
    lines += body
    lines += [
        "",
        "",
        'if __name__ == "__main__":',
        "    logging.basicConfig(level=logging.INFO)",
        "    main()",
    ]

    return "\n".join(lines)
