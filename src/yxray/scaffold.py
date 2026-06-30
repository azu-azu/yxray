"""Alteryx → Python scaffold generator.

scaffold(doc) returns a .py file string with one code block per tool,
in topological order. Supported tools get real (if partial) pandas code;
unsupported tools get a TODO comment.

Variable naming: df_{tool_id} — unambiguous and easy for the user to rename.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

from yxray.config_utils import as_list, field_name, first_text, select_field_rows
from yxray.models.workflow import WorkflowDoc
from yxray.topology import topo_order

__all__ = ["scaffold"]

# ── Alteryx expression → pandas translation ───────────────────────────────

_FIELD_RE = re.compile(r"\[([^\]]+)\]")
_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)


def _translate_expr(expr: str, df_var: str) -> str:
    """Replace [field] → df_var["field"] in Alteryx expressions."""
    return _FIELD_RE.sub(lambda m: f'{df_var}["{m.group(1)}"]', expr)


def _file_read(path: str) -> str:
    """Return `pd.read_excel` or `pd.read_csv` based on file extension."""
    ext = pathlib.Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f'pd.read_excel("{path}")'
    return f'pd.read_csv("{path}")'


def _file_write(path: str, df_var: str) -> str:
    ext = pathlib.Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f'{df_var}.to_excel("{path}", index=False)'
    return f'{df_var}.to_csv("{path}", index=False)'


# ── Connection helpers ─────────────────────────────────────────────────────


def _build_predecessor_map(doc: WorkflowDoc) -> dict[int, list[int]]:
    """All upstream tool_ids for each tool, in connection order."""
    preds: dict[int, list[int]] = {}
    for c in doc.connections:
        dst = int(c.dst_tool)
        preds.setdefault(dst, []).append(int(c.src_tool))
    return preds


def _build_anchor_map(doc: WorkflowDoc) -> dict[int, dict[str, int]]:
    """For each dst tool, map anchor name → src tool_id."""
    anchors: dict[int, dict[str, int]] = {}
    for c in doc.connections:
        dst = int(c.dst_tool)
        anchors.setdefault(dst, {})[c.dst_anchor] = int(c.src_tool)
    return anchors


def _dvar(tool_id: int) -> str:
    return f"df_{tool_id}"


# ── Per-tool code generators ───────────────────────────────────────────────


def _gen_input(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    _preds: list[int],
    _anchors: dict[str, int],
) -> str:
    path = first_text(config, "File", "FileName")
    if path:
        return f"{_dvar(tool_id)} = {_file_read(path)}"
    return f"{_dvar(tool_id)} = pd.read_csv(...)  # TODO: set file path"


def _gen_output(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    path = first_text(config, "File", "FileName")
    if path:
        return _file_write(path, df_in)
    return f"{df_in}.to_csv(...)  # TODO: set file path"


def _gen_filter(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
    expr = first_text(config, "Expression", "CustomFilterExpression")
    if expr:
        pandas_expr = _translate_expr(expr, df_in)
        return (
            f"# NOTE: Alteryx expression — review translation\n"
            f"{df_out} = {df_in}[{pandas_expr}]"
        )
    return f"{df_out} = {df_in}  # TODO: Filter expression missing"


def _gen_select(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
    rows = select_field_rows(config)
    selected = [
        field_name(r)
        for r in rows
        if isinstance(r, dict)
        and r.get("@selected", "True").lower() not in ("false",)
        and field_name(r)
    ]
    renames = {
        field_name(r): (r.get("@rename") or r.get("@Rename", ""))
        for r in rows
        if isinstance(r, dict)
        and field_name(r)
        and (r.get("@rename") or r.get("@Rename", ""))
        and (r.get("@rename") or r.get("@Rename", "")) != field_name(r)
    }
    if not selected:
        return f"{df_out} = {df_in}  # TODO: Select — no columns found"
    cols = "[" + ", ".join(f'"{c}"' for c in selected) + "]"
    if renames:
        rename_dict = "{" + ", ".join(f'"{k}": "{v}"' for k, v in renames.items()) + "}"
        return f"{df_out} = {df_in}[{cols}].rename(columns={rename_dict})"
    return f"{df_out} = {df_in}[{cols}]"


def _gen_formula(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
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
    note = "# NOTE: Alteryx expressions — review translation\n"
    if len(formulas) == 1:
        return f"{note}{df_out} = {df_in}.assign({assigns})"
    return f"{note}{df_out} = {df_in}.assign(\n    {assigns},\n)"


def _gen_join(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
) -> str:
    df_out = _dvar(tool_id)
    left_id = anchors.get("Left")
    right_id = anchors.get("Right")
    df_left = _dvar(left_id) if left_id else "df_left"
    df_right = _dvar(right_id) if right_id else "df_right"

    # Parse join keys from JoinExpression
    expr = first_text(config, "JoinExpression") or ""
    matches = _JOIN_COND_RE.findall(expr)

    # Also try JoinInfo style
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
    # Fallback — no keys parsed
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
) -> str:
    df_out = _dvar(tool_id)
    if not preds:
        return f"{df_out} = pd.concat([...], ignore_index=True)  # TODO: set inputs"
    parts = ", ".join(_dvar(p) for p in preds)
    return f"{df_out} = pd.concat([{parts}], ignore_index=True)"


def _gen_summarize(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
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
    return f"{df_out} = {df_in}.groupby({group_str}).agg({{...}})  # TODO: set aggregations"


def _gen_sort(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
    sort_info = config.get("SortInfo", {})
    if isinstance(sort_info, dict):
        sort_info = [sort_info] if sort_info else []
    if isinstance(sort_info, list) and sort_info:
        fields = [r.get("@field", "") for r in sort_info if isinstance(r, dict)]
        orders = [
            r.get("@order", "Ascending").lower() != "descending"
            for r in sort_info
            if isinstance(r, dict)
        ]
        if fields:
            col_str = "[" + ", ".join(f'"{f}"' for f in fields if f) + "]"
            asc_str = str([a for a, f in zip(orders, fields) if f])
            return f"{df_out} = {df_in}.sort_values({col_str}, ascending={asc_str})"
    return f"{df_out} = {df_in}.sort_values([...])  # TODO: set sort fields"


def _gen_sample(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    df_out = _dvar(tool_id)
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
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    return f"{_dvar(tool_id)} = {df_in}.drop_duplicates()"


# ── Generator registry ─────────────────────────────────────────────────────

_GENERATORS: dict[str, Any] = {
    "DbFileInput": _gen_input,
    "InputData": _gen_input,
    "TextInput": _gen_input,
    "DbFileOutput": _gen_output,
    "OutputData": _gen_output,
    "AlteryxFilter": _gen_filter,
    "Filter": _gen_filter,
    "AlteryxSelect": _gen_select,
    "Select": _gen_select,
    "AlteryxFormula": _gen_formula,
    "Formula": _gen_formula,
    "AlteryxJoin": _gen_join,
    "Join": _gen_join,
    "AlteryxUnion": _gen_union,
    "Union": _gen_union,
    "AlteryxAppend": _gen_union,
    "Append": _gen_union,
    "AlteryxSummarize": _gen_summarize,
    "Summarize": _gen_summarize,
    "AlteryxSort": _gen_sort,
    "Sort": _gen_sort,
    "AlteryxSample": _gen_sample,
    "Sample": _gen_sample,
    "Unique": _gen_unique,
}

# ── Public API ─────────────────────────────────────────────────────────────


def scaffold(doc: WorkflowDoc) -> str:
    """Return a Python scaffold string for the given workflow.

    Each tool becomes one annotated code block in topological order.
    Supported tools get semi-concrete pandas code; unsupported tools get
    a TODO comment block.
    """
    node_map = {int(n.tool_id): n for n in doc.nodes if "ToolContainer" not in n.tool_type}
    pred_map = _build_predecessor_map(doc)
    anchor_map = _build_anchor_map(doc)
    order = topo_order(doc)

    source = pathlib.Path(doc.filepath).name
    lines: list[str] = [
        f'"""Scaffold generated by yxray from {source}"""',
        "",
        "import pandas as pd",
        "",
    ]

    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue
        segment = node.tool_type.split(".")[-1]
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})

        # Section header
        lines.append(f"# {'─' * 68}")
        lines.append(f"# ToolID {tool_id}: {segment}")

        gen = _GENERATORS.get(segment)
        if gen is None:
            lines.append(f"# TODO: unsupported tool type — review manually")
            lines.append(f"# {_dvar(tool_id)} = ...")
            lines.append("")
            continue

        code = gen(tool_id, segment, node.config, preds, anchors)
        lines.append(code)
        lines.append("")

    return "\n".join(lines)
