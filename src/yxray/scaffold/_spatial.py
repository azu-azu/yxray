"""Spatial tools (Create Points, Spatial Match, Spatial Info, Distance)
for the scaffold generator.

All emit geopandas code; the CRS story that makes them safe (everything
normalized to WGS84, matching Alteryx's SpatialObj convention) is split
with _io: file reads normalize on load there, Create Points hard-codes
EPSG:4326 here.

Distance is the one tool that cannot just trust that invariant — it
outputs a metric number, and EPSG:4326 measures in degrees — so it
projects into an estimated UTM zone for the measurement alone. That rule
is shared, not per-tool: see _METRIC_CRS_NOTE.
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


def _flag(config: dict[str, Any], key: str, *, default: bool = False) -> bool:
    """A <Key value="True"/> switch, or `default` when the tag is absent."""
    node = config.get(key)
    if not isinstance(node, dict):
        return default
    value = node.get("@value")
    return default if value is None else str(value).lower() == "true"


def _spatial_field_note(*fields: str) -> str:
    """Why the generated code does not simply index the XML's field name."""
    quoted = " and ".join(repr(comment_safe(f)) for f in fields)
    head = (
        f"# the XML's spatial field is {quoted}"
        if len(fields) == 1
        else f"# the XML's spatial fields are {quoted}"
    )
    return (
        f"{head}, but a frame read through\n"
        "# gpd.read_file (or built by Create Points) names its geometry"
        ' "geometry" —\n'
        "# fall back to the active geometry when the XML name is not a column\n"
        "# the crs= labels a plain Series and asserts on a GeoSeries: every"
        " frame\n"
        "# here is EPSG:4326 by construction (docs/spatial-crs-design.md)"
    )


def _geoseries_expr(df: str, field: str) -> str:
    """A GeoSeries for an Alteryx spatial field of `df`.

    Alteryx calls the field SpatialObj (or whatever an upstream tool named
    it); the generated frames call the active geometry "geometry", so the
    XML name is used only when it really is a column — which it is exactly
    when an earlier tool created it, e.g. Spatial Info's Centroid.
    """
    return (
        "gpd.GeoSeries(\n"
        f"    {df}[{py_str(field)}] if {py_str(field)} in {df}.columns"
        f" else {df}.geometry,\n"
        '    crs="EPSG:4326",\n'
        ")"
    )


# Metric operations have no answer on EPSG:4326 — the invariant CRS here
# (docs/spatial-crs-design.md) — because its unit is the degree, so the
# project-wide rule is: project every operand into ONE metric CRS estimated
# from the data, measure there, convert metres into the unit the tool's
# config asks for. UTM stays sub-metre inside its zone; EPSG:3857 is not an
# option, overstating by 1/cos(latitude) — 23% at Tokyo's 35.7°N.
_METRIC_CRS_NOTE = (
    "# EPSG:4326 measures in degrees — project both operands into one metric\n"
    "# CRS (UTM estimated from the data) before measuring"
)


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


# Spatial Info adds one field per selected item, named after the item: the
# tool's output MetaInfo tags the new field with
# source="SpatialInfo: CentroidObj Source=SpatialObj", and the tool has no
# rename UI, so the name is fixed. {item: (output field, GeoSeries attribute,
# comment lines)}.
#
# Only CentroidObj is translated, following _findreplace's rule of emitting
# real code for the verified combinations and an explicit TODO for the rest.
# Area and Length are held back on purpose: Alteryx returns them in the unit
# its config selects (sq miles, km) while EPSG:4326 — the CRS every frame
# carries here, see docs/spatial-crs-design.md — measures in degrees, so
# .area/.length would put a wrong number in a column golden CSVs compare.
# Centroid has neither problem, being a SpatialObj golden CSVs never show.
_SPATIAL_INFO_ITEMS: dict[str, tuple[str, str, str]] = {
    "CentroidObj": (
        "Centroid",
        "centroid",
        "# Centroid is a SpatialObj — like the geometry column it appears"
        " only in\n"
        "# Alteryx's Map tab, never in the Results grid or golden CSVs;"
        " drop it\n"
        "# on the comparison side, not here\n"
        "# .centroid on EPSG:4326 is a planar centroid in degrees (geopandas"
        "\n# warns); the offset from a geodesic one is negligible at"
        " building scale",
    ),
}

_SPATIAL_INFO_SKIP_NOTE = (
    "#   Area/Length need a projected CRS (EPSG:4326 measures in degrees) and\n"
    "#   Alteryx's unit setting; other items await golden verification"
)


def _selected_items(config: dict[str, Any]) -> list[str]:
    """Item names under <SelectedItems>, in XML order."""
    selected = config.get("SelectedItems", {})
    if not isinstance(selected, dict):
        return []
    names = (
        field_name(item)
        for item in as_list(selected.get("Item"))
        if isinstance(item, dict)
    )
    return [name for name in names if name]


def gen_spatialinfo(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    spatial_obj = ctx.config.get("SpatialObj", {})
    field = field_name(spatial_obj) if isinstance(spatial_obj, dict) else ""
    items = _selected_items(ctx.config)
    translated = [item for item in items if item in _SPATIAL_INFO_ITEMS]
    skipped = [item for item in items if item not in _SPATIAL_INFO_ITEMS]

    lines: list[str] = []
    if skipped:
        lines.append(
            "# TODO: Spatial Info — selected items not translated: "
            + comment_safe(", ".join(skipped))
        )
        lines.append(_SPATIAL_INFO_SKIP_NOTE)
    if not field or not translated:
        reason = "no input SpatialObj field" if not field else "no translatable items"
        lines.append(f"{df_out} = {df_in}  # TODO: Spatial Info — {reason}")
        return GeneratedCode("\n".join(lines))

    lines.append(
        "# spatial tool — requires geopandas\n"
        f"{_spatial_field_note(field)}\n"
        f"_geom = {_geoseries_expr(df_in, field)}\n"
        f"{df_out} = {df_in}.copy()"
    )
    for item in translated:
        out_field, attr, note = _SPATIAL_INFO_ITEMS[item]
        lines.append(f"{note}\n{df_out}[{py_str(out_field)}] = _geom.{attr}")
    return GeneratedCode("\n".join(lines), requirements=_GEOPANDAS)


# Metres per unit, keyed by Alteryx's OutputUnits spelling. The output field
# is named "Distance" + that spelling, confirmed by the tool's output
# MetaInfo: source="Distance: Distance Source=Centroid Destination=SpatialObj
# Units=Kilometers" on a field named DistanceKilometers. An unlisted spelling
# falls through to a TODO rather than guessing a conversion factor.
_DISTANCE_UNITS: dict[str, float] = {
    "Kilometers": 1000.0,
    "Meters": 1.0,
    "Miles": 1609.344,
    "Feet": 0.3048,
    "Yards": 0.9144,
    "NauticalMiles": 1852.0,
}

_DISTANCE_INSIDE_EDGE_NOTE = (
    "# DistToInsideEdge=True: measure to the boundary, so a source inside the\n"
    "# destination polygon gets the distance to its nearest edge instead of 0\n"
    "# (outside the polygon the two are identical)"
)

# The distance lands in a Double column that golden CSVs do compare, and a
# planar UTM measurement is not bit-identical to whatever earth model the
# Alteryx engine uses. The shape of the translation is settled; the last
# digits are not, so the generated code says so instead of implying parity.
_DISTANCE_WARNING = (
    "# WARNING: this is a planar UTM distance — Alteryx measures on its own\n"
    "# earth model, so diff this column against golden output before trusting it"
)


def _distance_todo(reason: str) -> str:
    return f"# TODO: Distance — {comment_safe(reason)}"


def _direction_todos(config: dict[str, Any], src: str, dst: str) -> list[str]:
    """TODO lines for the direction outputs, which are never generated.

    The cardinal field is named Direction and holds an 8-point compass point
    (its MetaInfo declares size=2, and 16-point labels need 3 characters),
    but which point of a polygon destination Alteryx takes the bearing to is
    not pinned down by anything in the XML — so it stays a TODO.
    """
    todos: list[str] = []
    pair = f"{comment_safe(src)} -> {comment_safe(dst)}"
    if _flag(config, "OutputCardinalDirection"):
        todos.append(
            _distance_todo('"Direction" (8-point compass) is not translated:')
            + f"\n#   {pair}, but the point Alteryx takes the bearing to on a"
            "\n#   polygon destination is unverified"
        )
    if _flag(config, "OutputDirectionDegrees"):
        todos.append(
            _distance_todo("the bearing-in-degrees output is not translated:")
            + f"\n#   {pair}, same open question, and its field name is not"
            "\n#   confirmed by any MetaInfo we have"
        )
    return todos


def gen_distance(ctx: ToolContext) -> GeneratedCode:
    df_in = ctx.df_in
    df_out = ctx.df_out
    config = ctx.config
    src_field = first_text(config, "SpatialObjSource")
    dst_field = first_text(config, "SpatialObjDest")
    units = first_text(config, "OutputUnits")

    blocker = ""
    if _flag(config, "OutputDriveTimeAndDistance"):
        blocker = (
            "drive-time/drive-distance mode has no pandas equivalent"
            " (needs a routing service)"
        )
    elif len(ctx.preds) > 1:
        blocker = (
            "two-input mode pairs whole streams — how ReturnNearest picks the"
            " rows is unverified, so only the single-input form is translated"
        )
    elif not _flag(config, "OutputDistance", default=True):
        blocker = "the distance output is switched off"
    elif not src_field or not dst_field:
        blocker = "Source/Destination spatial fields not found"
    elif units not in _DISTANCE_UNITS:
        blocker = f"unknown OutputUnits {units!r} — no conversion from metres"

    lines = _direction_todos(config, src_field, dst_field)
    if blocker:
        lines.insert(0, _distance_todo(blocker))
        lines.append(f"{df_out} = {df_in}")
        return GeneratedCode("\n".join(lines))

    dst_expr = "_dst.to_crs(_crs_m)"
    if _flag(config, "DistToInsideEdge"):
        dst_expr += ".boundary"
    measure = f"_src.to_crs(_crs_m).distance({dst_expr})"
    per_unit = _DISTANCE_UNITS[units]
    if per_unit != 1.0:
        # .10g keeps every digit of the factors (%g's default 6 would emit
        # 1609.34 for a mile) while dropping the trailing .0 from round ones.
        measure += f" / {per_unit:.10g}"

    body = [
        "# spatial tool — requires geopandas",
        "# single input: Source and Destination are two spatial fields of the"
        " same\n# record — the Centroid here is the column Spatial Info added"
        " upstream",
        _spatial_field_note(src_field, dst_field),
        f"_src = {_geoseries_expr(df_in, src_field)}",
        f"_dst = {_geoseries_expr(df_in, dst_field)}",
        _METRIC_CRS_NOTE,
        "_crs_m = _src.estimate_utm_crs()",
    ]
    if _flag(config, "DistToInsideEdge"):
        body.append(_DISTANCE_INSIDE_EDGE_NOTE)
    body += [
        _DISTANCE_WARNING,
        f"{df_out} = {df_in}.copy()",
        f"{df_out}[{py_str('Distance' + units)}] = (\n    {measure}\n)",
    ]
    return GeneratedCode("\n".join([*body, *lines]), requirements=_GEOPANDAS)
