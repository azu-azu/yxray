"""Whole-scaffold assembly: the package's public API lives here.

scaffold(doc) returns a .py file string with one code block per tool,
in topological order (preamble, ENV/paths block, main()); scaffold_simple
/ scaffold_simple_blocks return the flat .md variant without the
project-level boilerplate. Both share a single per-tool loop (_tool_blocks):
each tool becomes a ToolContext dispatched through _registry.GENERATORS by
segment alone — Input/Output included — so the only difference between the
two outputs is the PathStyle passed in (PROJECT_PATHS vs INLINE_PATHS) and
the surrounding boilerplate.

Variable naming: each tool's output is named df<tool_id> (e.g. df34, df108),
matching the ToolID comment above each block so the mapping is unambiguous.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Any

from yxray.config_utils import (
    comment_safe,
    first_text,
)
from yxray.models.workflow import WorkflowDoc
from yxray.scaffold._common import PathStyle, ToolContext
from yxray.scaffold._io import (
    INLINE_PATHS,
    PROJECT_PATHS,
    SHX_RESTORE_LINE,
    SPATIAL_EXTS,
    is_shp,
)
from yxray.scaffold._registry import DETAIL_HINT_SEGMENTS, GENERATORS
from yxray.tool_registry import (
    SCAFFOLD_BROWSE_SEGMENTS,
    SCAFFOLD_INPUT_SEGMENTS,
    SCAFFOLD_OUTPUT_SEGMENTS,
    SCAFFOLD_SPATIAL_SEGMENTS,
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


def _make_context(
    tool_id: int,
    node: Any,
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
    names: dict[int, str],
    paths: PathStyle,
) -> ToolContext:
    """Bundle a tool's config + graph position + path style into one argument."""
    return ToolContext(
        tool_id=tool_id,
        segment=tool_segment(node.tool_type),
        config=node.config,
        preds=pred_map.get(tool_id, []),
        anchors=anchor_map.get(tool_id, {}),
        names=names,
        paths=paths,
    )


def node_code_snippets(doc: WorkflowDoc) -> dict[int, str]:
    """Per-node pandas code, identical to the .md Python Scaffold section.

    Only returns entries for tool_ids whose segment is in
    DETAIL_HINT_SEGMENTS; callers should fall back to the generic
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
        if segment not in DETAIL_HINT_SEGMENTS:
            continue
        # DETAIL_HINT excludes Input/Output, so the path style never matters here.
        ctx = _make_context(tool_id, node, pred_map, anchor_map, names, INLINE_PATHS)
        snippets[tool_id] = GENERATORS[segment](ctx)
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


def _tool_blocks(
    order: list[int],
    node_map: dict[int, Any],
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
    names: dict[int, str],
    paths: PathStyle,
    warnings_by_tool: dict[int, list[str]] | None,
) -> list[ScaffoldBlock]:
    """One ScaffoldBlock per tool, in topological order.

    The single per-tool loop behind both scaffold outputs: `paths` selects
    how Input/Output render file paths (PROJECT_PATHS for .py, INLINE_PATHS
    for .md), and every segment — Input/Output included — dispatches through
    GENERATORS, so there is no per-tool branching here.
    """
    blocks: list[ScaffoldBlock] = []
    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        ctx = _make_context(tool_id, node, pred_map, anchor_map, names, paths)
        lines = _header_comment_lines(ctx.tool_id, ctx.segment, warnings_by_tool)
        gen = GENERATORS.get(ctx.segment)
        if gen is None:
            lines.append("# TODO: unsupported tool type — review manually")
            lines.append(f"# {ctx.df_out} = ...")
        else:
            lines.append(gen(ctx))
        blocks.append(ScaffoldBlock(ctx.tool_id, ctx.segment, lines))
    return blocks


def _flatten_blocks(blocks: list[ScaffoldBlock]) -> list[str]:
    """Blocks → flat lines, one blank line after each block.

    A block's code entry may be a multi-line string, so each entry is
    exploded on newlines to keep the result a list of single lines.
    """
    lines: list[str] = []
    for block in blocks:
        for entry in block.lines:
            lines.extend(entry.split("\n"))
        lines.append("")
    return lines


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

    blocks = _tool_blocks(
        order, node_map, pred_map, anchor_map, names, INLINE_PATHS, warnings_by_tool
    )

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
    return "\n".join(list(header) + _flatten_blocks(blocks))


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
    blocks = _tool_blocks(
        order, node_map, pred_map, anchor_map, names, PROJECT_PATHS, warnings_by_tool
    )
    body = ["    " + line if line else "" for line in _flatten_blocks(blocks)]
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
