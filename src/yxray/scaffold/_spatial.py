"""Spatial tools (Create Points, Spatial Match) for the scaffold generator.

Both emit geopandas code; the CRS story that makes them safe (everything
normalized to WGS84, matching Alteryx's SpatialObj convention) is split
with _io: file reads normalize on load there, Create Points hard-codes
EPSG:4326 here.
"""

from __future__ import annotations

from yxray.config_utils import py_str
from yxray.scaffold._common import ToolContext, anchor_src, frame_name


def gen_createpoints(ctx: ToolContext) -> str:
    df_in = ctx.df_in
    df_out = ctx.df_out
    fields = ctx.config.get("Fields", {})
    x = fields.get("@fieldX", "") if isinstance(fields, dict) else ""
    y = fields.get("@fieldY", "") if isinstance(fields, dict) else ""
    if x and y:
        return (
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
    return f"{df_out} = {df_in}  # TODO: Create Points — X/Y fields not found"


def gen_spatialmatch(ctx: ToolContext) -> str:
    df_out = ctx.df_out
    t_id = anchor_src(ctx.anchors, ctx.preds, ("Targets", "Target"), 0)
    u_id = anchor_src(ctx.anchors, ctx.preds, ("Universe",), 1)
    df_t = frame_name(ctx.names, t_id, "df_targets")
    df_u = frame_name(ctx.names, u_id, "df_universe")
    method = ctx.config.get("Method", {})
    method_name = method.get("@method", "") if isinstance(method, dict) else ""
    predicate = method_name.lower() if method_name else "intersects"
    return (
        "# spatial tool — requires geopandas;"
        " review predicate and output fields\n"
        f"{df_out} = gpd.sjoin(\n"
        f"    {df_t},\n"
        f"    {df_u},\n"
        f'    how="inner",\n'
        f"    predicate={py_str(predicate)},\n"
        f")"
    )
