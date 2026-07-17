"""Spatial tools (Create Points, Spatial Match) for the scaffold generator.

Both emit geopandas code; the CRS story that makes them safe (everything
normalized to WGS84, matching Alteryx's SpatialObj convention) is split
with _io: file reads normalize on load there, Create Points hard-codes
EPSG:4326 here.
"""

from __future__ import annotations

from typing import Any

from yxray.config_utils import (
    as_list,
    comment_safe,
    field_name,
    first_text,
    py_str,
    select_field_rows,
)
from yxray.scaffold._common import (
    GeneratedCode,
    Requirement,
    ToolContext,
    anchor_src,
    frame_name,
)

_GEOPANDAS = frozenset({Requirement.GEOPANDAS})


def gen_createpoints(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    fields = ctx.config.get("Fields", {})
    x = fields.get("@fieldX", "") if isinstance(fields, dict) else ""
    y = fields.get("@fieldY", "") if isinstance(fields, dict) else ""
    if x and y:
        code = (
            "# spatial tool — requires geopandas\n"
            "# NOTE: 'geometry' is Alteryx's 'Centroid' SpatialObj field —\n"
            "# shown only in the Map tab, never in the Results grid or\n"
            "# golden CSVs; drop it on the comparison side, not here\n"
            "# X/Y coerced to float64 first: points_from_xy() calls float()\n"
            "# per value, which raises TypeError on pd.NA (nullable dtypes)\n"
            "# or strings; rows with missing X/Y are kept, as Alteryx does\n"
            f"_x = pd.to_numeric({df_in}[{py_str(x)}],"
            ' errors="coerce").astype("float64")\n'
            f"_y = pd.to_numeric({df_in}[{py_str(y)}],"
            ' errors="coerce").astype("float64")\n'
            f"{df_out} = gpd.GeoDataFrame(\n"
            f"    {df_in},\n"
            f"    geometry=gpd.points_from_xy(_x, _y),\n"
            f'    crs="EPSG:4326",\n'
            f")"
        )
        return GeneratedCode(code, requirements=_GEOPANDAS)
    # TODO fallback emits no gpd code, so it declares nothing.
    return GeneratedCode(
        f"{df_out} = {df_in}  # TODO: Create Points — X/Y fields not found"
    )


def _matched_select_rows(config: dict[str, Any]) -> list[Any]:
    """SelectField rows of the Matched output's embedded Select, or []."""
    select_conf = config.get("SelectConfiguration", {})
    if not isinstance(select_conf, dict):
        return []
    for conf in as_list(select_conf.get("Configuration")):
        if not isinstance(conf, dict):
            continue
        if str(conf.get("@outputConnection", "Matched")).lower() == "matched":
            return select_field_rows(conf)
    return []


def _embedded_select_deviations(rows: list[Any]) -> list[str]:
    """Deviations of an embedded Select from its all-pass default state.

    A default embedded Select (every field selected, no rename, no type
    change) makes the sjoin translation complete apart from naming; only a
    deviation is worth a warning in the generated code.
    """
    deselected: list[str] = []
    renamed: list[str] = []
    retyped: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = field_name(r)
        if not name:
            continue
        if str(r.get("@selected", "True")).lower() == "false":
            deselected.append(name)
            continue
        new_name = first_text(r, "@rename", "@Rename")
        if new_name and new_name != name:
            renamed.append(f"{name} -> {new_name}")
        alteryx_type = first_text(r, "@type", "@Type")
        if alteryx_type:
            retyped.append(f"{name} ({alteryx_type})")
    deviations: list[str] = []
    if deselected:
        deviations.append("deselected: " + ", ".join(deselected))
    if renamed:
        deviations.append("renamed: " + ", ".join(renamed))
    if retyped:
        deviations.append("type changed: " + ", ".join(retyped))
    return deviations


# The embedded Select names fields with their input prefix (Target_ID),
# while sjoin's output keeps raw names plus _left/_right collision
# suffixes — emitting SelectColumnEdit rows against the XML names would be
# a silent no-op (apply_select_edits ignores missing columns), so until
# the name mapping is pinned down by golden data we only warn.
_EMBEDDED_SELECT_WARNING_LINES = (
    "# WARNING: the Matched output's embedded Select deviates from its"
    " default\n"
    "# state and is NOT translated — sjoin column names (raw names,"
    " _left/_right\n"
    "# suffixes on collisions) don't match the XML's Target_/Universe_"
    " prefixed\n"
    "# names, so align the output columns manually:"
)


def gen_spatialmatch(ctx: ToolContext) -> GeneratedCode:
    df_out = ctx.df_out
    t_id = anchor_src(ctx.anchors, ctx.preds, ("Targets", "Target"), 0)
    u_id = anchor_src(ctx.anchors, ctx.preds, ("Universe",), 1)
    df_t = frame_name(ctx.names, t_id, "df_targets")
    df_u = frame_name(ctx.names, u_id, "df_universe")
    method = ctx.config.get("Method", {})
    method_name = method.get("@method", "") if isinstance(method, dict) else ""
    predicate = method_name.lower() if method_name else "intersects"

    lines = ["# spatial tool — requires geopandas; review predicate and output fields"]
    deviations = _embedded_select_deviations(_matched_select_rows(ctx.config))
    if deviations:
        lines.append(_EMBEDDED_SELECT_WARNING_LINES)
        lines.extend(f"#   {comment_safe(d)}" for d in deviations)
    lines.append(
        "# index_right (sjoin artifact) is dropped —"
        " Alteryx output has no counterpart\n"
        f"{df_out} = gpd.sjoin(\n"
        f"    {df_t},\n"
        f"    {df_u},\n"
        f'    how="inner",\n'
        f"    predicate={py_str(predicate)},\n"
        f').drop(columns=["index_right"])'
    )
    return GeneratedCode("\n".join(lines), requirements=_GEOPANDAS)
