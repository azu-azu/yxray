"""Select tool → pandas translation for the scaffold generator.

Select's quirk is that its XML is saved-state: the .yxmd keeps the Select
configuration as of some earlier save, so it can silently disagree with
what the Alteryx GUI actually shows. Every generated block therefore
carries a stale-XML warning, plus targeted warnings for the *Unknown
pseudo-field patterns that usually indicate a source-file issue.
"""

from __future__ import annotations

from yxray.config_utils import field_name, py_str, select_field_rows
from yxray.scaffold._common import GeneratedCode, ToolContext

# Select tools always carry this warning: the .yxmd XML keeps the Select
# state as of some earlier save, so it can silently disagree with what the
# Alteryx GUI actually shows (e.g. a field the GUI flags as "not found" /
# 見つかりません still looks like a regular entry in the XML).
_SELECT_STALE_XML_WARNING = (
    "# WARNING: Select XML may be stale (saved-state) and can differ from the\n"
    '# actual Select contents — fields shown as "not found" in the Alteryx GUI\n'
    "# may still appear here as regular entries. Always verify in the GUI."
)


def gen_select(ctx: ToolContext) -> GeneratedCode:
    tool_id = ctx.tool_id
    df_in = ctx.df_in
    df_out = ctx.df_out
    rows = select_field_rows(ctx.config)

    edits: list[tuple[str, str | None, bool, str | None]] = []
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
        # @type は型変更された列にのみ現れる（V_WString / Int32 など）
        alteryx_type: str | None = r.get("@type") or r.get("@Type") or None
        edits.append((name, new_name, selected, alteryx_type))

    if not edits:
        return GeneratedCode(
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
        name == "*Unknown" and not selected for name, _, selected, _ in edits
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
    col_lines.append(
        "# NOTE: SelectColumnEdit / apply_select_edits are not generated —"
    )
    col_lines.append("# copy them from scripts/apply_select_edits.py")
    col_lines.append(f"{var} = [")
    for name, new_name, selected, alteryx_type in edits:
        if not selected:
            # drop される列に new_name / type を出しても意味がないので省く
            col_lines.append(f"    SelectColumnEdit({py_str(name)}, selected=False),")
            continue
        args = [py_str(name)]
        if new_name:
            args.append(f"new_name={py_str(new_name)}")
        if alteryx_type:
            args.append(f"type={py_str(alteryx_type)}")
        col_lines.append(f"    SelectColumnEdit({', '.join(args)}),")
    col_lines.append("]")
    col_lines.append(f"{df_out} = apply_select_edits({df_in}, {var})")
    return GeneratedCode("\n".join(col_lines))
