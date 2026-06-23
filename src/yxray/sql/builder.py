"""Build SQL conversion IR from selected workflow nodes."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Collection

from yxray.config_utils import (
    as_list,
    field_name,
    first_text,
    get_text,
    select_field_rows,
)
from yxray.models.types import ToolID
from yxray.models.workflow import WorkflowDoc
from yxray.sql.ir import (
    AggregateField,
    AggregateStep,
    ComputeStep,
    FilterStep,
    FormulaField,
    IRStep,
    JoinCondition,
    JoinStep,
    ProjectionStep,
    SelectField,
    SourceStep,
    UnsupportedStep,
)
from yxray.topology import compute_node_layer

_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)
_LEFT_INPUT_ANCHOR = "Left"
_RIGHT_INPUT_ANCHOR = "Right"


def _parse_join_conditions(expression: str) -> tuple[JoinCondition, ...]:
    return tuple(
        JoinCondition(m.group(1), m.group(2))
        for m in _JOIN_COND_RE.finditer(expression)
    )


def _ancestors(
    reverse: dict[int, list[int]],
    start_id: int,
    selected: set[int],
) -> frozenset[int]:
    """BFS backward from start_id; return all selected predecessor tool_ids."""
    visited: set[int] = set()
    queue: deque[int] = deque([start_id])
    while queue:
        node_id = queue.popleft()
        for pred_id in reverse.get(node_id, []):
            if pred_id in selected and pred_id not in visited:
                visited.add(pred_id)
                queue.append(pred_id)
    return frozenset(visited)


def build_ir(doc: WorkflowDoc, tool_ids: Collection[ToolID]) -> tuple[IRStep, ...]:
    selected = {int(tool_id) for tool_id in tool_ids}
    layers = compute_node_layer(doc)
    nodes = sorted(
        (node for node in doc.nodes if int(node.tool_id) in selected),
        key=lambda node: (
            layers.get(int(node.tool_id), 0),
            node.y,
            node.x,
            int(node.tool_id),
        ),
    )
    reverse: dict[int, list[int]] = {}
    for c in doc.connections:
        reverse.setdefault(int(c.dst_tool), []).append(int(c.src_tool))
    steps: list[IRStep] = []
    for node in nodes:
        segment = node.tool_type.split(".")[-1]
        config = node.config
        if segment in {"InputData", "DbFileInput"}:
            steps.append(
                SourceStep(node.tool_id, first_text(config, "File", "FileName") or None)
            )
        elif segment in {"Select", "AlteryxSelect"}:
            fields = tuple(
                SelectField(
                    field_name(row),
                    row.get("@rename") or row.get("@Rename"),
                    row.get("@type") or row.get("@Type"),
                )
                for row in select_field_rows(config)
                if isinstance(row, dict)
                and row.get("@selected", "True").lower() != "false"
                and field_name(row)
            )
            steps.append(ProjectionStep(node.tool_id, fields))
        elif segment in {"Filter", "AlteryxFilter"}:
            expression = first_text(config, "Expression", "CustomFilterExpression")
            steps.append(
                FilterStep(node.tool_id, expression)
                if expression
                else UnsupportedStep(
                    node.tool_id, node.tool_type, "missing-filter-expression"
                )
            )
        elif segment in {"Formula", "AlteryxFormula", "MultiFieldFormula"}:
            ffs = config.get("FormulaFields", {})
            formulas = tuple(
                FormulaField(
                    field=item.get("@field", "") or item.get("@name", ""),
                    expression=(
                        item.get("@expression", "")
                        or item.get("@formula", "")
                        or get_text(item, "Expression")
                    ),
                )
                for item in (
                    as_list(ffs.get("FormulaField", []))
                    if isinstance(ffs, dict)
                    else []
                )
                if isinstance(item, dict)
                and (item.get("@field") or item.get("@name"))
                and (
                    item.get("@expression")
                    or item.get("@formula")
                    or get_text(item, "Expression")
                )
            )
            steps.append(
                ComputeStep(node.tool_id, formulas)
                if formulas
                else UnsupportedStep(node.tool_id, node.tool_type, "empty-formula")
            )
        elif segment in {"Summarize", "AlteryxSummarize"}:
            rows = (
                as_list(config.get("SummarizeFields", {}).get("SummarizeField", []))
                if isinstance(config.get("SummarizeFields"), dict)
                else []
            )
            aggregate_fields = tuple(
                AggregateField(
                    field_name(row),
                    str(row.get("@action", "")),
                    str(row.get("@rename")) or None,
                )
                for row in rows
                if isinstance(row, dict) and field_name(row)
            )
            steps.append(
                AggregateStep(
                    node.tool_id,
                    tuple(
                        field.field
                        for field in aggregate_fields
                        if field.action.lower() == "groupby"
                    ),
                    tuple(
                        field
                        for field in aggregate_fields
                        if field.action.lower() != "groupby"
                    ),
                )
            )
        elif segment in {"Join", "AlteryxJoin"}:
            expression = first_text(config, "JoinExpression") or ""
            if not expression:
                steps.append(
                    UnsupportedStep(
                        node.tool_id, node.tool_type, "missing-join-expression"
                    )
                )
            else:
                conditions = _parse_join_conditions(expression)
                left_direct = next(
                    (
                        int(c.src_tool)
                        for c in doc.connections
                        if int(c.dst_tool) == int(node.tool_id)
                        and c.dst_anchor == _LEFT_INPUT_ANCHOR
                    ),
                    None,
                )
                right_direct = next(
                    (
                        int(c.src_tool)
                        for c in doc.connections
                        if int(c.dst_tool) == int(node.tool_id)
                        and c.dst_anchor == _RIGHT_INPUT_ANCHOR
                    ),
                    None,
                )
                left_ids = (
                    _ancestors(reverse, left_direct, selected) | {left_direct}
                    if left_direct is not None and left_direct in selected
                    else frozenset()
                )
                right_ids = (
                    _ancestors(reverse, right_direct, selected) | {right_direct}
                    if right_direct is not None and right_direct in selected
                    else frozenset()
                )
                steps.append(
                    JoinStep(node.tool_id, left_ids, right_ids, conditions, expression)
                )
        else:
            steps.append(
                UnsupportedStep(node.tool_id, node.tool_type, "unsupported-tool-type")
            )
    return tuple(steps)
