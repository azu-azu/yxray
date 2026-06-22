"""Render the v1 SQL IR as ANSI SQL-like output."""

from __future__ import annotations

from yxray.sql.ir import (
    AggregateStep,
    ConversionResult,
    FilterStep,
    IRStep,
    ProjectionStep,
    SourceStep,
    UnsupportedStep,
)


def render_sql(steps: tuple[IRStep, ...]) -> ConversionResult:
    source = next((step for step in steps if isinstance(step, SourceStep)), None)
    projections = [step for step in steps if isinstance(step, ProjectionStep)]
    filters = [step for step in steps if isinstance(step, FilterStep)]
    aggregate = next((step for step in steps if isinstance(step, AggregateStep)), None)
    unsupported = [step for step in steps if isinstance(step, UnsupportedStep)]
    columns = [
        f"{field.name} AS {field.rename}" if field.rename else field.name
        for step in projections
        for field in step.fields
    ] or ["*"]
    if aggregate:
        columns = list(aggregate.group_by) + [
            f"{field.action.upper()}({field.field})"
            + (f" AS {field.output_name}" if field.output_name else "")
            for field in aggregate.aggregates
        ]
    from_clause = (
        source.source_identifier
        if source and source.source_identifier
        else f"<source:node_{source.tool_id if source else 'unknown'}>"
    )
    lines = ["SELECT", "  " + ",\n  ".join(columns), f"FROM {from_clause}"]
    if filters:
        lines.append("WHERE " + " AND ".join(step.expression for step in filters))
    if aggregate and aggregate.group_by:
        lines.append("GROUP BY " + ", ".join(aggregate.group_by))
    warnings = (
        ("unresolved source",) if not source or not source.source_identifier else ()
    ) + tuple(
        f"unsupported {step.tool_type} (node {step.tool_id})" for step in unsupported
    )
    return ConversionResult(steps, "\n".join(lines) + ";", warnings)
