"""Input/Output tools and file read/write emission for the scaffold.

Everything that depends on the file path — extension dispatch
(csv/excel/spatial), post-read CRS normalization, the .shp-without-.shx
GDAL workaround, and the sidecar guards (.shp/.dbf, .tab/.dat) — lives
here, shared by
gen_input/gen_output (the .py scaffold, paths via INPUTS/OUTPUTS dicts)
and scaffold_simple_blocks (the .md scaffold, raw path literals).
"""

from __future__ import annotations

import pathlib

from yxray.config_utils import first_text
from yxray.scaffold._common import (
    GeneratedCode,
    PathStyle,
    Requirement,
    ToolContext,
)

SPATIAL_EXTS = frozenset({".shp", ".geojson", ".gpkg", ".gdb", ".tab"})

# Formats that keep their attribute table in a same-name sidecar rather than
# in the file the workflow names: read one without its sidecar and the
# attribute columns Alteryx declares are gone, so both get an existence check
# in front of the read. Uppercase suffixes pass too — GDAL's sidecar lookup
# is case-insensitive and Windows-produced sets are often uppercase.
# Each entry is (accepted suffixes, the comment explaining the guard).
SIDECAR_EXTS: dict[str, tuple[tuple[str, ...], str]] = {
    ".shp": (
        (".dbf", ".DBF"),
        "# attribute columns live in the same-name .dbf sidecar; GDAL opens\n"
        "# a .shp without it geometry-only, with no error — fail loudly",
    ),
    ".tab": (
        (".dat", ".DAT"),
        "# a MapInfo .tab is only a header file — the attribute table lives\n"
        "# in the same-name .dat sidecar, so refuse to read without it",
    ),
}

# GDAL refuses a .shp whose .shx sidecar is missing; Alteryx reads it anyway,
# so generated code must opt in to restoring the index. Process-wide config —
# set once, before the first read.
SHX_RESTORE_LINE = (
    'os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")  # read .shp without .shx'
)
SHX_NOTE_LINES = [
    "# NOTE: a .shp without its .shx sidecar fails to open — put",
    '# os.environ.setdefault("SHAPE_RESTORE_SHX", "YES") in your startup config.',
]


def is_shp(path: str | None) -> bool:
    return path is not None and pathlib.Path(path).suffix.lower() == ".shp"


def sidecar_ext(path: str | None) -> str:
    """The path's extension when it needs a sidecar guard, else ""."""
    if not path:
        return ""
    ext = pathlib.Path(path).suffix.lower()
    return ext if ext in SIDECAR_EXTS else ""


def _file_read(path_expr: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"pd.read_excel({path_expr})"
    if ext in SPATIAL_EXTS:
        return f"gpd.read_file({path_expr})"
    return f"pd.read_csv({path_expr})"


def _file_write(path_expr: str, df_var: str, ext: str) -> str:
    if ext in (".xlsx", ".xlsm", ".xls"):
        return f"{df_var}.to_excel({path_expr}, index=False)"
    if ext in SPATIAL_EXTS:
        return f"{df_var}.to_file({path_expr})"
    return f"{df_var}.to_csv({path_expr}, index=False)"


def _crs_normalize_stmt(target: str, src_expr: str) -> str:
    """Post-read CRS normalization emitted after every spatial file read.

    Alteryx stores every SpatialObj in WGS84 and converts on input, so its
    spatial tools never see mixed CRS. Without this, a .shp missing its .prj
    sidecar loads as CRS None and gpd.sjoin warns (and silently computes on
    raw coordinates) when matched against a CRS-tagged frame — e.g. the
    EPSG:4326 hard-coded by the Create Points scaffold.

    The CRS-None branch warns: the 4326 assumption matches what Alteryx
    would do, but if the source data was really in another CRS the spatial
    results are silently wrong, so the run should say the guess happened.
    """
    return (
        "# Alteryx SpatialObj is always WGS84 — assume it when CRS metadata\n"
        "# is missing (e.g. .shp without .prj), reproject anything else\n"
        f"if {target}.crs is None:\n"
        "    logger.warning(\n"
        '        "no CRS metadata (missing .prj?) — assuming EPSG:4326: %s",\n'
        f"        {src_expr},\n"
        "    )\n"
        f'    {target} = {target}.set_crs("EPSG:4326")\n'
        "else:\n"
        f'    {target} = {target}.to_crs("EPSG:4326")'
    )


def _sidecar_read_stmt(target: str, path_expr: str, ext: str) -> str:
    """Spatial read with a sidecar-existence guard in front.

    For .shp GDAL treats the .dbf as optional — a .shp whose .dbf sidecar is
    missing (or SHAPE_RESTORE_SHX reviving a lone .shp) opens geometry-only
    with no error, and every attribute column Alteryx declares silently
    vanishes. For .tab the attribute table is likewise not in the named file.
    Fail loudly before the read instead of reading a stripped frame.
    """
    suffixes, note = SIDECAR_EXTS[ext]
    var = f"_{ext.lstrip('.')}"
    accepted = ", ".join(f'"{s}"' for s in suffixes)
    return (
        f"{note}\n"
        f"{var} = Path({path_expr})\n"
        f"if not any({var}.with_suffix(s).exists() for s in ({accepted})):\n"
        f'    raise FileNotFoundError(f"{{{var}}}: {suffixes[0]} sidecar not found")\n'
        f"{target} = gpd.read_file({var})\n" + _crs_normalize_stmt(target, var)
    )


def read_stmt(target: str, path: str | None, path_expr: str) -> str:
    """`target = pd.read_...(path_expr)`, or a TODO fallback when path is unset.

    Shared by scaffold() (path_expr → INPUTS[...]) and
    scaffold_simple_blocks() (path_expr → raw literal) so the extension
    dispatch and fallback wording live in one place.
    """
    if not path:
        return f"{target} = pd.read_csv(...)  # TODO: set file path"
    ext = pathlib.Path(path).suffix.lower()
    if ext in SIDECAR_EXTS:
        return _sidecar_read_stmt(target, path_expr, ext)
    stmt = f"{target} = {_file_read(path_expr, ext)}"
    if ext in SPATIAL_EXTS:
        stmt += "\n" + _crs_normalize_stmt(target, path_expr)
    return stmt


def write_stmt(df_in: str, path: str | None, path_expr: str) -> str:
    """`df_in.to_...(path_expr)`, or a TODO fallback when path is unset.

    Counterpart to read_stmt for the output side.
    """
    if not path:
        return f"{df_in}.to_csv(...)  # TODO: set file path"
    ext = pathlib.Path(path).suffix.lower()
    return _file_write(path_expr, df_in, ext)


# scaffold(): file paths resolve through the shared INPUTS/OUTPUTS dicts,
# and the .shx workaround lives once in the preamble.
PROJECT_PATHS = PathStyle(
    input_expr=lambda tool_id, path: f'INPUTS["input_{tool_id}"]',
    output_expr=lambda tool_id, path: f'OUTPUTS["output_{tool_id}"]',
    inline_shx_note=False,
)
# .md scaffold: raw path literals, .shx note prepended to the block itself.
INLINE_PATHS = PathStyle(
    input_expr=lambda tool_id, path: f'r"{path}"' if path else "",
    output_expr=lambda tool_id, path: f'r"{path}"' if path else "",
    inline_shx_note=True,
)


def _path_requirements(path: str | None) -> frozenset[Requirement]:
    """GEOPANDAS when the file is spatial (read/write goes through gpd)."""
    if path and pathlib.Path(path).suffix.lower() in SPATIAL_EXTS:
        return frozenset({Requirement.GEOPANDAS})
    return frozenset()


def _read_requirements(path: str | None) -> frozenset[Requirement]:
    """What the read_stmt emission relies on, beyond pandas.

    Spatial reads also declare LOGGING (the CRS-None branch warns); sidecar
    formats additionally declare PATHLIB (the guard builds a Path).
    """
    reqs = set(_path_requirements(path))
    if reqs:
        reqs.add(Requirement.LOGGING)
    if sidecar_ext(path):
        reqs.add(Requirement.PATHLIB)
    return frozenset(reqs)


def gen_input(ctx: ToolContext) -> GeneratedCode:
    path = first_text(ctx.config, "File", "FileName")
    code = read_stmt(
        ctx.names[ctx.tool_id], path, ctx.paths.input_expr(ctx.tool_id, path)
    )
    if ctx.paths.inline_shx_note and is_shp(path):
        code = "\n".join([*SHX_NOTE_LINES, code])
    return GeneratedCode(code, requirements=_read_requirements(path))


def gen_output(ctx: ToolContext) -> GeneratedCode:
    path = first_text(ctx.config, "File", "FileName")
    return GeneratedCode(
        write_stmt(ctx.df_in, path, ctx.paths.output_expr(ctx.tool_id, path)),
        requirements=_path_requirements(path),
    )
