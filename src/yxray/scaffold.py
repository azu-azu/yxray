"""Alteryx → Python scaffold generator.

scaffold(doc) returns a .py file string with one code block per tool,
in topological order. Supported tools get real (if partial) pandas code;
unsupported tools get a TODO comment.

Variable naming: each tool's output is named df<tool_id> (e.g. df34, df108),
matching the ToolID comment above each block so the mapping is unambiguous.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Any

from yxray.alteryx_expr import (
    ExprTranslationError,
    FilterTranslation,
    translate_expr,
    translate_filter_masks,
)
from yxray.config_utils import (
    as_list,
    field_name,
    first_text,
    operand_literal,
    select_field_rows,
    simple_filter_condition,
    sort_field_rows,
)
from yxray.models.workflow import WorkflowDoc
from yxray.tool_registry import (
    SCAFFOLD_APPENDFIELDS_SEGMENTS,
    SCAFFOLD_BROWSE_SEGMENTS,
    SCAFFOLD_CREATEPOINTS_SEGMENTS,
    SCAFFOLD_FILTER_SEGMENTS,
    SCAFFOLD_FINDREPLACE_SEGMENTS,
    SCAFFOLD_FORMULA_SEGMENTS,
    SCAFFOLD_INPUT_SEGMENTS,
    SCAFFOLD_JOIN_SEGMENTS,
    SCAFFOLD_OUTPUT_SEGMENTS,
    SCAFFOLD_SAMPLE_SEGMENTS,
    SCAFFOLD_SELECT_SEGMENTS,
    SCAFFOLD_SORT_SEGMENTS,
    SCAFFOLD_SPATIAL_SEGMENTS,
    SCAFFOLD_SPATIALMATCH_SEGMENTS,
    SCAFFOLD_SUMMARIZE_SEGMENTS,
    SCAFFOLD_TEXTINPUT_SEGMENTS,
    SCAFFOLD_UNION_SEGMENTS,
    SCAFFOLD_UNIQUE_SEGMENTS,
    tool_segment,
)
from yxray.topology import build_predecessor_map, topo_order

__all__ = [
    "ScaffoldBlock",
    "node_code_snippets",
    "scaffold",
    "scaffold_simple",
    "scaffold_simple_blocks",
]

# ── Alteryx expression → pandas translation ───────────────────────────────

_FIELD_RE = re.compile(r"\[([^\]]+)\]")
_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)
# Emissions of alteryx_expr that need "import numpy as np" in the preamble.
_NUMPY_RE = re.compile(r"\bnp\.(where|select|nan)\b")
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


def _translate_expr(expr: str, df_var: str) -> str:
    """Translate an Alteryx expression to pandas.

    Falls back to plain [field] → df_var["field"] substitution when the
    expression uses syntax translate_expr does not understand.
    """
    try:
        return translate_expr(expr, df_var)
    except ExprTranslationError:
        return _FIELD_RE.sub(lambda m: f'{df_var}["{m.group(1)}"]', expr)


_SPATIAL_EXTS = frozenset({".shp", ".geojson", ".gpkg", ".gdb"})


def _file_read(path_expr: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"pd.read_excel({path_expr})"
    if ext in _SPATIAL_EXTS:
        return f"gpd.read_file({path_expr})"
    return f"pd.read_csv({path_expr})"


def _file_write(path_expr: str, df_var: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"{df_var}.to_excel({path_expr}, index=False)"
    if ext in _SPATIAL_EXTS:
        return f"{df_var}.to_file({path_expr})"
    return f"{df_var}.to_csv({path_expr}, index=False)"


def _read_stmt(target: str, path: str | None, path_expr: str) -> str:
    """`target = pd.read_...(path_expr)`, or a TODO fallback when path is unset.

    Shared by scaffold() (path_expr → INPUTS[...]) and
    scaffold_simple_blocks() (path_expr → raw literal) so the extension
    dispatch and fallback wording live in one place.
    """
    if not path:
        return f"{target} = pd.read_csv(...)  # TODO: set file path"
    ext = pathlib.Path(path).suffix.lower()
    return f"{target} = {_file_read(path_expr, ext)}"


def _write_stmt(df_in: str, path: str | None, path_expr: str) -> str:
    """`df_in.to_...(path_expr)`, or a TODO fallback when path is unset.

    Counterpart to _read_stmt for the output side.
    """
    if not path:
        return f"{df_in}.to_csv(...)  # TODO: set file path"
    ext = pathlib.Path(path).suffix.lower()
    return _file_write(path_expr, df_in, ext)


# ── Connection helpers ─────────────────────────────────────────────────────



def _build_anchor_map(doc: WorkflowDoc) -> dict[int, dict[str, int]]:
    """For each dst tool, map anchor name → src tool_id."""
    anchors: dict[int, dict[str, int]] = {}
    for c in doc.connections:
        dst = int(c.dst_tool)
        anchors.setdefault(dst, {})[c.dst_anchor] = int(c.src_tool)
    return anchors


def _assign_frame_names(
    order: list[int],
    node_map: dict[int, Any],
) -> dict[int, str]:
    """Name each tool's output frame df<tool_id> (e.g. df34, df108).

    One-to-one with ToolIDs so variable names are stable, unambiguous,
    and never collide between inputs and outputs of the same operation.
    """
    return {tool_id: f"df{tool_id}" for tool_id in order if tool_id in node_map}


def _frame_name(
    names: dict[int, str],
    tool_id: int | None,
    fallback: str = "df_?",
) -> str:
    """Frame variable for a source tool, or a placeholder when unresolved."""
    if tool_id is None:
        return fallback
    return names.get(tool_id, fallback)


# ── Per-tool code generators ───────────────────────────────────────────────


def _gen_input(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    _preds: list[int],
    _anchors: dict[str, int],
    input_paths: dict[int, str],
    names: dict[int, str],
) -> str:
    path = input_paths.get(tool_id)
    return _read_stmt(names[tool_id], path, f'INPUTS["input_{tool_id}"]')


def _gen_output(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    output_paths: dict[int, str],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    path = output_paths.get(tool_id)
    return _write_stmt(df_in, path, f'OUTPUTS["output_{tool_id}"]')


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
    col = f'{df_var}["{field}"]'
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
        return f'{col}.str.contains("{operand}", regex=False, na=False)'
    if operator == "NotContains":
        return f'~{col}.str.contains("{operand}", regex=False, na=False)'
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
        lines.append(f"# {mask.fragment}")
        lines.append(f"cond_{i} = {mask.code}")
    joined = f" {translation.joiner} ".join(
        f"cond_{i}" for i in range(1, len(masks) + 1)
    )
    lines += ["", f"{df_out} = {df_in}[{joined}]"]
    return lines


def _fields_in_fragment(fragment: str) -> set[str]:
    return set(_FIELD_RE.findall(fragment))


def _date_columns_in_fragment(fragment: str) -> set[str]:
    return {
        m.group(1) or m.group(2) for m in _ADJACENT_DATE_RE.finditer(fragment)
    }


def _isempty_columns_in_fragment(fragment: str) -> set[str]:
    return set(_ISEMPTY_CALL_RE.findall(fragment))


def _isempty_dead_code_note(col: str, *, confident: bool) -> str:
    if confident:
        return (
            f'# NOTE: after conversion, IsEmpty\'s == "" check on "{col}"'
            ' always evaluates False — isna() alone is enough (it also'
            " catches NaT)."
        )
    return (
        f'# NOTE: if "{col}" needs pd.to_datetime conversion, its IsEmpty'
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
            lines.append(
                f'# WARNING: column "{col}" is compared as a date in'
                f" {where} — convert first:"
            )
            lines.append(
                f'# df["{col}"] = pd.to_datetime(df["{col}"], errors="coerce")'
            )
            if col in isempty_cols:
                lines.append(_isempty_dead_code_note(col, confident=True))
        for col in sorted(residual):
            lines.append(
                f"# WARNING: {where} involves a date comparison — verify"
                f' the type of column "{col}" too (mask-level heuristic).'
            )
            if col in isempty_cols:
                lines.append(_isempty_dead_code_note(col, confident=False))
    return lines


def _gen_filter(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    expr = first_text(config, "Expression", "CustomFilterExpression")
    if expr:
        translation: FilterTranslation | None
        try:
            translation = translate_filter_masks(expr, df_in)
            pandas_expr = translation.combined
        except ExprTranslationError:
            translation = None
            pandas_expr = _FIELD_RE.sub(
                lambda m: f'{df_in}["{m.group(1)}"]', expr
            )
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


# Select tools always carry this warning: the .yxmd XML keeps the Select
# state as of some earlier save, so it can silently disagree with what the
# Alteryx GUI actually shows (e.g. a field the GUI flags as "not found" /
# 見つかりません still looks like a regular entry in the XML).
_SELECT_STALE_XML_WARNING = (
    "# WARNING: Select XML may be stale (saved-state) and can differ from the\n"
    '# actual Select contents — fields shown as "not found" in the Alteryx GUI\n'
    "# may still appear here as regular entries. Always verify in the GUI."
)


def _gen_select(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    rows = select_field_rows(config)

    edits: list[tuple[str, str | None, bool]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = field_name(r)
        if not name:
            continue
        selected = r.get("@selected", "True").lower() not in ("false",)
        new_name: str | None = r.get("@rename") or r.get("@Rename") or None
        if new_name == name:
            new_name = None
        edits.append((name, new_name, selected))

    if not edits:
        return (
            f"{_SELECT_STALE_XML_WARNING}\n"
            f"{df_out} = {df_in}  # TODO: Select — no columns found"
        )

    only_unknown = (
        len(edits) == 1
        and edits[0][0] == "*Unknown"
        and edits[0][1] is None
        and edits[0][2] is True
    )
    unknown_deselected = any(
        name == "*Unknown" and not selected for name, _, selected in edits
    )

    var = f"_COLS_{tool_id}"
    col_lines: list[str] = [_SELECT_STALE_XML_WARNING]
    if only_unknown:
        col_lines.append(
            "# WARNING: Select only specifies *Unknown — no explicit column edits;"
            " likely a source-file issue (passthrough)"
        )
    if unknown_deselected:
        col_lines.append(
            "# WARNING: *Unknown=False — apply_select_edits keeps only explicitly"
            " selected columns; verify column list matches Alteryx output"
        )
    col_lines.append(f"{var} = [")
    for name, new_name, selected in edits:
        if not selected:
            col_lines.append(f'    SelectColumnEdit("{name}", selected=False),')
        elif new_name:
            col_lines.append(f'    SelectColumnEdit("{name}", new_name="{new_name}"),')
        else:
            col_lines.append(f'    SelectColumnEdit("{name}"),')
    col_lines.append("]")
    col_lines.append(f"{df_out} = apply_select_edits({df_in}, {var})")
    return "\n".join(col_lines)


def _gen_browse(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    return f'logger.info("ToolID {tool_id} (Browse): rows=%d", len({df_in}))'


def _gen_formula(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    ffs = config.get("FormulaFields", {})
    formulas: list[tuple[str, str]] = []
    if isinstance(ffs, dict):
        for item in as_list(ffs.get("FormulaField", [])):
            if not isinstance(item, dict):
                continue
            fname = item.get("@field", "") or item.get("@name", "")
            expr = (
                item.get("@expression", "")
                or item.get("@formula", "")
            )
            if fname and expr:
                formulas.append((fname, expr))
    if not formulas:
        return f"{df_out} = {df_in}  # TODO: Formula — no fields found"
    assigns = ",\n    ".join(
        f'{f} = {_translate_expr(e, df_in)}'
        for f, e in formulas
    )
    note = "# Alteryx expressions — review translation\n"
    if len(formulas) == 1:
        return f"{note}{df_out} = {df_in}.assign({assigns})"
    return f"{note}{df_out} = {df_in}.assign(\n    {assigns},\n)"


def _gen_join(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    left_id = anchors.get("Left")
    right_id = anchors.get("Right")
    df_left = _frame_name(names, left_id, "df_left")
    df_right = _frame_name(names, right_id, "df_right")

    expr = first_text(config, "JoinExpression") or ""
    matches = _JOIN_COND_RE.findall(expr)

    if not matches:
        join_info = config.get("JoinInfo", {})
        if isinstance(join_info, list):
            join_info = join_info[0] if join_info else {}
        if isinstance(join_info, dict):
            lk = join_info.get("@left", "") or join_info.get("@Left", "")
            rk = join_info.get("@right", "") or join_info.get("@Right", "")
            if lk and rk:
                matches = [(lk, rk)]

    if matches:
        if all(lk == rk for lk, rk in matches):
            keys = "[" + ", ".join(f'"{lk}"' for lk, _ in matches) + "]"
            return (
                f'{df_out} = pd.merge(\n'
                f'    {df_left}, {df_right},\n'
                f'    on={keys},\n'
                f'    how="inner",\n'
                f')'
            )
        lkeys = "[" + ", ".join(f'"{lk}"' for lk, _ in matches) + "]"
        rkeys = "[" + ", ".join(f'"{rk}"' for _, rk in matches) + "]"
        return (
            f'{df_out} = pd.merge(\n'
            f'    {df_left}, {df_right},\n'
            f'    left_on={lkeys},\n'
            f'    right_on={rkeys},\n'
            f'    how="inner",\n'
            f')'
        )
    return (
        f"# TODO: parse join condition: {expr or '(none)'}\n"
        f'{df_out} = pd.merge({df_left}, {df_right}, on=[...], how="inner")'
    )


def _gen_union(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    if not preds:
        return f"{df_out} = pd.concat([...], ignore_index=True)  # TODO: set inputs"
    parts = ", ".join(names.get(p, "df_?") for p in preds)
    return f"{df_out} = pd.concat([{parts}], ignore_index=True)"


def _gen_summarize(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    sf = config.get("SummarizeFields", {})
    if not isinstance(sf, dict):
        return f"{df_out} = {df_in}.groupby([...]).agg({{...}})  # TODO"
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
        return f"{df_out} = {df_in}.groupby([...]).agg({{...}})  # TODO"
    group_str = "[" + ", ".join(f'"{g}"' for g in groups if g) + "]"
    if aggs:
        agg_map = (
            "{"
            + ", ".join(
                f'"{field}": "{action.lower()}"' for field, action in aggs if field
            )
            + "}"
        )
        return (
            f"{df_out} = (\n"
            f"    {df_in}\n"
            f"    .groupby({group_str})\n"
            f"    .agg({agg_map})\n"
            f"    .reset_index()\n"
            f")"
        )
    return (
        f"{df_out} = {df_in}.groupby({group_str}).agg({{...}}) "
        "# TODO: set aggregations"
    )


def _gen_sort(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    rows = sort_field_rows(config)
    if rows:
        fields = [r["@field"] for r in rows]
        orders = [
            r.get("@order", "Ascending").lower() != "descending" for r in rows
        ]
        col_str = "[" + ", ".join(f'"{f}"' for f in fields) + "]"
        return f"{df_out} = {df_in}.sort_values({col_str}, ascending={orders})"
    return f"{df_out} = {df_in}.sort_values([...])  # TODO: set sort fields"


def _gen_sample(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    for key in ("RecordLimit", "N", "@N"):
        val = config.get(key)
        if val:
            n = val.get("#text", "") if isinstance(val, dict) else str(val)
            if n:
                return f"{df_out} = {df_in}.head({n})"
    return f"{df_out} = {df_in}.head(...)  # TODO: set sample count"


def _gen_unique(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    unique_fields = config.get("UniqueFields", {})
    field_names: list[str] = []
    if isinstance(unique_fields, dict):
        field_names = [
            field_name(f)
            for f in as_list(unique_fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    if field_names:
        subset = "[" + ", ".join(f'"{n}"' for n in field_names) + "]"
        return f"{df_out} = {df_in}.drop_duplicates(subset={subset})"
    return f"{df_out} = {df_in}.drop_duplicates()"


def _anchor_src(
    anchors: dict[str, int],
    preds: list[int],
    names: tuple[str, ...],
    index: int,
) -> int | None:
    """Src tool for a named input anchor, falling back to predecessor order."""
    for name in names:
        if name in anchors:
            return anchors[name]
    return preds[index] if len(preds) > index else None


def _gen_text_input(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    _preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    fields = config.get("Fields", {})
    field_names: list[str] = []
    if isinstance(fields, dict):
        field_names = [
            field_name(f)
            for f in as_list(fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    if not field_names:
        return f"{df_out} = pd.DataFrame(...)  # TODO: Text Input — no fields found"

    data = config.get("Data", {})
    rows: list[list[str]] = []
    for r in as_list(data.get("r")) if isinstance(data, dict) else []:
        if not isinstance(r, dict):
            continue
        cells: list[str] = []
        for c in as_list(r.get("c")) if "c" in r else []:
            if isinstance(c, dict):
                c = c.get("#text")
            cells.append("" if c is None else str(c))
        rows.append(cells)

    lines = [
        "# Text Input values are strings — cast dtypes if needed",
        f"{df_out} = pd.DataFrame({{",
    ]
    for i, name in enumerate(field_names):
        values = ", ".join(
            f'"{row[i]}"' if i < len(row) else '""' for row in rows
        )
        lines.append(f'    "{name}": [{values}],')
    lines.append("})")
    return "\n".join(lines)


def _gen_findreplace(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    # Alteryx FindReplace XML connection anchors: Targets = main stream (FieldFind),
    # Source = lookup table (FieldSearch). "F"/"R" are kept as fallbacks
    # for test fixtures.
    f_id = _anchor_src(anchors, preds, ("Targets", "F", "Find", "Input"), 0)
    r_id = _anchor_src(anchors, preds, ("Source", "R", "Replace"), 1)
    df_f = _frame_name(names, f_id, "df_find")
    df_r = _frame_name(names, r_id, "df_replace")

    field_find = first_text(config, "FieldFind")
    field_search = first_text(config, "FieldSearch")
    find_mode = first_text(config, "FindMode")
    replace_mode = first_text(config, "ReplaceMode")
    append_fields = config.get("ReplaceAppendFields", {})
    append_names: list[str] = []
    if isinstance(append_fields, dict):
        append_names = [
            field_name(f)
            for f in as_list(append_fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    rmf_raw = config.get("ReplaceMultipleFound", {})
    replace_multiple_found = not (
        isinstance(rmf_raw, dict) and rmf_raw.get("@value", "").lower() == "false"
    )

    whole_match = find_mode == "FindWhole" and bool(field_find and field_search)
    any_match = find_mode == "FindAny" and bool(field_find and field_search)

    if (whole_match or any_match) and replace_mode == "Append" and append_names:
        cols = ", ".join(f'"{n}"' for n in (field_search, *append_names))
        key = (
            f'    on="{field_find}",'
            if field_find == field_search
            else f'    left_on="{field_find}",\n    right_on="{field_search}",'
        )
        note = (
            "# Find Replace (append fields on whole match) as a left join"
            if whole_match
            else (
                "# Find Replace (FindAny — translated as left join;"
                " verify match semantics, incl. NaN/empty-string handling)"
            )
        )
        if any_match and not replace_multiple_found:
            lookup_var = f"_LOOKUP_{tool_id}"
            return (
                f"{note} — review translation\n"
                f"{lookup_var} = {df_r}[[{cols}]].drop_duplicates('{field_search}')\n"
                f"{df_out} = pd.merge(\n"
                f"    {df_f},\n"
                f"    {lookup_var},\n"
                f"{key}\n"
                f'    how="left",\n'
                f")"
            )
        guard = (
            f'if {df_r}["{field_search}"].duplicated().any():\n'
            f"    raise ValueError(\n"
            f"        \"Find & Replace lookup key '{field_search}' is not unique\"\n"
            f'        " — a left join would duplicate rows; verify Alteryx'
            f' semantics"\n'
            f"    )"
        )
        return (
            f"{note} — review translation\n"
            f"{guard}\n"
            f"{df_out} = pd.merge(\n"
            f"    {df_f},\n"
            f"    {df_r}[[{cols}]],\n"
            f"{key}\n"
            f'    how="left",\n'
            f")"
        )
    replace_field = first_text(config, "ReplaceFoundField")
    if whole_match and replace_field:
        map_var = f"_MAP_{tool_id}"
        return (
            "# Find Replace (whole match) via lookup map"
            " — review translation\n"
            f'{map_var} = dict(zip({df_r}["{field_search}"],'
            f' {df_r}["{replace_field}"]))\n'
            f"{df_out} = {df_f}.copy()\n"
            f'{df_out}["{field_find}"] = ('
            f'{df_out}["{field_find}"].map({map_var})'
            f'.fillna({df_out}["{field_find}"]))'
        )
    return (
        f"# TODO: Find Replace — mode '{find_mode or '?'}' not translated;"
        " review manually\n"
        f"{df_out} = {df_f}"
    )


def _gen_appendfields(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    t_id = _anchor_src(anchors, preds, ("Targets", "Target"), 0)
    s_id = _anchor_src(anchors, preds, ("Sources", "Source"), 1)
    df_t = _frame_name(names, t_id, "df_targets")
    df_s = _frame_name(names, s_id, "df_sources")
    return (
        "# Append Fields — every source record is appended"
        " to every target record\n"
        f'{df_out} = pd.merge({df_t}, {df_s}, how="cross")'
    )


def _gen_createpoints(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _frame_name(names, src)
    df_out = names[tool_id]
    fields = config.get("Fields", {})
    x = fields.get("@fieldX", "") if isinstance(fields, dict) else ""
    y = fields.get("@fieldY", "") if isinstance(fields, dict) else ""
    if x and y:
        return (
            "# spatial tool — requires geopandas\n"
            f"{df_out} = gpd.GeoDataFrame(\n"
            f"    {df_in},\n"
            f'    geometry=gpd.points_from_xy({df_in}["{x}"], {df_in}["{y}"]),\n'
            f'    crs="EPSG:4326",\n'
            f")"
        )
    return f"{df_out} = {df_in}  # TODO: Create Points — X/Y fields not found"


def _gen_spatialmatch(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    t_id = _anchor_src(anchors, preds, ("Targets", "Target"), 0)
    u_id = _anchor_src(anchors, preds, ("Universe",), 1)
    df_t = _frame_name(names, t_id, "df_targets")
    df_u = _frame_name(names, u_id, "df_universe")
    method = config.get("Method", {})
    method_name = method.get("@method", "") if isinstance(method, dict) else ""
    predicate = method_name.lower() if method_name else "intersects"
    return (
        "# spatial tool — requires geopandas;"
        " review predicate and output fields\n"
        f"{df_out} = gpd.sjoin(\n"
        f"    {df_t},\n"
        f"    {df_u},\n"
        f'    how="inner",\n'
        f'    predicate="{predicate}",\n'
        f")"
    )


# ── Generator registry ─────────────────────────────────────────────────────

_GENERATORS: dict[str, Any] = {
    **dict.fromkeys(SCAFFOLD_BROWSE_SEGMENTS, _gen_browse),
    **dict.fromkeys(SCAFFOLD_FILTER_SEGMENTS, _gen_filter),
    **dict.fromkeys(SCAFFOLD_SELECT_SEGMENTS, _gen_select),
    **dict.fromkeys(SCAFFOLD_FORMULA_SEGMENTS, _gen_formula),
    **dict.fromkeys(SCAFFOLD_JOIN_SEGMENTS, _gen_join),
    **dict.fromkeys(SCAFFOLD_UNION_SEGMENTS, _gen_union),
    **dict.fromkeys(SCAFFOLD_SUMMARIZE_SEGMENTS, _gen_summarize),
    **dict.fromkeys(SCAFFOLD_SORT_SEGMENTS, _gen_sort),
    **dict.fromkeys(SCAFFOLD_SAMPLE_SEGMENTS, _gen_sample),
    **dict.fromkeys(SCAFFOLD_UNIQUE_SEGMENTS, _gen_unique),
    **dict.fromkeys(SCAFFOLD_TEXTINPUT_SEGMENTS, _gen_text_input),
    **dict.fromkeys(SCAFFOLD_FINDREPLACE_SEGMENTS, _gen_findreplace),
    **dict.fromkeys(SCAFFOLD_APPENDFIELDS_SEGMENTS, _gen_appendfields),
    **dict.fromkeys(SCAFFOLD_CREATEPOINTS_SEGMENTS, _gen_createpoints),
    **dict.fromkeys(SCAFFOLD_SPATIALMATCH_SEGMENTS, _gen_spatialmatch),
}

# Segments whose scaffold snippet is self-contained enough to show as a
# single node's "python hint" (used by the inspect report's right pane).
# Excludes Input/Output (depend on file paths, which the panel already shows
# separately) and Text Input (would enumerate every data row — the panel
# shows the data).
_DETAIL_HINT_SEGMENTS = frozenset(_GENERATORS) - SCAFFOLD_TEXTINPUT_SEGMENTS


def node_code_snippets(doc: WorkflowDoc) -> dict[int, str]:
    """Per-node pandas code, identical to the .md Python Scaffold section.

    Only returns entries for tool_ids whose segment is in
    _DETAIL_HINT_SEGMENTS; callers should fall back to the generic
    python_hint for everything else.
    """
    node_map = {
        int(n.tool_id): n for n in doc.nodes if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    names = _assign_frame_names(topo_order(doc), node_map)

    snippets: dict[int, str] = {}
    for tool_id, node in node_map.items():
        segment = tool_segment(node.tool_type)
        if segment not in _DETAIL_HINT_SEGMENTS:
            continue
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})
        snippets[tool_id] = _GENERATORS[segment](
            tool_id, segment, node.config, preds, anchors, names
        )
    return snippets


# ── Scaffold section builders ──────────────────────────────────────────────


def _collect_metadata(
    node_map: dict[int, Any],
    order: list[int],
) -> tuple[dict[int, str], dict[int, str], bool, bool]:
    """Pre-pass: collect input/output paths and which helper imports are needed."""
    input_paths: dict[int, str] = {}
    output_paths: dict[int, str] = {}
    has_select = False
    has_spatial = False

    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        segment = tool_segment(node.tool_type)
        if segment in SCAFFOLD_INPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if path:
                input_paths[tool_id] = path
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if path:
                output_paths[tool_id] = path
        elif segment in SCAFFOLD_SELECT_SEGMENTS:
            has_select = True
        elif segment in SCAFFOLD_SPATIAL_SEGMENTS:
            has_spatial = True

    return input_paths, output_paths, has_select, has_spatial


def _emit_preamble(
    source: str,
    has_select: bool,
    has_spatial: bool,
    uses_numpy: bool,
) -> list[str]:
    lines: list[str] = [
        f'"""Scaffold generated by yxray from {source}"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if has_select:
        lines.append("from dataclasses import dataclass")
    lines += [
        "import logging",
        "import os",
        "from pathlib import Path",
        "",
    ]
    if has_spatial:
        lines.append("import geopandas as gpd")
    if uses_numpy:
        lines.append("import numpy as np")
    lines += [
        "import pandas as pd",
        "",
        "logger = logging.getLogger(__name__)",
    ]
    return lines


def _emit_paths_block(
    input_paths: dict[int, str],
    output_paths: dict[int, str],
) -> list[str]:
    if not (input_paths or output_paths):
        return []

    lines: list[str] = [
        "",
        'ENV = os.getenv("APP_ENV", "test")',
        "",
        "# ── Paths ─────────────────────────────────────────────────────────────",
        "",
        'if ENV == "test":',
        "    BASE_DIR = Path(__file__).resolve().parents[2]",
    ]
    if input_paths:
        lines += ["", "    INPUTS = {"]
        for tid, path in input_paths.items():
            fname = pathlib.PureWindowsPath(path).name
            lines.append(f'        "input_{tid}": BASE_DIR / "input" / "{fname}",')
        lines.append("    }")
    if output_paths:
        lines += ["", "    OUTPUTS = {"]
        for tid, path in output_paths.items():
            fname = pathlib.PureWindowsPath(path).name
            lines.append(f'        "output_{tid}": BASE_DIR / "output" / "{fname}",')
        lines.append("    }")
    lines += ["", 'elif ENV == "prod":']
    if input_paths:
        lines.append("    INPUTS = {")
        for tid, path in input_paths.items():
            lines.append(f'        "input_{tid}": Path(r"{path}"),')
        lines.append("    }")
    if output_paths:
        if input_paths:
            lines.append("")
        lines.append("    OUTPUTS = {")
        for tid, path in output_paths.items():
            lines.append(f'        "output_{tid}": Path(r"{path}"),')
        lines.append("    }")
    lines += [
        "",
        "else:",
        '    raise ValueError(f"Unknown ENV: {ENV}")',
    ]
    return lines


def _emit_select_helpers() -> list[str]:
    return [
        "",
        "",
        "@dataclass(frozen=True)",
        "class SelectColumnEdit:",
        "    name: str",
        "    new_name: str | None = None",
        "    selected: bool = True",
        "",
        "",
        "def apply_select_edits(",
        "        df: pd.DataFrame,",
        "        columns: list[SelectColumnEdit],",
        ") -> pd.DataFrame:",
        '    wildcard = next((c for c in columns if c.name == "*Unknown"), None)',
        '    explicit = [c for c in columns if c.name != "*Unknown"]',
        "    if wildcard is not None and not wildcard.selected:",
        "        keep = [",
        "            c.name for c in explicit",
        "            if c.selected and c.name in df.columns",
        "        ]",
        "        df = df[keep]",
        "    else:",
        "        drop = {c.name for c in explicit if not c.selected} & set(df.columns)",
        "        df = df.drop(columns=drop)",
        "    rename_map = {",
        "        c.name: c.new_name",
        "        for c in explicit",
        "        if c.selected and c.new_name and c.name in df.columns",
        "    }",
        "    return df.rename(columns=rename_map)",
    ]


def _emit_main_body(
    order: list[int],
    node_map: dict[int, Any],
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
    input_paths: dict[int, str],
    output_paths: dict[int, str],
    names: dict[int, str],
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> list[str]:
    body: list[str] = []
    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        segment = tool_segment(node.tool_type)
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})

        body.append(f"# {'─' * 68}")
        body.append(f"# ToolID {tool_id}: {segment}")
        for msg in (warnings_by_tool or {}).get(tool_id, []):
            body.append(f"# WARNING: {msg}")

        if segment in SCAFFOLD_INPUT_SEGMENTS:
            code = _gen_input(
                tool_id, segment, node.config, preds, anchors, input_paths, names
            )
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            code = _gen_output(
                tool_id, segment, node.config, preds, anchors, output_paths, names
            )
        else:
            gen = _GENERATORS.get(segment)
            if gen is None:
                body.append("# TODO: unsupported tool type — review manually")
                body.append(f"# {names[tool_id]} = ...")
                body.append("")
                continue
            code = gen(tool_id, segment, node.config, preds, anchors, names)

        body.extend(code.split("\n"))
        body.append("")

    return ["    " + line if line else "" for line in body]


# ── Public API ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScaffoldBlock:
    """One tool's chunk of the simple scaffold: header comments + code."""

    tool_id: int
    segment: str
    lines: list[str]


def scaffold_simple_blocks(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> tuple[list[str], list[ScaffoldBlock]]:
    """Return (header_lines, per-tool blocks) for the flat scaffold.

    Same content as scaffold_simple(), but structured per tool so callers
    (the .md writer) can interleave other material — e.g. the original
    <Node> XML — between tool blocks.
    """
    node_map = {
        int(n.tool_id): n
        for n in doc.nodes
        if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    order = topo_order(doc)
    source = pathlib.Path(doc.filepath).name
    names = _assign_frame_names(order, node_map)
    has_spatial = any(
        tool_segment(node.tool_type) in SCAFFOLD_SPATIAL_SEGMENTS
        for node in node_map.values()
    )
    has_browse = any(
        tool_segment(node.tool_type) in SCAFFOLD_BROWSE_SEGMENTS
        for node in node_map.values()
    )

    blocks: list[ScaffoldBlock] = []

    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        segment = tool_segment(node.tool_type)
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})

        lines: list[str] = [f"# {'─' * 68}", f"# ToolID {tool_id}: {segment}"]
        for msg in (warnings_by_tool or {}).get(tool_id, []):
            lines.append(f"# WARNING: {msg}")

        if segment in SCAFFOLD_INPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            code = _read_stmt(names[tool_id], path, f'r"{path}"' if path else "")
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            src = preds[0] if preds else None
            df_in = _frame_name(names, src)
            path = first_text(node.config, "File", "FileName")
            code = _write_stmt(df_in, path, f'r"{path}"' if path else "")
        else:
            gen = _GENERATORS.get(segment)
            if gen is None:
                lines.append("# TODO: unsupported tool type — review manually")
                lines.append(f"# {names[tool_id]} = ...")
                blocks.append(ScaffoldBlock(tool_id, segment, lines))
                continue
            code = gen(tool_id, segment, node.config, preds, anchors, names)

        lines.append(code)
        blocks.append(ScaffoldBlock(tool_id, segment, lines))

    header: list[str] = [
        f'"""Scaffold generated by yxray from {source}"""',
        "",
    ]
    if has_browse:
        header += ["import logging", ""]
    if has_spatial:
        header.append("import geopandas as gpd")
    if any(
        _NUMPY_RE.search(line) for block in blocks for line in block.lines
    ):
        header.append("import numpy as np")
    header += [
        "import pandas as pd",
        "",
    ]
    if has_browse:
        header += ["logger = logging.getLogger(__name__)", ""]
    return header, blocks


def scaffold_simple(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> str:
    """Return a flat Python scaffold without ENV/paths block or main() wrapper.

    Used for .md display: shows tool-by-tool code in topological order with
    raw file paths, without the project-level boilerplate added to .py files.
    """
    header, blocks = scaffold_simple_blocks(doc, warnings_by_tool=warnings_by_tool)
    lines = list(header)
    for block in blocks:
        lines.extend(block.lines)
        lines.append("")
    return "\n".join(lines)


def scaffold(
    doc: WorkflowDoc,
    warnings_by_tool: dict[int, list[str]] | None = None,
) -> str:
    """Return a Python scaffold string for the given workflow.

    Each tool becomes one annotated code block in topological order.
    Supported tools get semi-concrete pandas code; unsupported tools get
    a TODO comment block.
    """
    node_map = {
        int(n.tool_id): n
        for n in doc.nodes
        if "ToolContainer" not in n.tool_type
    }
    pred_map = build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    order = topo_order(doc)
    source = pathlib.Path(doc.filepath).name

    input_paths, output_paths, has_select, has_spatial = _collect_metadata(
        node_map, order
    )

    names = _assign_frame_names(order, node_map)
    body = _emit_main_body(
        order, node_map, pred_map, anchor_map, input_paths, output_paths, names,
        warnings_by_tool=warnings_by_tool,
    )
    uses_numpy = any(_NUMPY_RE.search(line) for line in body)

    lines = _emit_preamble(source, has_select, has_spatial, uses_numpy)
    lines += _emit_paths_block(input_paths, output_paths)
    if has_select:
        lines += _emit_select_helpers()
    lines += ["", "", "def main() -> None:"]
    lines += body
    lines += [
        "",
        "",
        'if __name__ == "__main__":',
        "    logging.basicConfig(level=logging.INFO)",
        "    main()",
    ]

    return "\n".join(lines)
