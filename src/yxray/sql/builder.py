"""Build SQL conversion IR from selected workflow nodes."""

from __future__ import annotations

from collections.abc import Collection

from yxray.config_utils import as_list, field_name, first_text, select_field_rows
from yxray.models.types import ToolID
from yxray.models.workflow import WorkflowDoc
from yxray.sql.ir import (
    AggregateField,
    AggregateStep,
    FilterStep,
    IRStep,
    ProjectionStep,
    SelectField,
    SourceStep,
    UnsupportedStep,
)
from yxray.topology import compute_node_layer


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
        else:
            steps.append(
                UnsupportedStep(node.tool_id, node.tool_type, "unsupported-tool-type")
            )
    return tuple(steps)
