"""Rule-based workflow summarizer.

Takes a WorkflowDoc and returns a topologically-sorted list of
WorkflowStep objects describing what each tool does in plain English.

Only covers the most common Alteryx tool types (~25).  Unknown tool
types fall back to the short class name from the plugin string.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

from yxray.models.workflow import WorkflowDoc

__all__ = ["WorkflowStep", "summarize"]

# ---------------------------------------------------------------------------
# Tool type registry
# ---------------------------------------------------------------------------

# Last segment of the plugin string (e.g. "DbFileInput") →
# (display_name, category)
# category: "input" | "transform" | "output" | "unknown"
_TOOL_MAP: dict[str, tuple[str, str]] = {
    "DbFileInput":          ("Input",               "input"),
    "TextInput":            ("Text Input",           "input"),
    "DbFileOutput":         ("Output",              "output"),
    "BrowseV2":             ("Browse",              "output"),
    "AlteryxFilter":        ("Filter",              "transform"),
    "AlteryxJoin":          ("Join",                "transform"),
    "AlteryxSelect":        ("Select Fields",       "transform"),
    "AlteryxFormula":       ("Formula",             "transform"),
    "MultiFieldFormula":    ("Multi-Field Formula", "transform"),
    "AlteryxSummarize":     ("Summarize",           "transform"),
    "AlteryxSort":          ("Sort",                "transform"),
    "AlteryxSample":        ("Sample",              "transform"),
    "AlteryxUnion":         ("Union",               "transform"),
    "AlteryxAppend":        ("Append",              "transform"),
    "AlteryxCrossTab":      ("Cross Tab",           "transform"),
    "AlteryxTranspose":     ("Transpose",           "transform"),
    "DynamicRename":        ("Dynamic Rename",      "transform"),
    "RecordID":             ("Record ID",           "transform"),
    "DateTime":             ("Date/Time",           "transform"),
    "DataCleansing":        ("Data Cleansing",      "transform"),
    "FindReplace":          ("Find & Replace",      "transform"),
    "GenerateRows":         ("Generate Rows",       "transform"),
    "AlteryxFuzzyMatch":    ("Fuzzy Match",         "transform"),
    "Tile":                 ("Tile",                "transform"),
    "Random":               ("Random Sample",       "transform"),
    "RunCommand":           ("Run Command",         "transform"),
    "ToolContainer":        ("Container",           "unknown"),
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    tool_id: int
    short_type: str
    category: str   # "input" | "transform" | "output" | "unknown"
    description: str
    change: str | None  # "added" | "modified" | None

    def to_dict(self, *, include_change: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "short_type": self.short_type,
            "category": self.category,
            "description": self.description,
        }
        if include_change:
            d["change"] = self.change
        return d


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

    steps: list[WorkflowStep] = []
    for tid in order:
        node = node_map.get(tid)
        if node is None:
            continue
        short_type, category = _classify(node.tool_type)
        description = _describe(node.tool_type, node.config)
        # ToolContainer without a caption is pure layout noise — skip it.
        # Ones with a caption carry human-assigned structural labels worth showing.
        if "ToolContainer" in node.tool_type and not description:
            continue
        change: str | None = None
        if added_ids and tid in added_ids:
            change = "added"
        elif modified_ids and tid in modified_ids:
            change = "modified"
        steps.append(WorkflowStep(
            tool_id=int(tid),
            short_type=short_type,
            category=category,
            description=description,
            change=change,
        ))
    return steps


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


def _describe(tool_type: str, config: dict[str, Any]) -> str:
    """Return a short human-readable description of a tool's configuration."""
    segment = tool_type.split(".")[-1]

    if segment in ("DbFileInput", "DbFileOutput"):
        path = _get_text(config, "File")
        if not path:
            return ""
        try:
            return pathlib.Path(path).name
        except Exception:
            return path

    if segment == "TextInput":
        fields = config.get("Fields", {})
        if isinstance(fields, dict):
            field_list = fields.get("Field", [])
            if not isinstance(field_list, list):
                field_list = [field_list] if field_list else []
            return f"{len(field_list)} fields"
        return ""

    if segment == "AlteryxFilter":
        expr = _get_text(config, "Expression")
        return _truncate(expr, 60)

    if segment in ("AlteryxFormula", "MultiFieldFormula"):
        ffs = config.get("FormulaFields", {})
        if isinstance(ffs, dict):
            ff = ffs.get("FormulaField")
            if isinstance(ff, list):
                ff = ff[0] if ff else None
            if isinstance(ff, dict):
                expr = ff.get("@expression", "") or _get_text(ff, "Expression")
                field = ff.get("@field", "")
                if field and expr:
                    return _truncate(f"{field} = {expr}", 60)
                return _truncate(expr or field, 60)
        return ""

    if segment == "AlteryxJoin":
        ji = config.get("JoinInfo", {})
        if isinstance(ji, list):
            ji = ji[0] if ji else {}
        if isinstance(ji, dict):
            left = ji.get("@left", "") or ji.get("@Left", "")
            right = ji.get("@right", "") or ji.get("@Right", "")
            if left and right:
                return f"{left} = {right}"
        return ""

    if segment == "AlteryxSelect":
        fields = config.get("SelectFields", {})
        if not isinstance(fields, dict):
            fields = config.get("Fields", {})
        if isinstance(fields, dict):
            fl = fields.get("SelectField", fields.get("Field", []))
            if not isinstance(fl, list):
                fl = [fl] if fl else []
            selected = [
                f.get("@field", f.get("@name", ""))
                for f in fl
                if isinstance(f, dict) and f.get("@selected", "True") not in ("False", "false")
            ]
            if selected:
                return _truncate(", ".join(s for s in selected if s), 60)
        return ""

    if segment == "AlteryxSummarize":
        sfs = config.get("SummarizeFields", {})
        if isinstance(sfs, dict):
            sf_list = sfs.get("SummarizeField", [])
            if not isinstance(sf_list, list):
                sf_list = [sf_list] if sf_list else []
            groups = [
                f.get("@field", "")
                for f in sf_list
                if isinstance(f, dict) and f.get("@action", "").lower() == "groupby"
            ]
            if groups:
                return "Group by: " + _truncate(", ".join(g for g in groups if g), 50)
        return ""

    if segment == "AlteryxSort":
        si = config.get("SortInfo", {})
        if isinstance(si, dict):
            field = si.get("@field", "")
            order = si.get("@order", "")
            if field:
                return f"{field} ({order})" if order else field
        if isinstance(si, list) and si:
            first = si[0]
            if isinstance(first, dict):
                field = first.get("@field", "")
                order = first.get("@order", "")
                return f"{field} ({order})" if order else field
        return ""

    if segment == "AlteryxSample":
        for key in ("RecordLimit", "N", "@N"):
            val = config.get(key)
            if val:
                n = val.get("#text", "") if isinstance(val, dict) else str(val)
                return f"{n} records"
        return ""

    if segment == "RunCommand":
        cmd = _get_text(config, "Command") or config.get("@command", "")
        return _truncate(str(cmd), 50) if cmd else ""

    if segment == "ToolContainer":
        caption = _get_text(config, "Caption")
        return _truncate(caption, 60) if caption else ""

    return ""


def _truncate(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"
