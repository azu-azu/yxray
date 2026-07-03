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

from yxray.config_utils import (
    as_list,
    field_name,
    first_text,
    operand_literal,
    select_field_rows,
    simple_filter_condition,
)
from yxray.models.workflow import WorkflowDoc
from yxray.tool_registry import (
    SCAFFOLD_FILTER_SEGMENTS,
    SCAFFOLD_FORMULA_SEGMENTS,
    SCAFFOLD_INPUT_SEGMENTS,
    SCAFFOLD_JOIN_SEGMENTS,
    SCAFFOLD_OUTPUT_SEGMENTS,
    SCAFFOLD_SAMPLE_SEGMENTS,
    SCAFFOLD_SELECT_SEGMENTS,
    SCAFFOLD_SORT_SEGMENTS,
    SCAFFOLD_SUMMARIZE_SEGMENTS,
    SCAFFOLD_UNION_SEGMENTS,
    SCAFFOLD_UNIQUE_SEGMENTS,
    tool_segment,
)
from yxray.topology import build_predecessor_map, topo_order

__all__ = ["scaffold", "scaffold_simple", "node_code_snippets"]

# ── Alteryx expression → pandas translation ───────────────────────────────

_FIELD_RE = re.compile(r"\[([^\]]+)\]")
_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)


def _translate_expr(expr: str, df_var: str) -> str:
    """Replace [field] → df_var["field"] in Alteryx expressions."""
    return _FIELD_RE.sub(lambda m: f'{df_var}["{m.group(1)}"]', expr)


def _file_read(path_expr: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"pd.read_excel({path_expr})"
    return f"pd.read_csv({path_expr})"


def _file_write(path_expr: str, df_var: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"{df_var}.to_excel({path_expr}, index=False)"
    return f"{df_var}.to_csv({path_expr}, index=False)"


# ── Connection helpers ─────────────────────────────────────────────────────



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
    input_paths: dict[int, str],
) -> str:
    if tool_id in input_paths:
        ext = pathlib.Path(input_paths[tool_id]).suffix.lower()
        path_expr = f'INPUTS["input_{tool_id}"]'
        return f"{_dvar(tool_id)} = {_file_read(path_expr, ext)}"
    return f"{_dvar(tool_id)} = pd.read_csv(...)  # TODO: set file path"


def _gen_output(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    output_paths: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = _dvar(src) if src else "df_?"
    if tool_id in output_paths:
        ext = pathlib.Path(output_paths[tool_id]).suffix.lower()
        path_expr = f'OUTPUTS["output_{tool_id}"]'
        return _file_write(path_expr, df_in, ext)
    return f"{df_in}.to_csv(...)  # TODO: set file path"


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
    if operator == "Contains":
        return f'{col}.str.contains("{operand}", na=False)'
    if operator == "NotContains":
        return f'~{col}.str.contains("{operand}", na=False)'
    op = _SIMPLE_FILTER_OPS.get(operator)
    if op is None:
        return ""
    return f"{col} {op} {operand_literal(operand)}"


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
    simple_expr = _simple_filter_pandas(config, df_in)
    if simple_expr:
        return (
            f"# NOTE: from Simple-mode filter settings — review translation\n"
            f"{df_out} = {df_in}[{simple_expr}]"
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
        return f"{df_out} = {df_in}  # TODO: Select — no columns found"

    var = f"_COLS_{tool_id}"
    col_lines: list[str] = [f"{var} = ["]
    for name, new_name, selected in edits:
        if not selected:
            col_lines.append(f'    SelectColumnEdit("{name}", selected=False),')
        elif new_name:
            col_lines.append(f'    SelectColumnEdit("{name}", "{new_name}"),')
        else:
            col_lines.append(f'    SelectColumnEdit("{name}"),')
    col_lines.append("]")
    col_lines.append(f"{df_out} = apply_select_edits({df_in}, {var})")
    return "\n".join(col_lines)


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
            asc_str = str([a for a, f in zip(orders, fields, strict=True) if f])
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
    **dict.fromkeys(SCAFFOLD_FILTER_SEGMENTS, _gen_filter),
    **dict.fromkeys(SCAFFOLD_SELECT_SEGMENTS, _gen_select),
    **dict.fromkeys(SCAFFOLD_FORMULA_SEGMENTS, _gen_formula),
    **dict.fromkeys(SCAFFOLD_JOIN_SEGMENTS, _gen_join),
    **dict.fromkeys(SCAFFOLD_UNION_SEGMENTS, _gen_union),
    **dict.fromkeys(SCAFFOLD_SUMMARIZE_SEGMENTS, _gen_summarize),
    **dict.fromkeys(SCAFFOLD_SORT_SEGMENTS, _gen_sort),
    **dict.fromkeys(SCAFFOLD_SAMPLE_SEGMENTS, _gen_sample),
    **dict.fromkeys(SCAFFOLD_UNIQUE_SEGMENTS, _gen_unique),
}

# Segments whose scaffold snippet is short and self-contained enough to show
# as a single node's "python hint" (used by the inspect report's right pane).
# Excludes Select (would enumerate every column — too long) and Input/Output
# (depend on file paths, which the panel already shows separately).
_DETAIL_HINT_SEGMENTS = frozenset(_GENERATORS) - SCAFFOLD_SELECT_SEGMENTS


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

    snippets: dict[int, str] = {}
    for tool_id, node in node_map.items():
        segment = tool_segment(node.tool_type)
        if segment not in _DETAIL_HINT_SEGMENTS:
            continue
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})
        snippets[tool_id] = _GENERATORS[segment](
            tool_id, segment, node.config, preds, anchors
        )
    return snippets


# ── Scaffold section builders ──────────────────────────────────────────────


def _collect_metadata(
    node_map: dict[int, Any],
    order: list[int],
) -> tuple[dict[int, str], dict[int, str], bool]:
    """Pre-pass: collect input/output paths and whether any Select tools exist."""
    input_paths: dict[int, str] = {}
    output_paths: dict[int, str] = {}
    has_select = False

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

    return input_paths, output_paths, has_select


def _emit_preamble(source: str, has_select: bool) -> list[str]:
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
            fname = pathlib.Path(path).name
            lines.append(f'        "input_{tid}": BASE_DIR / "input" / "{fname}",')
        lines.append("    }")
    if output_paths:
        lines += ["", "    OUTPUTS = {"]
        for tid, path in output_paths.items():
            fname = pathlib.Path(path).name
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
        "    drop_columns = {c.name for c in columns if not c.selected}",
        "    rename_map = {",
        "        c.name: c.new_name",
        "        for c in columns",
        "        if c.selected and c.new_name and c.new_name != c.name",
        "    }",
        "    return df.drop(columns=drop_columns).rename(columns=rename_map)",
    ]


def _emit_main_body(
    order: list[int],
    node_map: dict[int, Any],
    pred_map: dict[int, list[int]],
    anchor_map: dict[int, dict[str, int]],
    input_paths: dict[int, str],
    output_paths: dict[int, str],
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

        if segment in SCAFFOLD_INPUT_SEGMENTS:
            code = _gen_input(
                tool_id, segment, node.config, preds, anchors, input_paths
            )
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            code = _gen_output(
                tool_id, segment, node.config, preds, anchors, output_paths
            )
        else:
            gen = _GENERATORS.get(segment)
            if gen is None:
                body.append("# TODO: unsupported tool type — review manually")
                body.append(f"# {_dvar(tool_id)} = ...")
                body.append("")
                continue
            code = gen(tool_id, segment, node.config, preds, anchors)

        body.append(code)
        body.append("")

    return ["    " + line if line else "" for line in body]


# ── Public API ─────────────────────────────────────────────────────────────


def scaffold_simple(doc: WorkflowDoc) -> str:
    """Return a flat Python scaffold without ENV/paths block or main() wrapper.

    Used for .md display: shows tool-by-tool code in topological order with
    raw file paths, without the project-level boilerplate added to .py files.
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
        segment = tool_segment(node.tool_type)
        preds = pred_map.get(tool_id, [])
        anchors = anchor_map.get(tool_id, {})

        lines.append(f"# {'─' * 68}")
        lines.append(f"# ToolID {tool_id}: {segment}")

        if segment in SCAFFOLD_INPUT_SEGMENTS:
            path = first_text(node.config, "File", "FileName")
            if path:
                ext = pathlib.Path(path).suffix.lower()
                path_expr = f'"{path}"'
                code = f"{_dvar(tool_id)} = {_file_read(path_expr, ext)}"
            else:
                code = f"{_dvar(tool_id)} = pd.read_csv(...)  # TODO: set file path"
        elif segment in SCAFFOLD_OUTPUT_SEGMENTS:
            src = preds[0] if preds else None
            df_in = _dvar(src) if src else "df_?"
            path = first_text(node.config, "File", "FileName")
            if path:
                ext = pathlib.Path(path).suffix.lower()
                path_expr = f'"{path}"'
                code = _file_write(path_expr, df_in, ext)
            else:
                code = f"{df_in}.to_csv(...)  # TODO: set file path"
        else:
            gen = _GENERATORS.get(segment)
            if gen is None:
                lines.append("# TODO: unsupported tool type — review manually")
                lines.append(f"# {_dvar(tool_id)} = ...")
                lines.append("")
                continue
            code = gen(tool_id, segment, node.config, preds, anchors)

        lines.append(code)
        lines.append("")

    return "\n".join(lines)


def scaffold(doc: WorkflowDoc) -> str:
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

    input_paths, output_paths, has_select = _collect_metadata(node_map, order)

    lines = _emit_preamble(source, has_select)
    lines += _emit_paths_block(input_paths, output_paths)
    if has_select:
        lines += _emit_select_helpers()
    lines += ["", "", "def main() -> None:"]
    lines += _emit_main_body(
        order, node_map, pred_map, anchor_map, input_paths, output_paths
    )
    lines += [
        "",
        "",
        'if __name__ == "__main__":',
        "    logging.basicConfig(level=logging.INFO)",
        "    main()",
    ]

    return "\n".join(lines)
