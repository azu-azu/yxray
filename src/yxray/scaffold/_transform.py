"""Single-input row transforms (Formula, Sort, Sample, Unique).

Formula is the interesting one — it leans on alteryx_expr for expression
translation and preserves Alteryx's top-to-bottom formula semantics; the
rest are one-line pandas translations.
"""

from __future__ import annotations

from yxray.alteryx_expr import ExprTranslationError, translate_expr
from yxray.config_utils import as_list, field_name, py_str, sort_field_rows
from yxray.scaffold._common import FIELD_RE, ToolContext


def _translate_expr(expr: str, df_var: str) -> str:
    """Translate an Alteryx expression to pandas.

    Falls back to plain [field] → df_var["field"] substitution when the
    expression uses syntax translate_expr does not understand.
    """
    try:
        return translate_expr(expr, df_var)
    except ExprTranslationError:
        return FIELD_RE.sub(lambda m: f"{df_var}[{py_str(m.group(1))}]", expr)


def gen_formula(ctx: ToolContext) -> str:
    df_in = ctx.df_in
    df_out = ctx.df_out
    ffs = ctx.config.get("FormulaFields", {})
    formulas: list[tuple[str, str]] = []
    if isinstance(ffs, dict):
        for item in as_list(ffs.get("FormulaField", [])):
            if not isinstance(item, dict):
                continue
            fname = item.get("@field", "") or item.get("@name", "")
            expr = item.get("@expression", "") or item.get("@formula", "")
            if fname and expr:
                formulas.append((fname, expr))
    if not formulas:
        return f"{df_out} = {df_in}  # TODO: Formula — no fields found"
    # Build df_out up one column at a time rather than with a single
    # .assign(). Two reasons: Alteryx applies formulas top to bottom and a
    # later one may reference a column an earlier one just created (an
    # .assign() expression would evaluate against the original frame and
    # KeyError); and subscript assignment keys are strings, so field names
    # that aren't valid Python identifiers (e.g. "Sales Amount", "2020")
    # work — as .assign() keyword arguments they'd be a SyntaxError.
    lines = [
        "# Alteryx Formula — applied top to bottom; review translation",
        f"{df_out} = {df_in}.copy()",
    ]
    for fname, expr in formulas:
        lines.append(f"{df_out}[{py_str(fname)}] = {_translate_expr(expr, df_out)}")
    return "\n".join(lines)


def gen_sort(ctx: ToolContext) -> str:
    df_in = ctx.df_in
    df_out = ctx.df_out
    rows = sort_field_rows(ctx.config)
    if rows:
        fields = [r["@field"] for r in rows]
        orders = [r.get("@order", "Ascending").lower() != "descending" for r in rows]
        col_str = "[" + ", ".join(py_str(f) for f in fields) + "]"
        return f"{df_out} = {df_in}.sort_values({col_str}, ascending={orders})"
    return f"{df_out} = {df_in}.sort_values([...])  # TODO: set sort fields"


def gen_sample(ctx: ToolContext) -> str:
    df_in = ctx.df_in
    df_out = ctx.df_out
    for key in ("RecordLimit", "N", "@N"):
        val = ctx.config.get(key)
        if val:
            n = val.get("#text", "") if isinstance(val, dict) else str(val)
            if n:
                return f"{df_out} = {df_in}.head({n})"
    return f"{df_out} = {df_in}.head(...)  # TODO: set sample count"


def gen_unique(ctx: ToolContext) -> str:
    df_in = ctx.df_in
    df_out = ctx.df_out
    unique_fields = ctx.config.get("UniqueFields", {})
    field_names: list[str] = []
    if isinstance(unique_fields, dict):
        field_names = [
            field_name(f)
            for f in as_list(unique_fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    if field_names:
        subset = "[" + ", ".join(py_str(n) for n in field_names) + "]"
        return f"{df_out} = {df_in}.drop_duplicates(subset={subset})"
    return f"{df_out} = {df_in}.drop_duplicates()"
