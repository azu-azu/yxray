"""Rule-based workflow summarizer.

Takes a WorkflowDoc and returns a topologically-sorted list of
WorkflowStep objects describing what each tool does in plain English.

Only covers the most common Alteryx tool types (~25).  Unknown tool
types fall back to the short class name from the plugin string.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yxray.config_utils import (
    as_list,
    field_name,
    first_text,
    formula_field_summaries,
    get_text,
    select_field_rows,
)
from yxray.models.workflow import WorkflowDoc
from yxray.topology import topo_order

__all__ = [
    "WorkflowStep",
    "KeyInsight",
    "classify",
    "summarize",
    "extract_key_insights",
]

# ---------------------------------------------------------------------------
# Tool type registry
# ---------------------------------------------------------------------------

# Last segment of the plugin string (e.g. "DbFileInput") →
# (display_name, category)
# category: "input" | "transform" | "output" | "unknown"
_TOOL_MAP: dict[str, tuple[str, str]] = {
    "DbFileInput": ("Input", "input"),
    "InputData": ("Input", "input"),
    "TextInput": ("Text Input", "input"),
    "DbFileOutput": ("Output", "output"),
    "OutputData": ("Output", "output"),
    "BrowseV2": ("Browse", "output"),
    "Browse": ("Browse", "output"),
    "AlteryxFilter": ("Filter", "transform"),
    "Filter": ("Filter", "transform"),
    "AlteryxJoin": ("Join", "transform"),
    "Join": ("Join", "transform"),
    "AlteryxSelect": ("Select Fields", "transform"),
    "Select": ("Select Fields", "transform"),
    "AlteryxFormula": ("Formula", "transform"),
    "Formula": ("Formula", "transform"),
    "MultiFieldFormula": ("Multi-Field Formula", "transform"),
    "AlteryxSummarize": ("Summarize", "transform"),
    "Summarize": ("Summarize", "transform"),
    "AlteryxSort": ("Sort", "transform"),
    "Sort": ("Sort", "transform"),
    "AlteryxSample": ("Sample", "transform"),
    "Sample": ("Sample", "transform"),
    "AlteryxUnion": ("Union", "transform"),
    "Union": ("Union", "transform"),
    "AlteryxAppend": ("Append", "transform"),
    "Append": ("Append", "transform"),
    "AlteryxCrossTab": ("Cross Tab", "transform"),
    "CrossTab": ("Cross Tab", "transform"),
    "AlteryxTranspose": ("Transpose", "transform"),
    "Transpose": ("Transpose", "transform"),
    "DynamicInput": ("Dynamic Input", "input"),
    "DynamicRename": ("Dynamic Rename", "transform"),
    "RecordID": ("Record ID", "transform"),
    "DateTime": ("Date/Time", "transform"),
    "DataCleansing": ("Data Cleansing", "transform"),
    "FindReplace": ("Find & Replace", "transform"),
    "GenerateRows": ("Generate Rows", "transform"),
    "AlteryxFuzzyMatch": ("Fuzzy Match", "transform"),
    "Tile": ("Tile", "transform"),
    "Random": ("Random Sample", "transform"),
    "RunCommand": ("Run Command", "transform"),
    "ToolContainer": ("Container", "unknown"),
    "CountRecords": ("Count Records", "transform"),
}

# Trunk detection thresholds for extract_key_insights:
# a Filter/Formula is considered a "trunk" node when its downstream reach
# is at least _TRUNK_MIN_DOWNSTREAM and at least 1/_TRUNK_RATIO_DIVISOR of all nodes.
_TRUNK_MIN_DOWNSTREAM = 3
_TRUNK_RATIO_DIVISOR = 5


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStep:
    tool_id: int
    short_type: str
    category: str  # "input" | "transform" | "output" | "unknown"
    description: str
    change: str | None  # "added" | "modified" | None
    config: dict[str, Any] | None = None

    def to_dict(self, *, include_change: bool = False) -> dict[str, Any]:
        # Exclude XML attribute keys (@ prefix) — they're noise in the UI
        clean_config = {
            k: v for k, v in (self.config or {}).items() if not k.startswith("@")
        }
        d: dict[str, Any] = {
            "tool_id": self.tool_id,
            "short_type": self.short_type,
            "category": self.category,
            "description": self.description,
            "config": clean_config,
        }
        if include_change:
            d["change"] = self.change
        return d


@dataclass
class KeyInsight:
    """A single 'important' node distilled for the at-a-glance summary."""

    tool_id: int
    short_type: str
    role: str  # input|output|join|union|aggregate|filter|formula|reshape
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "short_type": self.short_type,
            "role": self.role,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def summarize(
    doc: WorkflowDoc,
    *,
    added_ids: frozenset[int] | None = None,
    modified_ids: frozenset[int] | None = None,
) -> list[WorkflowStep]:
    """Return a topologically-sorted list of workflow steps.

    Parameters
    ----------
    doc:
        The parsed workflow document to summarise.
    added_ids:
        Tool IDs that were added (diff mode only).  Marked with change="added".
    modified_ids:
        Tool IDs that were modified (diff mode only).  Marked with change="modified".
    """
    node_map = {int(n.tool_id): n for n in doc.nodes}
    order = topo_order(doc)
    members_by_container: dict[int, list[Any]] = {}
    for node in doc.nodes:
        if node.container_id is not None:
            members_by_container.setdefault(int(node.container_id), []).append(node)

    steps: list[WorkflowStep] = []
    for tid in order:
        current_node = node_map.get(tid)
        if current_node is None:
            continue
        short_type, category = classify(current_node.tool_type)
        description = _describe(
            current_node.tool_type,
            current_node.config,
            members=members_by_container.get(int(tid), []),
            max_len=90,
        )
        change: str | None = None
        if added_ids and tid in added_ids:
            change = "added"
        elif modified_ids and tid in modified_ids:
            change = "modified"
        steps.append(
            WorkflowStep(
                tool_id=int(tid),
                short_type=short_type,
                category=category,
                description=description,
                change=change,
                config=current_node.config,
            )
        )
    return steps


def extract_key_insights(doc: WorkflowDoc) -> list[KeyInsight]:
    """Return the most structurally important nodes as human-readable insights.

    Importance is determined by tool type and graph topology:
    - Input/Output tools: always included
    - Join/Union/Append/Summarize/CrossTab/Transpose: always included
    - Filter/Formula: only when they feed >= 20% of total nodes downstream
    - Select: only when they rename >= 2 or drop >= 3 fields
    """
    node_ids = {int(n.tool_id) for n in doc.nodes}
    successors: dict[int, list[int]] = {int(n.tool_id): [] for n in doc.nodes}
    predecessors: dict[int, list[int]] = {int(n.tool_id): [] for n in doc.nodes}
    for c in doc.connections:
        src_tool = int(c.src_tool)
        dst_tool = int(c.dst_tool)
        if src_tool in node_ids:
            successors[src_tool].append(dst_tool)
        if dst_tool in node_ids:
            predecessors[dst_tool].append(src_tool)

    total = max(len(doc.nodes), 1)
    trunk_threshold = max(_TRUNK_MIN_DOWNSTREAM, total // _TRUNK_RATIO_DIVISOR)

    node_map = {int(n.tool_id): n for n in doc.nodes}
    order = topo_order(doc)

    # Pre-compute downstream reach in O(n + e) using sum approximation.
    # May overcount in diamond (converging) patterns, but that is acceptable
    # for the trunk detection heuristic.
    downstream: dict[int, int] = {nid: 0 for nid in order}
    for _tid in reversed(order):
        for _s in successors.get(_tid, []):
            downstream[_tid] += 1 + downstream.get(_s, 0)

    insights: list[KeyInsight] = []
    input_count = 0
    join_count = 0
    output_count = 0

    for tid in order:
        node = node_map.get(tid)
        if node is None:
            continue
        short_type, category = classify(node.tool_type)
        segment = node.tool_type.split(".")[-1]
        dc = downstream.get(tid, 0)
        role = _insight_role(
            segment, category, node.config,
            successors.get(tid, []),
            dc, trunk_threshold,
        )
        if role is None:
            continue
        if role == "input":
            input_count += 1
        elif role == "join":
            join_count += 1
        elif role == "output":
            output_count += 1
        if role in ("input", "output"):
            description = first_text(
                node.config, "File", "FileName"
            ) or _describe(node.tool_type, node.config)
        else:
            description = _describe(node.tool_type, node.config)
        insights.append(KeyInsight(
            tool_id=int(tid),
            short_type=short_type,
            role=role,
            description=description,
        ))

    # Summary count row at the top
    parts = []
    if input_count:
        parts.append(f"Input × {input_count}")
    if join_count:
        parts.append(f"Join × {join_count}")
    if output_count:
        parts.append(f"Output × {output_count}")
    if parts:
        insights.insert(0, KeyInsight(
            tool_id=-1,
            short_type="",
            role="summary",
            description="  ·  ".join(parts),
        ))

    return insights


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def classify(tool_type: str) -> tuple[str, str]:
    """Return (display_name, category) for a plugin string."""
    segment = tool_type.split(".")[-1]
    if segment in _TOOL_MAP:
        return _TOOL_MAP[segment]
    # Macro (.yxmc path) or unknown plugin
    name = segment.replace("_", " ").replace("-", " ")
    return name, "unknown"


def _count_by_short_type(nodes: list[Any]) -> str:
    counts: dict[str, int] = {}
    for node in nodes:
        short, _category = classify(node.tool_type)
        counts[short] = counts.get(short, 0) + 1
    parts = [
        f"{name} x{count}" if count > 1 else name
        for name, count in sorted(counts.items())
    ]
    return ", ".join(parts)


DescribeFn = Callable[[dict[str, Any], list[Any] | None], str]


def _describe_file_tool(config: dict[str, Any], _members: list[Any] | None) -> str:
    path = first_text(config, "File", "FileName")
    return f"Uses file: {pathlib.Path(path).name}" if path else ""


def _describe_text_input(config: dict[str, Any], _members: list[Any] | None) -> str:
    fields = config.get("Fields", {})
    if isinstance(fields, dict):
        field_list = fields.get("Field", [])
        if not isinstance(field_list, list):
            field_list = [field_list] if field_list else []
        return f"{len(field_list)} fields"
    return ""


def _describe_filter(config: dict[str, Any], _members: list[Any] | None) -> str:
    expr = first_text(config, "Expression", "CustomFilterExpression")
    return f"Keeps rows where {expr}" if expr else "Filters rows"


def _describe_formula(config: dict[str, Any], _members: list[Any] | None) -> str:
    formulas = formula_field_summaries(config)
    if not formulas:
        expr = first_text(config, "Expression", "Formula")
        if expr:
            formulas.append(expr)
    if not formulas:
        return "Calculates fields"
    prefix = "Calculates "
    return prefix + "; ".join(formulas)


def _describe_join(config: dict[str, Any], _members: list[Any] | None) -> str:
    join_info = config.get("JoinInfo", {})
    if isinstance(join_info, list):
        join_info = join_info[0] if join_info else {}
    if isinstance(join_info, dict):
        left = join_info.get("@left", "") or join_info.get("@Left", "")
        right = join_info.get("@right", "") or join_info.get("@Right", "")
        if left and right:
            return f"{left} = {right}"
    return ""


def _get_rename(row: dict[str, Any]) -> str:
    return row.get("@rename") or row.get("@Rename") or ""


def _describe_select(config: dict[str, Any], _members: list[Any] | None) -> str:
    rows = select_field_rows(config)
    selected = [
        field_name(row)
        for row in rows
        if isinstance(row, dict)
        and row.get("@selected", "True") not in ("False", "false")
    ]
    renamed = [
        f"{field_name(row)} -> {rename}"
        for row in rows
        if isinstance(row, dict)
        and field_name(row)
        and (rename := _get_rename(row))
        and rename != field_name(row)
    ]
    type_changes = [
        field_name(row)
        for row in rows
        if isinstance(row, dict)
        and field_name(row)
        and (row.get("@type") or row.get("@Type"))
    ]
    if not selected:
        return "Selects or changes fields"

    detail = f"Keeps {len(selected)} fields: " + ", ".join(
        name for name in selected if name
    )
    extras: list[str] = []
    if renamed:
        extras.append(f"{len(renamed)} renamed")
    if type_changes:
        extras.append(f"{len(type_changes)} typed")
    return detail + (f" ({', '.join(extras)})" if extras else "")


def _describe_summarize(config: dict[str, Any], _members: list[Any] | None) -> str:
    summarize_fields = config.get("SummarizeFields", {})
    if not isinstance(summarize_fields, dict):
        return "Aggregates rows"

    field_rows = as_list(summarize_fields.get("SummarizeField", []))
    groups = [
        row.get("@field", "")
        for row in field_rows
        if isinstance(row, dict) and row.get("@action", "").lower() == "groupby"
    ]
    if groups:
        return "Group by: " + ", ".join(group for group in groups if group)

    actions = [
        f"{row.get('@action', '')}({row.get('@field', '')})"
        for row in field_rows
        if isinstance(row, dict) and row.get("@action", "").lower() != "groupby"
    ]
    if actions:
        return "Summarizes: " + ", ".join(action for action in actions if action)
    return "Aggregates rows"


def _describe_sort(config: dict[str, Any], _members: list[Any] | None) -> str:
    sort_info = config.get("SortInfo", {})
    if isinstance(sort_info, dict):
        field = sort_info.get("@field", "")
        order = sort_info.get("@order", "")
        if field:
            return f"{field} ({order})" if order else field
    if isinstance(sort_info, list) and sort_info:
        first = sort_info[0]
        if isinstance(first, dict):
            field = first.get("@field", "")
            order = first.get("@order", "")
            return f"{field} ({order})" if order else field
    return "Sorts rows"


def _describe_union(config: dict[str, Any], _members: list[Any] | None) -> str:
    mode = first_text(config, "Mode", "ByName", "OutputMode")
    return f"Combines inputs ({mode})" if mode else "Combines input streams"


def _describe_sample(config: dict[str, Any], _members: list[Any] | None) -> str:
    for key in ("RecordLimit", "N", "@N"):
        val = config.get(key)
        if val:
            n = val.get("#text", "") if isinstance(val, dict) else str(val)
            return f"{n} records"
    return ""


def _describe_run_command(config: dict[str, Any], _members: list[Any] | None) -> str:
    cmd = get_text(config, "Command") or config.get("@command", "")
    return str(cmd) if cmd else ""


def _describe_container(config: dict[str, Any], members: list[Any] | None) -> str:
    caption = first_text(config, "Caption")
    member_nodes = members or []
    if not member_nodes:
        return _truncate(caption, 90) if caption else ""
    summary = _count_by_short_type(member_nodes)
    prefix = f"{caption}: " if caption else ""
    return _truncate(f"{prefix}contains {len(member_nodes)} tools ({summary})", 110)


_JOIN_SEGMENTS = frozenset({"AlteryxJoin", "Join", "AlteryxAppend", "Append"})
_UNION_SEGMENTS = frozenset({"AlteryxUnion", "Union"})
_AGGREGATE_SEGMENTS = frozenset(
    {
        "AlteryxSummarize", "Summarize", "AlteryxCrossTab",
        "CrossTab", "AlteryxTranspose", "Transpose",
    }
)
_FILTER_SEGMENTS = frozenset({"AlteryxFilter", "Filter"})
_FORMULA_SEGMENTS = frozenset({"AlteryxFormula", "Formula", "MultiFieldFormula"})
_SELECT_SEGMENTS = frozenset({"AlteryxSelect", "Select"})


def _insight_role(
    segment: str,
    category: str,
    config: dict[str, Any],
    succs: list[Any],
    downstream_count: int,
    trunk_threshold: int,
) -> str | None:
    if category == "input" and "Browse" not in segment:
        return "input"
    if category == "output" and "Browse" not in segment:
        return "output"
    if segment in _JOIN_SEGMENTS:
        return "join"
    if segment in _UNION_SEGMENTS:
        return "union"
    if segment in _AGGREGATE_SEGMENTS:
        return "aggregate"
    if segment in _FILTER_SEGMENTS:
        return "filter" if downstream_count >= trunk_threshold else None
    if segment in _FORMULA_SEGMENTS:
        return "formula" if downstream_count >= trunk_threshold else None
    if segment in _SELECT_SEGMENTS:
        rows = select_field_rows(config)
        renamed = sum(
            1 for r in rows
            if isinstance(r, dict)
            and field_name(r)
            and (rename := _get_rename(r))
            and rename != field_name(r)
        )
        dropped = sum(
            1 for r in rows
            if isinstance(r, dict)
            and r.get("@selected", "True") in ("False", "false")
        )
        return "reshape" if (renamed >= 2 or dropped >= 3) else None
    return None


def _describe_count_records(config: dict[str, Any], _members: list[Any] | None) -> str:
    return "Counts records"


_DESCRIBERS: dict[str, DescribeFn] = {
    "DbFileInput": _describe_file_tool,
    "DbFileOutput": _describe_file_tool,
    "DynamicInput": _describe_file_tool,
    "InputData": _describe_file_tool,
    "OutputData": _describe_file_tool,
    "TextInput": _describe_text_input,
    "AlteryxFilter": _describe_filter,
    "Filter": _describe_filter,
    "AlteryxFormula": _describe_formula,
    "Formula": _describe_formula,
    "MultiFieldFormula": _describe_formula,
    "AlteryxJoin": _describe_join,
    "Join": _describe_join,
    "AlteryxSelect": _describe_select,
    "Select": _describe_select,
    "AlteryxSummarize": _describe_summarize,
    "Summarize": _describe_summarize,
    "AlteryxSort": _describe_sort,
    "Sort": _describe_sort,
    "AlteryxUnion": _describe_union,
    "Union": _describe_union,
    "AlteryxSample": _describe_sample,
    "Sample": _describe_sample,
    "RunCommand": _describe_run_command,
    "ToolContainer": _describe_container,
    "CountRecords": _describe_count_records,
}


def _describe(
    tool_type: str,
    config: dict[str, Any],
    *,
    members: list[Any] | None = None,
    max_len: int | None = None,
) -> str:
    """Return a human-readable description of a tool's configuration.

    Pass max_len to cap the output length (Summary panel).
    Omit max_len (default None) for untruncated output (At a Glance panel).
    """
    segment = tool_type.split(".")[-1]
    describer = _DESCRIBERS.get(segment)
    result = describer(config, members) if describer else ""
    if max_len is not None and result:
        result = _truncate(result, max_len)
    return result


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
