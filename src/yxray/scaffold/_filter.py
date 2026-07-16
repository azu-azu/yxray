"""Filter tool → pandas translation for the scaffold generator.

Alteryx's Filter tool has grown its own translation subsystem, distinct
from the other per-tool generators:

* Simple-mode conditions → pandas boolean expressions.
* Expression-mode conditions → pandas, via alteryx_expr.
* Splitting a multi-condition Expression filter into named cond_N masks.
* Detecting date comparisons (CSV columns load as strings) and emitting
  pd.to_datetime conversion warnings, split into precise vs. residual
  columns.
* Detecting the IsEmpty-vs-datetime contradiction (IsEmpty's == "" half
  goes dead once a column is coerced to datetime) and noting it.

Only gen_filter is called by the generator registry; the rest are its
internals (a few are also imported by tests).
"""

from __future__ import annotations

import re
from typing import Any

from yxray.alteryx_expr import (
    ExprTranslationError,
    FilterTranslation,
    translate_filter_masks,
)
from yxray.config_utils import (
    comment_safe,
    first_text,
    operand_literal,
    py_str,
    simple_filter_condition,
)
from yxray.scaffold._common import FIELD_RE, ToolContext

# Translated filter expressions that compare against datetime values;
# CSV-loaded columns are strings, so warn about the dtype mismatch.
_DATE_EXPR_RE = re.compile(r"\bpd\.(to_datetime|Timestamp|DateOffset)\b")
# [col] adjacent to a ToDate/DateTime* call across a comparison operator,
# in either order — the column that is actually being date-compared.
# Multi-char operators must precede their single-char prefix (>= before >)
# so the alternation doesn't consume just the prefix.
_ADJACENT_DATE_RE = re.compile(
    r"\[([^\]]+)\]\s*(?:>=|<=|==|!=|>|<)\s*(?:ToDate|DateTime)\w*"
    r"|(?:ToDate|DateTime)\w*\([^()]*\)\s*(?:>=|<=|==|!=|>|<)\s*\[([^\]]+)\]",
    re.IGNORECASE,
)
# IsEmpty([col]) specifically — not IsNull([col]): IsNull translates to
# .isna() alone (still valid after pd.to_datetime coercion), but IsEmpty
# translates to isna() | (col == ""), whose == "" half goes dead once the
# column is converted to datetime.
_ISEMPTY_CALL_RE = re.compile(r"IsEmpty\s*\(\s*\[([^\]]+)\]", re.IGNORECASE)


_SIMPLE_FILTER_OPS = {
    "=": "==",
    "!=": "!=",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
}


def _simple_filter_pandas(config: dict[str, Any], df_var: str) -> str:
    """Pandas boolean expression for a Simple-mode Filter, or ""."""
    cond = simple_filter_condition(config)
    if cond is None:
        return ""
    field, operator, operand = cond
    col = f"{df_var}[{py_str(field)}]"
    if operator == "IsNull":
        return f"{col}.isna()"
    if operator == "IsNotNull":
        return f"{col}.notna()"
    if operator == "IsEmpty":
        return f'({col}.isna() | ({col} == ""))'
    if operator == "IsNotEmpty":
        return f'({col}.notna() & ({col} != ""))'
    # Alteryx Contains is a literal (non-regex) substring match: regex=False.
    if operator == "Contains":
        return f"{col}.str.contains({py_str(operand)}, regex=False, na=False)"
    if operator == "NotContains":
        return f"~{col}.str.contains({py_str(operand)}, regex=False, na=False)"
    op = _SIMPLE_FILTER_OPS.get(operator)
    if op is None:
        return ""
    return f"{col} {op} {operand_literal(operand)}"


# Split an Expression-mode Filter into named masks when the top-level
# AND/OR chain has this many operands or more; with exactly 2 operands,
# split only when the one-line form exceeds _MASK_SPLIT_LINE_LIMIT.
_MASK_SPLIT_MIN_OPERANDS = 3
_MASK_SPLIT_LINE_LIMIT = 88  # ruff line-length


def _filter_mask_lines(
    translation: FilterTranslation,
    df_in: str,
    df_out: str,
) -> list[str] | None:
    """Split-form lines for an Expression Filter, or None to keep one line.

    Two-pass rule (mechanical, so output stays stable): 3+ top-level
    operands always split; exactly 2 split only when the rendered
    one-line form exceeds the line-length limit as generated (the .py
    scaffold's main() indent is not counted).
    """
    masks = translation.masks
    if len(masks) < 2:
        return None
    if len(masks) < _MASK_SPLIT_MIN_OPERANDS:
        one_line = f"{df_out} = {df_in}[{translation.combined}]"
        if len(one_line) <= _MASK_SPLIT_LINE_LIMIT:
            return None
    lines: list[str] = []
    for i, mask in enumerate(masks, 1):
        lines.append(f"# {comment_safe(mask.fragment)}")
        lines.append(f"cond_{i} = {mask.code}")
    joined = f" {translation.joiner} ".join(
        f"cond_{i}" for i in range(1, len(masks) + 1)
    )
    lines += ["", f"{df_out} = {df_in}[{joined}]"]
    return lines


def _fields_in_fragment(fragment: str) -> set[str]:
    return set(FIELD_RE.findall(fragment))


def _date_columns_in_fragment(fragment: str) -> set[str]:
    return {m.group(1) or m.group(2) for m in _ADJACENT_DATE_RE.finditer(fragment)}


def _isempty_columns_in_fragment(fragment: str) -> set[str]:
    return set(_ISEMPTY_CALL_RE.findall(fragment))


def _isempty_dead_code_note(col: str, *, confident: bool) -> str:
    name = comment_safe(col)
    if confident:
        return (
            f'# NOTE: after conversion, IsEmpty\'s == "" check on "{name}"'
            " always evaluates False — isna() alone is enough (it also"
            " catches NaT)."
        )
    return (
        f'# NOTE: if "{name}" needs pd.to_datetime conversion, its IsEmpty'
        ' == "" check becomes always False afterward — isna() alone is'
        " enough."
    )


def _filter_date_warning_lines(
    translation: FilterTranslation, *, split: bool
) -> list[str]:
    """Per-column date-conversion warnings, split into precise vs. residual.

    A mask matching a date function (_DATE_EXPR_RE on its translated code)
    contributes two tiers of warning: columns the adjacent-pattern regex
    can name with confidence, and the mask's remaining columns named more
    tentatively. The residual tier matters because one side of a
    column-vs-column comparison (e.g. `[A] >= [B]` where only `A` is also
    compared against a literal date elsewhere) would otherwise go
    unwarned even though it needs the same dtype conversion.
    """
    isempty_cols: set[str] = set()
    for mask in translation.masks:
        isempty_cols |= _isempty_columns_in_fragment(mask.fragment)

    lines: list[str] = []
    for i, mask in enumerate(translation.masks, 1):
        if not _DATE_EXPR_RE.search(mask.code):
            continue
        where = f"cond_{i}" if split else "this filter"
        precise = _date_columns_in_fragment(mask.fragment)
        residual = _fields_in_fragment(mask.fragment) - precise
        for col in sorted(precise):
            name = comment_safe(col)
            lines.append(
                f'# WARNING: column "{name}" is compared as a date in'
                f" {where} — convert first:"
            )
            lines.append(
                f'# df["{name}"] = pd.to_datetime(df["{name}"], errors="coerce")'
            )
            if col in isempty_cols:
                lines.append(_isempty_dead_code_note(col, confident=True))
        for col in sorted(residual):
            name = comment_safe(col)
            lines.append(
                f"# WARNING: {where} involves a date comparison — verify"
                f' the type of column "{name}" too (mask-level heuristic).'
            )
            if col in isempty_cols:
                lines.append(_isempty_dead_code_note(col, confident=False))
    return lines


def gen_filter(ctx: ToolContext) -> str:
    config = ctx.config
    df_in = ctx.df_in
    df_out = ctx.df_out
    expr = first_text(config, "Expression", "CustomFilterExpression")
    if expr:
        translation: FilterTranslation | None
        try:
            translation = translate_filter_masks(expr, df_in)
            pandas_expr = translation.combined
        except ExprTranslationError:
            translation = None
            pandas_expr = FIELD_RE.sub(lambda m: f"{df_in}[{py_str(m.group(1))}]", expr)
        lines = ["# Alteryx expression — review translation"]
        if _DATE_EXPR_RE.search(pandas_expr):
            lines += [
                "# WARNING: date comparison — columns read from CSV are"
                " strings; convert",
                '# first: df[col] = pd.to_datetime(df[col], errors="coerce")',
            ]
        mask_lines = (
            _filter_mask_lines(translation, df_in, df_out)
            if translation is not None
            else None
        )
        if translation is not None:
            lines += _filter_date_warning_lines(
                translation, split=mask_lines is not None
            )
        if mask_lines is not None:
            lines += mask_lines
        else:
            lines.append(f"{df_out} = {df_in}[{pandas_expr}]")
        return "\n".join(lines)
    simple_expr = _simple_filter_pandas(config, df_in)
    if simple_expr:
        return (
            "# from Simple-mode filter settings — review translation\n"
            f"{df_out} = {df_in}[{simple_expr}]"
        )
    return f"{df_out} = {df_in}  # TODO: Filter expression missing"
