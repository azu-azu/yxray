"""Select tool → pandas translation for the scaffold generator.

Select's quirk is that its XML is saved-state: the .yxmd keeps the Select
configuration as of some earlier save, so it can silently disagree with
what the Alteryx GUI actually shows. Every generated block therefore
carries a stale-XML warning, plus targeted warnings for the *Unknown
pseudo-field patterns that usually indicate a source-file issue and for the
type changes whose pandas equivalent is not confirmed against Alteryx
(string formatting, integer rounding).
"""

from __future__ import annotations

from yxray.config_utils import field_name, first_text, py_str, select_field_rows
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

# apply_select_edits() (reference_impl/select_edits.py) converts a type
# change to one of these with series.astype("string") — Python's own float
# repr ("1.0"), not Alteryx's drop-the-trailing-zero rule ("1") that
# reference_impl/to_display_string.py already implements (docs/
# alteryx-pandas-differences.md chapter 20) but apply_select_edits doesn't
# call.
# The XML's @type only names the TARGET type (it appears "only on a column
# with a type change" — see gen_select()), not what the column held
# before, so a numeric source can't be ruled out here.
_SELECT_STRING_TYPES = frozenset({"String", "WString", "V_String", "V_WString"})

_SELECT_STRING_CONVERSION_WARNING = (
    "# WARNING: a type change here converts to a string type — if the source\n"
    "# was numeric, apply_select_edits()'s astype(\"string\") uses Python's own\n"
    '# float formatting ("1.0", full precision), not Alteryx\'s ("1", trailing\n'
    "# zero dropped). reference_impl/to_display_string.py already implements\n"
    "# Alteryx's rule but is not called here — same unconfirmed-formatting\n"
    "# risk as ToString() elsewhere in this repo either way, since\n"
    "# to_display_string() itself is not golden-verified against Alteryx\n"
    "# — diff the converted column against golden output before trusting it"
)

# apply_select_edits() reaches a nullable Int dtype via series.round(), which
# is round-half-to-even: a tie whose integer part is even rounds down (0.5 ->
# 0, 2.5 -> 2) where round-half-away-from-zero gives 1 and 3. The round() call
# itself is required (astype to a nullable Int rejects a fractional float), so
# the open question is the MODE, not whether to round. Alteryx's own mode is
# unconfirmed, same caveat as TOSTRING_FORMAT_WARNING_LINES in _common.py and
# _DISTANCE_WARNING in _spatial.py — the generated code says so rather than
# implying parity. Byte is Alteryx's unsigned 8-bit type; the set mirrors
# _INT_DTYPES in reference_impl/select_edits.py.
_SELECT_INT_TYPES = frozenset({"Byte", "Int16", "Int32", "Int64"})

_SELECT_INT_ROUNDING_WARNING = (
    "# WARNING: a type change here converts to an integer type —\n"
    "# apply_select_edits() rounds with Series.round(), which is\n"
    "# half-to-even (0.5 -> 0, 2.5 -> 2, not 1 and 3), and the rounding mode\n"
    "# is not confirmed against Alteryx — diff this column against golden\n"
    "# output before trusting it, negative values included"
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
        new_name: str | None = first_text(r, "@rename", "@Rename") or None
        if new_name == name:
            new_name = None
        # @type appears only on a column with a type change (V_WString /
        # Int32 etc.)
        alteryx_type: str | None = first_text(r, "@type", "@Type") or None
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
    converts_to_string = any(
        selected and alteryx_type in _SELECT_STRING_TYPES
        for _, _, selected, alteryx_type in edits
    )
    converts_to_int = any(
        selected and alteryx_type in _SELECT_INT_TYPES
        for _, _, selected, alteryx_type in edits
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
    if converts_to_string:
        col_lines.append(_SELECT_STRING_CONVERSION_WARNING)
    if converts_to_int:
        col_lines.append(_SELECT_INT_ROUNDING_WARNING)
    col_lines.append(
        "# NOTE: SelectColumnEdit / apply_select_edits are not generated —"
    )
    col_lines.append("# copy them from reference_impl/select_edits.py")
    col_lines.append(f"{var} = [")
    for name, new_name, selected, alteryx_type in edits:
        if not selected:
            # new_name / type are meaningless on a dropped column, so omit them
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
