"""Multi-input combiners (Join, Union, Append Fields).

These are the tools whose translation depends on which predecessor feeds
which anchor (Left/Right, Targets/Sources) rather than on a single input
stream.
"""

from __future__ import annotations

import re
from typing import Any

from yxray.config_utils import comment_safe, first_text, py_str
from yxray.scaffold._common import anchor_src, frame_name

_JOIN_COND_RE = re.compile(r"\[L:([^\]]+)\]\s*=\s*\[R:([^\]]+)\]", re.IGNORECASE)


def gen_join(
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
    df_left = frame_name(names, left_id, "df_left")
    df_right = frame_name(names, right_id, "df_right")

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
            keys = "[" + ", ".join(py_str(lk) for lk, _ in matches) + "]"
            return (
                f"{df_out} = pd.merge(\n"
                f"    {df_left}, {df_right},\n"
                f"    on={keys},\n"
                f'    how="inner",\n'
                f")"
            )
        lkeys = "[" + ", ".join(py_str(lk) for lk, _ in matches) + "]"
        rkeys = "[" + ", ".join(py_str(rk) for _, rk in matches) + "]"
        return (
            f"{df_out} = pd.merge(\n"
            f"    {df_left}, {df_right},\n"
            f"    left_on={lkeys},\n"
            f"    right_on={rkeys},\n"
            f'    how="inner",\n'
            f")"
        )
    return (
        f"# TODO: parse join condition: {comment_safe(expr) or '(none)'}\n"
        f'{df_out} = pd.merge({df_left}, {df_right}, on=[...], how="inner")'
    )


def gen_union(
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


def gen_appendfields(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    t_id = anchor_src(anchors, preds, ("Targets", "Target"), 0)
    s_id = anchor_src(anchors, preds, ("Sources", "Source"), 1)
    df_t = frame_name(names, t_id, "df_targets")
    df_s = frame_name(names, s_id, "df_sources")
    return (
        "# Append Fields — every source record is appended"
        " to every target record\n"
        f'{df_out} = pd.merge({df_t}, {df_s}, how="cross")'
    )
