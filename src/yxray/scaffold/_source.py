"""Non-file endpoints of the flow (Text Input, Browse).

Text Input materializes data embedded in the workflow XML — emitted as a
build_text_input_df_<id>() helper so the row data sits beside the flow
instead of in it; Browse is a sink that only logs. File-backed
Input/Output live in _io.
"""

from __future__ import annotations

from yxray.config_utils import as_list, field_name, py_str
from yxray.scaffold._common import GeneratedCode, Requirement, ToolContext


def gen_text_input(ctx: ToolContext) -> GeneratedCode:
    df_out = ctx.df_out
    fields = ctx.config.get("Fields", {})
    field_names: list[str] = []
    if isinstance(fields, dict):
        field_names = [
            field_name(f)
            for f in as_list(fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    if not field_names:
        return GeneratedCode(
            f"{df_out} = pd.DataFrame(...)  # TODO: Text Input — no fields found"
        )

    data = ctx.config.get("Data", {})
    rows: list[list[str]] = []
    for r in as_list(data.get("r")) if isinstance(data, dict) else []:
        if not isinstance(r, dict):
            continue
        cells: list[str] = []
        for c in as_list(r.get("c")) if "c" in r else []:
            if isinstance(c, dict):
                c = c.get("#text")
            cells.append("" if c is None else str(c))
        rows.append(cells)

    builder = f"build_text_input_df_{ctx.tool_id}"
    lines = [
        f"def {builder}() -> pd.DataFrame:",
        f'    """Data embedded in Text Input ToolID_{ctx.tool_id}."""',
        "    # Text Input values are strings — cast dtypes if needed",
        "    df = pd.DataFrame({",
    ]
    for i, name in enumerate(field_names):
        values = ", ".join(py_str(row[i]) if i < len(row) else '""' for row in rows)
        lines.append(f"        {py_str(name)}: [{values}],")
    lines += ["    })", "    return df"]
    return GeneratedCode(f"{df_out} = {builder}()", helpers=("\n".join(lines),))


def gen_browse(ctx: ToolContext) -> GeneratedCode:
    return GeneratedCode(
        f'logger.info("ToolID_{ctx.tool_id} (Browse): rows=%d", len({ctx.df_in}))',
        requirements=frozenset({Requirement.LOGGING}),
    )
