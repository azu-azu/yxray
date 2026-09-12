"""Single-input row transforms (Formula, Sort, Sample, Unique, RecordID,
Multi-Row Formula).

Formula is the interesting one — it leans on alteryx_expr for expression
translation and preserves Alteryx's top-to-bottom formula semantics; the
rest are one-line pandas translations.
"""

from __future__ import annotations

import re
from typing import Any

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
    FILL_EMPTY_NOTE_LINES,
    TOSTRING_FORMAT_WARNING_LINES,
    GeneratedCode,
    Requirement,
    ToolContext,
    fallback_field_substitute,
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
        code = fallback_field_substitute(expr, df_var)
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
    body: list[str] = []
    uses_numpy = False
    uses_fill_empty = False
    uses_tostring_format = False
    for fname, expr in formulas:
        translation, ok = _translate_expr(expr, df_out)
        uses_numpy = uses_numpy or translation.uses_numpy
        uses_fill_empty = uses_fill_empty or translation.uses_fill_empty
        uses_tostring_format = uses_tostring_format or translation.uses_tostring_format
        if not ok:
            body.append(
                f'# TODO: could not translate expression for "{comment_safe(fname)}"'
                f" — port manually: {comment_safe(expr)}"
            )
        body.append(f"{df_out}[{py_str(fname)}] = {translation.code}")
    # The helper NOTE goes above the block, so it is read before the call —
    # which is why the body is built first and the header assembled after.
    lines = ["# Alteryx Formula — applied top to bottom; review translation"]
    if uses_fill_empty:
        lines += FILL_EMPTY_NOTE_LINES
    if uses_tostring_format:
        lines += TOSTRING_FORMAT_WARNING_LINES
    lines.append(f"{df_out} = {df_in}.copy()")
    lines += body
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


def gen_countrecords(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    return GeneratedCode(f'{df_out} = pd.DataFrame({{"Count": [len({df_in})]}})')


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
        return GeneratedCode(
            "# Alteryx's Unique tool sorts by the Unique fields first, then\n"
            "# keeps the first row of each group (confirmed by Alteryx's own\n"
            "# help for the Unique tool) — drop_duplicates() alone keeps input\n"
            '# order and never sorts. kind="stable" keeps which row survives\n'
            "# unchanged (a stable sort preserves same-key rows' original\n"
            "# relative order, so drop_duplicates() still picks the same one)\n"
            "# and only changes the final row order to match Alteryx's sorted\n"
            '# output. na_position="first" matches Alteryx\'s Sort default.\n'
            f"{df_out} = (\n"
            f"    {df_in}\n"
            f'    .sort_values(by={subset}, kind="stable", na_position="first")\n'
            f"    .drop_duplicates(subset={subset})\n"
            "    .reset_index(drop=True)\n"
            ")"
        )
    return GeneratedCode(f"{df_out} = {df_in}.drop_duplicates()")


# Multi-Row Formula stayed unpromoted (commit 56b34d5) for lack of real XML,
# and 10 real nodes across one workflow confirm that caution was right: the
# Expression field is genuinely free-form (adjacent-row comparisons building
# XML/KML strings, UpdateField=True overwrites of an existing column, etc.)
# — no single snippet covers it. Exactly one shape recurs identically twice
# in that corpus and has a closed pandas form: [Row-1:<CreateField_Name>]+1
# with OtherRows=Empty, a self-referential running-counter idiom. Alteryx's
# own help for "Values for Rows That Don't Exist" confirms Empty means an
# out-of-range Row-N reads as 0 for a numeric field, so the recurrence
# resolves to "1, 2, 3, ... per group" — exactly groupby(...).cumcount()+1,
# no actual row-by-row recursion needed. Everything else — a different
# field/other rows' reference, more than one Row-N term, UpdateField=True,
# any OtherRows other than Empty — is a free-form recurrence pandas can't
# vectorize the same way, so it stays an explicit TODO like Distance's
# Direction or Buffer's fixed-size mode.
_MULTIROWFORMULA_COUNTER_RE = re.compile(r"^\[Row-1:(.+?)\]\s*\+\s*1$")

_MULTIROWFORMULA_COUNTER_NOTE = (
    "# [Row-1:<field>]+1 with OtherRows=Empty is Alteryx's per-group running-\n"
    "# counter idiom: an out-of-range Row-1 (the first row of a group) reads\n"
    "# as 0 for a numeric field (Alteryx help, \"Values for Rows That Don't\n"
    '# Exist" = 0 or Empty), so the recurrence is "1, 2, 3, ..." per group —\n'
    "# a closed form (groupby().cumcount()) covers it without an actual\n"
    "# row-by-row recurrence. Any other Multi-Row Formula shape (a different\n"
    "# field or other rows' reference, UpdateField=True, non-Empty OtherRows)\n"
    "# is a free-form recurrence this does not attempt to translate."
)


def _multirowformula_group_fields(config: dict[str, Any]) -> list[str]:
    """Field names under <GroupByFields><Field field="..."/></GroupByFields>."""
    group = config.get("GroupByFields", {})
    if not isinstance(group, dict):
        return []
    return [
        field_name(f)
        for f in as_list(group.get("Field"))
        if isinstance(f, dict) and field_name(f)
    ]


def _multirowformula_todo(reason: str, df_in: str, df_out: str) -> GeneratedCode:
    return GeneratedCode(
        f"# TODO: Multi-Row Formula — {comment_safe(reason)}\n{df_out} = {df_in}"
    )


def gen_multirowformula(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    config = ctx.config
    create_field = get_text(config, "CreateField_Name")
    update_field = config.get("UpdateField", {})
    updates_existing = (
        isinstance(update_field, dict)
        and str(update_field.get("@value", "")).lower() == "true"
    )
    other_rows = get_text(config, "OtherRows")
    expr = get_text(config, "Expression").strip()
    group_fields = _multirowformula_group_fields(config)

    if updates_existing:
        return _multirowformula_todo(
            "UpdateField=True overwrites an existing field with a free-form"
            " expression — not translated",
            df_in,
            df_out,
        )
    if not create_field:
        return _multirowformula_todo("no CreateField_Name found", df_in, df_out)
    if other_rows != "Empty":
        return _multirowformula_todo(
            f"OtherRows={other_rows!r} is not translated — only Empty (0 for"
            " an out-of-range numeric row, confirmed by Alteryx's help) is",
            df_in,
            df_out,
        )
    match = _MULTIROWFORMULA_COUNTER_RE.match(expr)
    if not match or match.group(1) != create_field:
        return _multirowformula_todo(
            "expression is not the recognized [Row-1:<field>]+1 running-"
            f"counter idiom: {comment_safe(expr)}",
            df_in,
            df_out,
        )

    requirements: frozenset[Requirement]
    if group_fields:
        subset = "[" + ", ".join(py_str(f) for f in group_fields) + "]"
        counter = f"{df_in}.groupby({subset}).cumcount() + 1"
        requirements = frozenset()
    else:
        counter = f"np.arange(1, len({df_in}) + 1)"
        requirements = frozenset({Requirement.NUMPY})
    return GeneratedCode(
        f"{_MULTIROWFORMULA_COUNTER_NOTE}\n"
        f"{df_out} = {df_in}.copy()\n"
        f'{df_out}[{py_str(create_field)}] = ({counter}).astype("int32")',
        requirements=requirements,
    )
