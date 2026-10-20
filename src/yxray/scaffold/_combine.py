"""Multi-input combiners (Join, Union, Append Fields).

These are the tools whose translation depends on which predecessor feeds
which anchor (Left/Right, Targets/Sources) rather than on a single input
stream.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from yxray.config_utils import (
    as_list,
    comment_safe,
    field_name,
    first_text,
    get_text,
    py_str,
    select_field_rows,
)
from yxray.scaffold._common import (
    GeneratedCode,
    ToolContext,
)

_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)


def _join_info_fields(config: dict[str, Any], connection: str) -> list[str]:
    """Ordered join-key field names for one side of a Join's <JoinInfo>.

    Real workflow XML nests one or more <Field field="..."/> children per
    <JoinInfo connection="Left"|"Right"> (one per join key, in order)
    rather than putting the key in a left/right attribute on <JoinInfo>
    itself — every Join tool observed in a real .yxmc used this shape,
    none used the @left/@right form below.
    """
    for info in as_list(config.get("JoinInfo")):
        if not isinstance(info, dict):
            continue
        if first_text(info, "@connection", "@Connection") != connection:
            continue
        return [
            name
            for field in as_list(info.get("Field"))
            if isinstance(field, dict) and (name := field_name(field))
        ]
    return []


def _resolve_join_matches(config: dict[str, Any]) -> list[tuple[str, str]]:
    """(left, right) key pairs for a Join, trying each known XML shape in turn.

    1. JoinExpression text ([L:x] = [R:y]) — never seen in a real .yxmc so
       far, kept in case an older Alteryx version emits it.
    2. JoinInfo/Field children — the shape every real Join has actually
       used (see _join_info_fields).
    3. JoinInfo @left/@right attributes — likewise never confirmed against
       real data; kept only as a last-resort defensive fallback. Drop this
       branch if it's still unreached after a few more real workflows.
    """
    expr = first_text(config, "JoinExpression") or ""
    matches = _JOIN_COND_RE.findall(expr)

    if not matches:
        left_fields = _join_info_fields(config, "Left")
        right_fields = _join_info_fields(config, "Right")
        if left_fields and len(left_fields) == len(right_fields):
            matches = list(zip(left_fields, right_fields, strict=True))

    if not matches:
        join_info = config.get("JoinInfo", {})
        if isinstance(join_info, list):
            join_info = join_info[0] if join_info else {}
        if isinstance(join_info, dict):
            lk = first_text(join_info, "@left", "@Left")
            rk = first_text(join_info, "@right", "@Right")
            if lk and rk:
                matches = [(lk, rk)]

    return matches


def _gen_join_selected(ctx: ToolContext) -> GeneratedCode:
    df_out = ctx.df_out
    df_left = ctx.input_frame(("Left",), fallback="df_left")
    df_right = ctx.input_frame(("Right",), 1, "df_right")

    expr = first_text(ctx.config, "JoinExpression") or ""
    matches = _resolve_join_matches(ctx.config)

    if str(ctx.config.get("@joinByRecordPos", "False")).lower() == "true":
        return GeneratedCode(
            "# TODO: Join by record position is not implemented\n"
            'raise NotImplementedError("Join by record position")'
        )

    selections = ctx.config.get("SelectConfiguration", {})
    if isinstance(selections, dict) and matches:
        for selection in as_list(selections.get("Configuration")):
            if not isinstance(selection, dict):
                continue
            if selection.get("@outputConnection") != "Join":
                continue
            rows = select_field_rows(selection)
            if not rows:
                continue
            order_value = selection.get("OrderChanged", {})
            order_changed = (
                str(order_value.get("@value", "")).lower() == "true"
                if isinstance(order_value, dict)
                else str(order_value).lower() == "true"
            )
            lines = [
                "# NOTE: join_selected() is not generated — copy it from",
                "# reference_impl/join_selected.py, together with select_edits.py",
                "# WARNING: saved Select XML may be stale; verify against Alteryx.",
                "# Type conversions use select_edits.py's documented approximations.",
                f"_JOIN_COLS_{ctx.tool_id} = [",
            ]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = field_name(row)
                if not name:
                    continue
                side = str(row.get("@input", ""))
                if name != "*Unknown":
                    if side not in ("Left_", "Right_") or not name.startswith(side):
                        return GeneratedCode(
                            "# TODO: ambiguous Join Select field; resolve input side\n"
                            'raise NotImplementedError("Ambiguous Join Select input")'
                        )
                    name = name[len(side) :]
                selected = str(row.get("@selected", "True")).lower() != "false"
                rename = first_text(row, "@rename", "@Rename") if selected else ""
                dtype = first_text(row, "@type", "@Type") if selected else ""
                lines.append(
                    f"    ({py_str(side)}, {py_str(name)}, {selected}, "
                    f"{py_str(rename) if rename else 'None'}, "
                    f"{py_str(dtype) if dtype else 'None'}),"
                )
            lines.extend(
                [
                    "]",
                    f"{df_out} = join_selected(",
                    f"    {df_left}, {df_right},",
                    f"    keys={matches!r},",
                    f"    columns=_JOIN_COLS_{ctx.tool_id},",
                    f"    order_changed={order_changed},",
                    ")",
                ]
            )
            return GeneratedCode("\n".join(lines))

    if matches:
        if all(lk == rk for lk, rk in matches):
            keys = "[" + ", ".join(py_str(lk) for lk, _ in matches) + "]"
            return GeneratedCode(
                f"{df_out} = pd.merge(\n"
                f"    {df_left}, {df_right},\n"
                f"    on={keys},\n"
                f'    how="inner",\n'
                f")"
            )
        lkeys = "[" + ", ".join(py_str(lk) for lk, _ in matches) + "]"
        rkeys = "[" + ", ".join(py_str(rk) for _, rk in matches) + "]"
        return GeneratedCode(
            f"{df_out} = pd.merge(\n"
            f"    {df_left}, {df_right},\n"
            f"    left_on={lkeys},\n"
            f"    right_on={rkeys},\n"
            f'    how="inner",\n'
            f")"
        )
    return GeneratedCode(
        f"# TODO: parse join condition: {comment_safe(expr) or '(none)'}\n"
        f'{df_out} = pd.merge({df_left}, {df_right}, on=[...], how="inner")'
    )


def gen_join(ctx: ToolContext) -> GeneratedCode:
    """Emit each connected L/J/R stream separately; Select applies to J only."""
    if not ctx.output_ports:
        return _gen_join_selected(ctx)
    if str(ctx.config.get("@joinByRecordPos", "False")).lower() == "true":
        return GeneratedCode(
            "# TODO: Join by record position is not implemented\n"
            'raise NotImplementedError("Join by record position")'
        )
    keys = _resolve_join_matches(ctx.config)
    if not keys:
        return GeneratedCode(
            "# TODO: Join keys could not be resolved\n"
            'raise NotImplementedError("Unresolved Join keys")'
        )
    lines = []
    for port in ctx.output_ports:
        suffix = {"Left": "l", "Join": "j", "Right": "r"}[port]
        output = f"{ctx.df_out}_{suffix}"
        if port == "Join":
            j_ctx = replace(ctx, names={**ctx.names, ctx.tool_id: output})
            lines.append(_gen_join_selected(j_ctx).code)
        else:
            lines += [
                "# NOTE: copy join_unmatched from reference_impl/join_selected.py",
                "# together with select_edits.py; null matching follows pandas.",
                f"{output} = join_unmatched(",
                f"    {ctx.input_frame(('Left',))}, {ctx.input_frame(('Right',), 1)},",
                f"    keys={keys!r}, side={port!r},",
                ")",
            ]
    return GeneratedCode("\n".join(lines))


def gen_union(ctx: ToolContext) -> GeneratedCode:
    df_out = ctx.df_out
    if not ctx.preds:
        return GeneratedCode(
            f"{df_out} = pd.concat([...], ignore_index=True)  # TODO: set inputs"
        )
    streams = list(ctx.input_streams or ())
    order_setting = ctx.config.get("SetOutputOrder", {})
    explicit_order = (
        isinstance(order_setting, dict)
        and str(order_setting.get("@value", "False")).lower() == "true"
    )
    if explicit_order and ctx.input_streams is not None:
        order = ctx.config.get("OutputOrder", {})
        ports = (
            [
                get_text({"port": port}, "port")
                for port in as_list(order.get("Connection"))
            ]
            if isinstance(order, dict)
            else []
        )
        by_port = {stream.name or stream.target_port: stream for stream in streams}
        if (
            len(by_port) != len(streams)
            or len(set(ports)) != len(ports)
            or set(ports) != set(by_port)
        ):
            return GeneratedCode(
                "# TODO: Union output order does not resolve all input connections\n"
                'raise NotImplementedError("Unresolved Union output order")'
            )
        streams = [by_port[port] for port in ports]
    parts = (
        ", ".join(stream.frame for stream in streams)
        if ctx.input_streams is not None
        else ", ".join(ctx.names.get(p, "df_?") for p in ctx.preds)
    )
    return GeneratedCode(f"{df_out} = pd.concat([{parts}], ignore_index=True)")


def gen_appendfields(ctx: ToolContext) -> GeneratedCode:
    df_out = ctx.df_out
    df_t = ctx.input_frame(("Targets", "Target"), 0, "df_targets")
    df_s = ctx.input_frame(("Sources", "Source"), 1, "df_sources")
    return GeneratedCode(
        "# Append Fields — every source record is appended"
        " to every target record\n"
        f'{df_out} = pd.merge({df_t}, {df_s}, how="cross")'
    )
