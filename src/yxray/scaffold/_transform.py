"""Single-input row transforms (Formula, Sort, Sample, Unique, RecordID).

Formula is the interesting one — it leans on alteryx_expr for expression
translation and preserves Alteryx's top-to-bottom formula semantics; the
rest are one-line pandas translations.
"""

from __future__ import annotations

from yxray.alteryx_expr import (
    ExprTranslation,
    ExprTranslationError,
    translate_expr,
)
from yxray.config_utils import (
    as_list,
    comment_safe,
    field_name,
    get_text,
    py_str,
    sort_field_rows,
)
from yxray.scaffold._common import (
    FIELD_RE,
    GeneratedCode,
    Requirement,
    ToolContext,
)


def _translate_expr(expr: str, df_var: str) -> tuple[ExprTranslation, bool]:
    """Translate an Alteryx expression to pandas.

    Falls back to plain [field] → df_var["field"] substitution when the
    expression uses syntax translate_expr does not understand. The bool
    is False on fallback — the substitution keeps untranslated Alteryx
    syntax (function names, operators) verbatim, so it looks like Python
    but is not runnable; callers must flag it, not just emit it.
    """
    try:
        return translate_expr(expr, df_var), True
    except ExprTranslationError:
        code = FIELD_RE.sub(lambda m: f"{df_var}[{py_str(m.group(1))}]", expr)
        return ExprTranslation(code=code, uses_numpy=False), False


def gen_formula(ctx: ToolContext) -> GeneratedCode:
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
        return GeneratedCode(f"{df_out} = {df_in}  # TODO: Formula — no fields found")
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
    uses_numpy = False
    for fname, expr in formulas:
        translation, ok = _translate_expr(expr, df_out)
        uses_numpy = uses_numpy or translation.uses_numpy
        if not ok:
            lines.append(
                f'# TODO: could not translate expression for "{comment_safe(fname)}"'
                f" — port manually: {comment_safe(expr)}"
            )
        lines.append(f"{df_out}[{py_str(fname)}] = {translation.code}")
    return GeneratedCode(
        "\n".join(lines),
        requirements=frozenset({Requirement.NUMPY}) if uses_numpy else frozenset(),
    )


def gen_sort(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    rows = sort_field_rows(ctx.config)
    if rows:
        fields = [r["@field"] for r in rows]
        orders = [r.get("@order", "Ascending").lower() != "descending" for r in rows]
        col_str = "[" + ", ".join(py_str(f) for f in fields) + "]"
        return GeneratedCode(
            f"{df_out} = {df_in}.sort_values({col_str}, ascending={orders})"
        )
    return GeneratedCode(
        f"{df_out} = {df_in}.sort_values([...])  # TODO: set sort fields"
    )


def gen_sample(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    for key in ("RecordLimit", "N", "@N"):
        val = ctx.config.get(key)
        if val:
            n = val.get("#text", "") if isinstance(val, dict) else str(val)
            if n:
                return GeneratedCode(f"{df_out} = {df_in}.head({n})")
    return GeneratedCode(f"{df_out} = {df_in}.head(...)  # TODO: set sample count")


def gen_recordid(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    field = get_text(ctx.config, "FieldName") or "RecordID"
    start_text = get_text(ctx.config, "StartValue")
    try:
        start = int(start_text) if start_text else 1
    except ValueError:
        start = 1
    return GeneratedCode(
        f"{df_out} = {df_in}.reset_index(drop=True)\n"
        f"{df_out}[{py_str(field)}] = {df_out}.index + {start}"
    )


def gen_unique(ctx: ToolContext) -> GeneratedCode:
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
        return GeneratedCode(f"{df_out} = {df_in}.drop_duplicates(subset={subset})")
    return GeneratedCode(f"{df_out} = {df_in}.drop_duplicates()")
