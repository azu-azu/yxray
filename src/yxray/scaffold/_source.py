"""Non-file endpoints of the flow (Text Input, Browse).

Text Input materializes data embedded in the workflow XML; Browse is a
sink that only logs. File-backed Input/Output live in _io.
"""

from __future__ import annotations

from typing import Any

from yxray.config_utils import as_list, field_name, py_str
from yxray.scaffold._common import frame_name


def gen_text_input(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    _preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    fields = config.get("Fields", {})
    field_names: list[str] = []
    if isinstance(fields, dict):
        field_names = [
            field_name(f)
            for f in as_list(fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    if not field_names:
        return f"{df_out} = pd.DataFrame(...)  # TODO: Text Input — no fields found"

    data = config.get("Data", {})
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

    lines = [
        "# Text Input values are strings — cast dtypes if needed",
        f"{df_out} = pd.DataFrame({{",
    ]
    for i, name in enumerate(field_names):
        values = ", ".join(py_str(row[i]) if i < len(row) else '""' for row in rows)
        lines.append(f"    {py_str(name)}: [{values}],")
    lines.append("})")
    return "\n".join(lines)


def gen_browse(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    _anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    src = preds[0] if preds else None
    df_in = frame_name(names, src)
    return f'logger.info("ToolID {tool_id} (Browse): rows=%d", len({df_in}))'
