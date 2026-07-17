"""Aggregation tools (Summarize) for the scaffold generator."""

from __future__ import annotations

from yxray.config_utils import as_list, py_str
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
        (r.get("@field", ""), r.get("@action", ""))
        for r in rows
        if isinstance(r, dict) and r.get("@action", "").lower() != "groupby"
    ]
    if not groups and not aggs:
        return GeneratedCode(f"{df_out} = {df_in}.groupby([...]).agg({{...}})  # TODO")
    group_str = "[" + ", ".join(py_str(g) for g in groups if g) + "]"
    if aggs:
        agg_map = (
            "{"
            + ", ".join(
                f"{py_str(field)}: {py_str(action.lower())}"
                for field, action in aggs
                if field
            )
            + "}"
        )
        return GeneratedCode(
            f"{df_out} = (\n"
            f"    {df_in}\n"
            f"    .groupby({group_str})\n"
            f"    .agg({agg_map})\n"
            f"    .reset_index()\n"
            f")"
        )
    return GeneratedCode(
        f"{df_out} = {df_in}.groupby({group_str}).agg({{...}}) # TODO: set aggregations"
    )
