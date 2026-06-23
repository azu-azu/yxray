"""Render the v1 SQL IR as ANSI SQL-like output."""

from __future__ import annotations

from yxray.sql.ir import (
    AggregateStep,
    ComputeStep,
    ConversionReport,
    ConversionResult,
    FilterStep,
    IRStep,
    JoinStep,
    ProjectionStep,
    SourceStep,
    UnsupportedStep,
)


def _build_select_cols(
    projections: list[ProjectionStep],
    computes: list[ComputeStep],
    aggregate: AggregateStep | None,
    *,
    default: str = "*",
) -> list[str]:
    """Build the SELECT column list from projection, compute, and aggregate steps."""
    cols: list[str] = [
        f"{f.name} AS {f.rename}" if f.rename else f.name
        for step in projections
        for f in step.fields
    ]
    for step in computes:
        for f in step.formulas:
            cols.append(f"<raw: {f.expression}> AS {f.field}")
    cols = cols or [default]
    if aggregate:
        cols = list(aggregate.group_by) + [
            f"{f.action.upper()}({f.field})"
            + (f" AS {f.output_name}" if f.output_name else "")
            for f in aggregate.aggregates
        ]
    return cols


def _render_branch(steps: tuple[IRStep, ...], placeholder: str) -> str:
    """Render a linear sub-chain as a SQL fragment (no trailing semicolon).

    Used for each side of a JOIN CTE, and for the top-level linear pipeline.
    """
    source = next((s for s in steps if isinstance(s, SourceStep)), None)
    projections = [s for s in steps if isinstance(s, ProjectionStep)]
    filters = [s for s in steps if isinstance(s, FilterStep)]
    computes = [s for s in steps if isinstance(s, ComputeStep)]
    aggregate = next((s for s in steps if isinstance(s, AggregateStep)), None)
    columns = _build_select_cols(projections, computes, aggregate)
    from_clause = (
        source.source_identifier
        if source and source.source_identifier
        else placeholder
    )
    lines = ["SELECT", "  " + ",\n  ".join(columns), f"FROM {from_clause}"]
    if filters:
        lines.append("WHERE " + " AND ".join(s.expression for s in filters))
    if aggregate and aggregate.group_by:
        lines.append("GROUP BY " + ", ".join(aggregate.group_by))
    return "\n".join(lines)


def _render_join(
    steps: tuple[IRStep, ...],
    join_step: JoinStep,
) -> ConversionResult:
    """Render a cluster containing a Join node as a CTE-based SQL query."""
    left_steps = tuple(
        s for s in steps
        if not isinstance(s, JoinStep) and int(s.tool_id) in join_step.left_tool_ids
    )
    right_steps = tuple(
        s for s in steps
        if not isinstance(s, JoinStep) and int(s.tool_id) in join_step.right_tool_ids
    )
    post_steps = tuple(
        s for s in steps
        if not isinstance(s, JoinStep)
        and int(s.tool_id) not in join_step.left_tool_ids
        and int(s.tool_id) not in join_step.right_tool_ids
    )

    left_sql = _render_branch(left_steps, "t")
    right_sql = _render_branch(right_steps, "t2")

    on_clause = (
        " AND ".join(
            f"_L.{c.left_field} = _R.{c.right_field}"
            for c in join_step.conditions
        )
        if join_step.conditions
        else f"/* {join_step.raw_expression} */"
    )

    post_projections = [s for s in post_steps if isinstance(s, ProjectionStep)]
    post_computes = [s for s in post_steps if isinstance(s, ComputeStep)]
    post_filters = [s for s in post_steps if isinstance(s, FilterStep)]
    post_aggregate = next((s for s in post_steps if isinstance(s, AggregateStep)), None)

    select_cols = _build_select_cols(
        post_projections, post_computes, post_aggregate, default="_L.*, _R.*"
    )

    left_indented = "\n  ".join(left_sql.splitlines())
    right_indented = "\n  ".join(right_sql.splitlines())

    lines = [
        f"WITH _L AS (\n  {left_indented}\n),",
        f"_R AS (\n  {right_indented}\n)",
        "SELECT",
        "  " + ",\n  ".join(select_cols),
        "FROM _L",
        f"{join_step.join_type} JOIN _R",
        f"  ON {on_clause}",
    ]
    if post_filters:
        lines.append("WHERE " + " AND ".join(s.expression for s in post_filters))
    if post_aggregate and post_aggregate.group_by:
        lines.append("GROUP BY " + ", ".join(post_aggregate.group_by))

    unsupported = [s for s in steps if isinstance(s, UnsupportedStep)]
    all_computes = [s for s in steps if isinstance(s, ComputeStep)]
    join_warn: tuple[str, ...] = (
        () if join_step.conditions
        else (f"unparsed join expression: {join_step.raw_expression}",)
    )
    warnings: tuple[str, ...] = (
        join_warn
        + tuple(f"raw Formula expression in node {s.tool_id}" for s in all_computes)
        + tuple(
            f"unsupported {s.tool_type} (node {s.tool_id}; reason: {s.reason})"
            for s in unsupported
        )
    )
    report = ConversionReport(
        is_partial=bool(warnings),
        supported=tuple(
            type(s).__name__ for s in steps if not isinstance(s, UnsupportedStep)
        ),
        unsupported=tuple(s.tool_type for s in unsupported),
        warnings=warnings,
    )
    return ConversionResult(steps, "\n".join(lines) + ";", report)


def render_sql(steps: tuple[IRStep, ...]) -> ConversionResult:
    join_step = next((s for s in steps if isinstance(s, JoinStep)), None)
    if join_step:
        return _render_join(steps, join_step)

    source = next((step for step in steps if isinstance(step, SourceStep)), None)
    computes = [step for step in steps if isinstance(step, ComputeStep)]
    aggregate = next((step for step in steps if isinstance(step, AggregateStep)), None)
    unsupported = [step for step in steps if isinstance(step, UnsupportedStep)]

    used_placeholder = not source or not source.source_identifier
    sql = _render_branch(steps, "t") + ";"

    placeholder_warn: tuple[str, ...] = (
        ("source unknown: using placeholder 't'",) if used_placeholder else ()
    )
    formula_warnings: tuple[str, ...] = (
        tuple(
            f"Formula node {step.tool_id} not included in aggregate output"
            for step in computes
        )
        if aggregate
        else tuple(
            f"raw Formula expression in node {step.tool_id}" for step in computes
        )
    )
    warnings = (
        placeholder_warn
        + formula_warnings
        + tuple(
            f"unsupported {step.tool_type} (node {step.tool_id}; reason: {step.reason})"
            for step in unsupported
        )
    )
    report = ConversionReport(
        is_partial=bool(warnings),
        supported=tuple(
            type(step).__name__
            for step in steps
            if not isinstance(step, UnsupportedStep)
        ),
        unsupported=tuple(step.tool_type for step in unsupported),
        warnings=warnings,
    )
    return ConversionResult(steps, sql, report)
