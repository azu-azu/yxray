"""Aggregation tools (Summarize) for the scaffold generator."""

from __future__ import annotations

from yxray.config_utils import as_list, first_text, py_str
from yxray.scaffold._common import GeneratedCode, ToolContext


def gen_summarize(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    sf = ctx.config.get("SummarizeFields", {})
    if not isinstance(sf, dict):
        return GeneratedCode(f"{df_out} = {df_in}.groupby([...]).agg({{...}})  # TODO")
    rows = as_list(sf.get("SummarizeField", []))
    groups = [
        r.get("@field", "")
        for r in rows
        if isinstance(r, dict) and r.get("@action", "").lower() == "groupby"
    ]
    aggs = [
        (
            r.get("@field", ""),
            r.get("@action", ""),
            first_text(r, "@rename", "@Rename", "rename", "Rename"),
        )
        for r in rows
        if isinstance(r, dict) and r.get("@action", "").lower() != "groupby"
    ]
    if not groups and not aggs:
        return GeneratedCode(f"{df_out} = {df_in}.groupby([...]).agg({{...}})  # TODO")
    group_str = "[" + ", ".join(py_str(g) for g in groups if g) + "]"
    if aggs:
        # Named aggregation preserves Alteryx output names and allows multiple
        # aggregations on the same input field without one silently replacing
        # another.  dropna=False keeps null-valued GroupBy keys, as Alteryx does.
        # Alteryx Count means the number of records in each group (including
        # nulls), whereas pandas "count" excludes null values.
        named_parts: list[str] = []
        for field, action, rename in aggs:
            if not field:
                continue
            action_lower = action.lower()
            pandas_action = "size" if action_lower == "count" else action_lower
            output_name = rename or f"{action}_{field}"
            named_parts.append(
                f"{py_str(output_name)}: ({py_str(field)}, {py_str(pandas_action)})"
            )
        named_agg_map = "{" + ", ".join(named_parts) + "}"
        return GeneratedCode(
            f"{df_out} = (\n"
            f"    {df_in}\n"
            f"    .groupby({group_str}, dropna=False)\n"
            f"    .agg(**{named_agg_map})\n"
            f"    .reset_index()\n"
            f")"
        )
    return GeneratedCode(
        f"{df_out} = {df_in}.groupby({group_str}).agg({{...}}) # TODO: set aggregations"
    )
