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

from yxray.models.workflow import WorkflowDoc

__all__ = ["WorkflowStep", "KeyInsight", "summarize", "extract_key_insights"]

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
}


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
        clean_config = {k: v for k, v in (self.config or {}).items() if not k.startswith("@")}
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
    role: str  # "input"|"output"|"join"|"union"|"aggregate"|"filter"|"formula"|"reshape"
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
    node_map = {n.tool_id: n for n in doc.nodes}
    order = _topo_sort(doc)
    members_by_container: dict[int, list[Any]] = {}
    for node in doc.nodes:
        if node.container_id is not None:
            members_by_container.setdefault(int(node.container_id), []).append(node)

    steps: list[WorkflowStep] = []
    for tid in order:
        current_node = node_map.get(tid)
        if current_node is None:
            continue
        short_type, category = _classify(current_node.tool_type)
        description = _describe(
            current_node.tool_type,
            current_node.config,
            members=members_by_container.get(int(tid), []),
        )
        # ToolContainer without a caption is pure layout noise — skip it.
        # Ones with a caption carry human-assigned structural labels worth showing.
        if "ToolContainer" in current_node.tool_type and not description:
            continue
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
    node_ids = {n.tool_id for n in doc.nodes}
    successors: dict[Any, list[Any]] = {n.tool_id: [] for n in doc.nodes}
    predecessors: dict[Any, list[Any]] = {n.tool_id: [] for n in doc.nodes}
    for c in doc.connections:
        if c.src_tool in node_ids:
            successors[c.src_tool].append(c.dst_tool)
        if c.dst_tool in node_ids:
            predecessors[c.dst_tool].append(c.src_tool)

    def _downstream_count(tid: Any) -> int:
        visited: set[Any] = set()
        stack = list(successors.get(tid, []))
        while stack:
            n = stack.pop()
            if n not in visited:
                visited.add(n)
                stack.extend(successors.get(n, []))
        return len(visited)

    total = max(len(doc.nodes), 1)
    trunk_threshold = max(3, total // 5)

    node_map = {n.tool_id: n for n in doc.nodes}
    order = _topo_sort(doc)

    insights: list[KeyInsight] = []
    input_count = 0
    join_count = 0
    output_count = 0

    for tid in order:
        node = node_map.get(tid)
        if node is None:
            continue
        short_type, category = _classify(node.tool_type)
        segment = node.tool_type.split(".")[-1]
        dc = _downstream_count(tid)
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
            description = _first_text(node.config, "File", "FileName") or _describe(node.tool_type, node.config)
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
# Topological sort (Kahn's algorithm — safe against cycles)
# ---------------------------------------------------------------------------


def _topo_sort(doc: WorkflowDoc) -> list[Any]:
    """Return tool IDs in topological order (sources first)."""
    node_ids = [n.tool_id for n in doc.nodes]
    in_degree: dict[Any, int] = {nid: 0 for nid in node_ids}
    successors: dict[Any, list[Any]] = {nid: [] for nid in node_ids}

    for c in doc.connections:
        if c.src_tool in successors and c.dst_tool in in_degree:
            successors[c.src_tool].append(c.dst_tool)
            in_degree[c.dst_tool] += 1

    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    result: list[Any] = []
    while queue:
        nid = queue.pop(0)
        result.append(nid)
        for s in successors.get(nid, []):
            in_degree[s] -= 1
            if in_degree[s] == 0:
                queue.append(s)

    # Append any remaining nodes (cycles / disconnected)
    visited = set(result)
    for nid in node_ids:
        if nid not in visited:
            result.append(nid)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify(tool_type: str) -> tuple[str, str]:
    """Return (display_name, category) for a plugin string."""
    segment = tool_type.split(".")[-1]
    if segment in _TOOL_MAP:
        return _TOOL_MAP[segment]
    # Macro (.yxmc path) or unknown plugin
    name = segment.replace("_", " ").replace("-", " ")
    return name, "unknown"


def _get_text(obj: Any, key: str) -> str:
    """Safely extract text content from a config dict value."""
    if not isinstance(obj, dict):
        return ""
    val = obj.get(key)
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return str(val.get("#text", ""))
    if isinstance(val, list) and val:
        first = val[0]
        return str(first.get("#text", "")) if isinstance(first, dict) else ""
    return ""


def _iter_values(obj: Any) -> list[Any]:
    """Return a flattened list of scalar/dict/list values for config traversal."""
    if isinstance(obj, list):
        values: list[Any] = []
        for item in obj:
            values.extend(_iter_values(item))
        return values
    return [obj]


def _child_values(obj: Any, key: str) -> list[Any]:
    """Return every value found at key under a nested dict/list config tree."""
    found: list[Any] = []
    if isinstance(obj, dict):
        if key in obj:
            found.extend(_iter_values(obj[key]))
        for value in obj.values():
            found.extend(_child_values(value, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_child_values(item, key))
    return found


def _first_text(config: dict[str, Any], *keys: str) -> str:
    """Return first non-empty text found for any key, searching nested config."""
    for key in keys:
        direct = _get_text(config, key)
        if direct:
            return direct
        for value in _child_values(config, key):
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                text = value.get("#text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return ""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _field_name(field: dict[str, Any]) -> str:
    for key in ("@field", "@name", "@Field", "@Name", "field", "name"):
        value = field.get(key)
        if value:
            return str(value)
    return ""


def _count_by_short_type(nodes: list[Any]) -> str:
    counts: dict[str, int] = {}
    for node in nodes:
        short, _category = _classify(node.tool_type)
        counts[short] = counts.get(short, 0) + 1
    parts = [
        f"{name} x{count}" if count > 1 else name
        for name, count in sorted(counts.items())
    ]
    return ", ".join(parts)


DescribeFn = Callable[[dict[str, Any], list[Any] | None], str]


def _describe_file_tool(config: dict[str, Any], _members: list[Any] | None) -> str:
    path = _first_text(config, "File", "FileName")
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
    expr = _first_text(config, "Expression", "CustomFilterExpression")
    return _truncate(f"Keeps rows where {expr}", 90) if expr else "Filters rows"


def _formula_field_summaries(config: dict[str, Any]) -> list[str]:
    ffs = config.get("FormulaFields", {})
    formulas: list[str] = []
    if not isinstance(ffs, dict):
        return formulas

    for item in _as_list(ffs.get("FormulaField")):
        if not isinstance(item, dict):
            continue
        expr = (
            item.get("@expression", "")
            or item.get("@formula", "")
            or _get_text(item, "Expression")
        )
        field = item.get("@field", "") or item.get("@name", "")
        if field and expr:
            formulas.append(f"{field} = {expr}")
        elif expr or field:
            formulas.append(str(expr or field))
    return formulas


def _describe_formula(config: dict[str, Any], _members: list[Any] | None) -> str:
    formulas = _formula_field_summaries(config)
    if not formulas:
        expr = _first_text(config, "Expression", "Formula")
        if expr:
            formulas.append(expr)
    if not formulas:
        return "Calculates fields"
    prefix = "Calculates "
    return prefix + _truncate("; ".join(formulas), 90 - len(prefix))


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


def _select_field_rows(config: dict[str, Any]) -> list[Any]:
    fields = config.get("SelectFields", {})
    if not isinstance(fields, dict) or (
        "SelectField" not in fields and "Field" not in fields
    ):
        fields = config.get("Fields", {})
    if not isinstance(fields, dict):
        return []
    return _as_list(fields.get("SelectField", fields.get("Field", [])))


def _describe_select(config: dict[str, Any], _members: list[Any] | None) -> str:
    rows = _select_field_rows(config)
    selected = [
        _field_name(row)
        for row in rows
        if isinstance(row, dict)
        and row.get("@selected", "True") not in ("False", "false")
    ]
    renamed = [
        f"{_field_name(row)} -> {row.get('@rename') or row.get('@Rename')}"
        for row in rows
        if isinstance(row, dict)
        and _field_name(row)
        and (row.get("@rename") or row.get("@Rename"))
        and (row.get("@rename") or row.get("@Rename")) != _field_name(row)
    ]
    type_changes = [
        _field_name(row)
        for row in rows
        if isinstance(row, dict)
        and _field_name(row)
        and (row.get("@type") or row.get("@Type"))
    ]
    if not selected:
        return "Selects or changes fields"

    detail = f"Keeps {len(selected)} fields: " + _truncate(
        ", ".join(name for name in selected if name), 70
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

    field_rows = _as_list(summarize_fields.get("SummarizeField", []))
    groups = [
        row.get("@field", "")
        for row in field_rows
        if isinstance(row, dict) and row.get("@action", "").lower() == "groupby"
    ]
    if groups:
        return "Group by: " + _truncate(
            ", ".join(group for group in groups if group),
            50,
        )

    actions = [
        f"{row.get('@action', '')}({row.get('@field', '')})"
        for row in field_rows
        if isinstance(row, dict) and row.get("@action", "").lower() != "groupby"
    ]
    if actions:
        return "Summarizes: " + _truncate(
            ", ".join(action for action in actions if action),
            70,
        )
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
    mode = _first_text(config, "Mode", "ByName", "OutputMode")
    return f"Combines inputs ({mode})" if mode else "Combines input streams"


def _describe_sample(config: dict[str, Any], _members: list[Any] | None) -> str:
    for key in ("RecordLimit", "N", "@N"):
        val = config.get(key)
        if val:
            n = val.get("#text", "") if isinstance(val, dict) else str(val)
            return f"{n} records"
    return ""


def _describe_run_command(config: dict[str, Any], _members: list[Any] | None) -> str:
    cmd = _get_text(config, "Command") or config.get("@command", "")
    return _truncate(str(cmd), 50) if cmd else ""


def _describe_container(config: dict[str, Any], members: list[Any] | None) -> str:
    caption = _first_text(config, "Caption")
    member_nodes = members or []
    if not member_nodes:
        return _truncate(caption, 90) if caption else ""
    summary = _count_by_short_type(member_nodes)
    prefix = f"{caption}: " if caption else ""
    return _truncate(f"{prefix}contains {len(member_nodes)} tools ({summary})", 110)


_JOIN_SEGMENTS = frozenset({"AlteryxJoin", "Join", "AlteryxAppend", "Append"})
_UNION_SEGMENTS = frozenset({"AlteryxUnion", "Union"})
_AGGREGATE_SEGMENTS = frozenset(
    {"AlteryxSummarize", "Summarize", "AlteryxCrossTab", "CrossTab", "AlteryxTranspose", "Transpose"}
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
        rows = _select_field_rows(config)
        renamed = sum(
            1 for r in rows
            if isinstance(r, dict)
            and _field_name(r)
            and (r.get("@rename") or r.get("@Rename"))
            and (r.get("@rename") or r.get("@Rename")) != _field_name(r)
        )
        dropped = sum(
            1 for r in rows
            if isinstance(r, dict)
            and r.get("@selected", "True") in ("False", "false")
        )
        return "reshape" if (renamed >= 2 or dropped >= 3) else None
    return None


_DESCRIBERS: dict[str, DescribeFn] = {
    "DbFileInput": _describe_file_tool,
    "DbFileOutput": _describe_file_tool,
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
}


def _describe(
    tool_type: str,
    config: dict[str, Any],
    *,
    members: list[Any] | None = None,
) -> str:
    """Return a short human-readable description of a tool's configuration."""
    segment = tool_type.split(".")[-1]
    describer = _DESCRIBERS.get(segment)
    return describer(config, members) if describer else ""


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
