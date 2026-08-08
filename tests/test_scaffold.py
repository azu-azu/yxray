from typing import Any

from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.scaffold import (
    node_code_snippets,
    scaffold,
    scaffold_simple,
    scaffold_simple_blocks,
)
from yxray.scaffold._filter import (
    _date_columns_in_fragment,
    _fields_in_fragment,
    _isempty_columns_in_fragment,
)


def _doc(
    *nodes: AlteryxNode,
    connections: tuple[AlteryxConnection, ...] = (),
) -> WorkflowDoc:
    return WorkflowDoc(filepath="test.yxmd", nodes=nodes, connections=connections)


# ── Header ─────────────────────────────────────────────────────────────────


def test_scaffold_includes_imports() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    code = scaffold(doc)
    assert "import pandas as pd" in code


def test_scaffold_includes_docstring() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    code = scaffold(doc)
    assert "test.yxmd" in code


def test_scaffold_includes_main() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    code = scaffold(doc)
    assert "def main()" in code
    assert '__name__ == "__main__"' in code


# ── Input / Output ──────────────────────────────────────────────────────────


def test_scaffold_input_excel() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": "master.xlsx"},
        )
    )
    code = scaffold(doc)
    assert 'INPUTS["input_1"]' in code
    assert "pd.read_excel" in code


def test_scaffold_input_csv() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": "data.csv"},
        )
    )
    code = scaffold(doc)
    assert 'INPUTS["input_1"]' in code
    assert "pd.read_csv" in code


def test_scaffold_input_paths_env_block() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": "data.csv"},
        )
    )
    code = scaffold(doc)
    assert 'ENV = os.getenv("APP_ENV", "test")' in code
    assert "BASE_DIR" in code
    assert "parents[2]" in code
    assert '"input_1"' in code


def test_scaffold_output_csv() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": "a.csv"},
        ),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="OutputData",
            x=10,
            y=0,
            config={"File": "out.csv"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'OUTPUTS["output_2"]' in code
    assert ".to_csv" in code


def test_scaffold_input_shp_uses_gpd_read_file() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        )
    )
    code = scaffold(doc)
    assert "gpd.read_file(" in code
    assert "import geopandas as gpd" in code
    assert "pd.read_csv(" not in code


def test_scaffold_spatial_read_normalizes_crs_to_wgs84() -> None:
    # Alteryx SpatialObj is always WGS84; a .shp without .prj loads as CRS
    # None and gpd.sjoin then warns about mixed CRS against e.g. the
    # EPSG:4326 frame Create Points builds. Every spatial read must
    # normalize right after loading.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        )
    )
    code = scaffold(doc)
    assert "if df_1.crs is None:" in code
    assert "no CRS metadata (missing .prj?)" in code
    assert 'df_1 = df_1.set_crs("EPSG:4326")' in code
    assert 'df_1 = df_1.to_crs("EPSG:4326")' in code


def test_scaffold_simple_spatial_read_normalizes_crs_to_wgs84() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.gpkg"},
        )
    )
    code = scaffold_simple(doc)
    assert "if df_1.crs is None:" in code
    assert "no CRS metadata (missing .prj?)" in code
    assert 'df_1 = df_1.set_crs("EPSG:4326")' in code
    assert 'df_1 = df_1.to_crs("EPSG:4326")' in code
    # the warning uses logger, so the .md header must set one up
    assert "import logging" in code
    assert "logger = logging.getLogger(__name__)" in code


def test_scaffold_csv_read_has_no_crs_normalization() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\plain.csv"},
        )
    )
    assert "set_crs" not in scaffold(doc)


def test_scaffold_shp_restores_shx_once_in_preamble() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        ),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="DbFileInput",
            x=0,
            y=100,
            config={"FileName": r"C:\data\roads.shp"},
        ),
    )
    code = scaffold(doc)
    restore = 'os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")'
    # Process-wide GDAL config: set once at module level, not per read.
    assert code.count(restore) == 1
    assert code.index(restore) < code.index("def main()")


def test_scaffold_non_shp_has_no_shx_restore() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.gpkg"},
        )
    )
    assert "SHAPE_RESTORE_SHX" not in scaffold(doc)


def test_scaffold_simple_shp_notes_shx_restore() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        )
    )
    code = scaffold_simple(doc)
    assert "import geopandas as gpd" in code
    # The .md scaffold carries a reminder comment, not executable config.
    assert "# NOTE: a .shp without its .shx sidecar fails to open" in code
    assert 'os.environ.setdefault("SHAPE_RESTORE_SHX", "YES")' in code
    assert "import os" not in code


def test_scaffold_simple_non_shp_spatial_has_no_shx_restore() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.gpkg"},
        )
    )
    code = scaffold_simple(doc)
    assert "SHAPE_RESTORE_SHX" not in code
    assert "import os" not in code


def test_scaffold_shp_read_guards_missing_dbf() -> None:
    # GDAL treats the .dbf sidecar as optional: a .shp without it opens
    # geometry-only with no error (SHAPE_RESTORE_SHX even revives a lone
    # .shp), and every attribute column Alteryx declares silently
    # vanishes. The emitted read fails loudly before that can happen.
    # .DBF too — GDAL's sidecar lookup is case-insensitive, so uppercase
    # sets from Windows must pass the guard.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        )
    )
    code = scaffold(doc)
    guard = 'any(_shp.with_suffix(s).exists() for s in (".dbf", ".DBF"))'
    assert guard in code
    assert 'raise FileNotFoundError(f"{_shp}: .dbf sidecar not found")' in code
    assert "df_1 = gpd.read_file(_shp)" in code


def test_scaffold_simple_shp_dbf_guard_imports_pathlib() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.shp"},
        )
    )
    code = scaffold_simple(doc)
    assert "from pathlib import Path" in code
    assert '_shp = Path(r"C:\\data\\areas.shp")' in code
    assert 'raise FileNotFoundError(f"{_shp}: .dbf sidecar not found")' in code


def test_scaffold_tab_read_guards_missing_dat() -> None:
    # A MapInfo .tab is only a header file: geometry lives in the .map and
    # the attribute table in the .dat, so a .tab on its own cannot produce
    # the columns Alteryx declares. Same guard shape as .shp/.dbf, and
    # .DAT passes too for uppercase sets from Windows.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\polygons.tab"},
        )
    )
    code = scaffold(doc)
    assert 'any(_tab.with_suffix(s).exists() for s in (".dat", ".DAT"))' in code
    assert 'raise FileNotFoundError(f"{_tab}: .dat sidecar not found")' in code
    assert "df_1 = gpd.read_file(_tab)" in code
    # .tab is a spatial format, so the read normalizes CRS like any other…
    assert 'df_1 = df_1.to_crs("EPSG:4326")' in code
    # …but SHAPE_RESTORE_SHX is shapefile-specific and must not leak here.
    assert "SHAPE_RESTORE_SHX" not in code


def test_scaffold_tab_write_goes_through_geopandas() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileOutput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\out.tab"},
        )
    )
    code = scaffold(doc)
    assert "import geopandas as gpd" in code
    assert ".to_file(" in code
    assert ".to_csv(" not in code


def test_scaffold_simple_non_shp_spatial_has_no_dbf_guard() -> None:
    # Only .shp and .tab split their attributes into a sidecar; single-file
    # spatial formats read whole, so no guard and no pathlib import.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\areas.gpkg"},
        )
    )
    code = scaffold_simple(doc)
    assert ".dbf" not in code
    assert "from pathlib import Path" not in code


def test_scaffold_windows_path_extracts_filename_in_test_block() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="DbFileInput",
            x=0,
            y=0,
            config={"FileName": r"C:\data\subdir\indoor4.csv"},
        )
    )
    code = scaffold(doc)
    # test block uses only filename, not the full Windows path
    assert 'BASE_DIR / "input" / "indoor4.csv"' in code
    # prod block keeps full path (intentional)
    assert r'Path(r"C:\data\subdir\indoor4.csv")' in code


# ── Filter ─────────────────────────────────────────────────────────────────


def test_scaffold_filter_translates_field_notation() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df_1["Age"] > 18' in code
    assert "df_2 = df_1[" in code


def test_scaffold_filter_date_comparison_warning() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": '[日付列] >= ToDate("2024-01-01")'},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "# WARNING: date comparison" in code
    assert "pd.to_datetime" in code


def test_scaffold_filter_no_date_warning_without_date_functions() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "# WARNING: date comparison" not in code


def test_date_columns_in_fragment_matches_both_directions() -> None:
    assert _date_columns_in_fragment('[日付列] >= ToDate("2024-01-01")') == {"日付列"}
    assert _date_columns_in_fragment('ToDate("2024-01-01") <= [日付列]') == {"日付列"}


def test_date_columns_in_fragment_misses_column_wrapped_inside_todate() -> None:
    # ToDate([col]) >= [other]: the column *inside* ToDate(...) can't be
    # named by the adjacent-pattern regex (matching inside a call's
    # parens is out of scope), but the column on the other side of the
    # comparison is still caught via the reverse-direction branch.
    assert _date_columns_in_fragment("ToDate([日付列]) >= [別の日付列]") == {
        "別の日付列"
    }


def test_isempty_columns_in_fragment_excludes_isnull() -> None:
    fragment = "IsEmpty([A]) OR IsNull([B])"
    assert _isempty_columns_in_fragment(fragment) == {"A"}


def test_fields_in_fragment_collects_all_columns() -> None:
    fragment = "[A] >= ToDate(...) OR [A] >= [B]"
    assert _fields_in_fragment(fragment) == {"A", "B"}


def test_scaffold_filter_isempty_plus_date_gets_precise_and_residual_warnings() -> None:
    # cond_1 is a bare IsEmpty on 日付列A, cond_2 date-compares 日付列A
    # against ToDate(...) and also against 日付列B (column-vs-column, so
    # 日付列B is only reachable via the residual fallback).
    expr = (
        "IsEmpty([日付列A]) OR ([日付列A] >= ToDate(DateTimeToday())"
        " or (!IsEmpty([日付列B]) and [日付列A] >= [日付列B]))"
    )
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'column "日付列A" is compared as a date in cond_2' in code
    assert 'IsEmpty\'s == "" check on "日付列A"' in code
    assert 'verify the type of column "日付列B" too' in code
    assert 'IsEmpty == "" check becomes always False afterward' in code


def test_scaffold_filter_isnull_with_date_has_no_dead_code_note() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={
                "Expression": 'IsNull([DateCol]) OR [DateCol] >= ToDate("2024-01-01")'
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'column "DateCol" is compared as a date' in code
    assert "IsEmpty" not in code


def test_scaffold_filter_date_residual_warning_flags_unrelated_column() -> None:
    # A single top-level operand can bundle an unrelated condition via an
    # inner AND ([Name] == "foo" here) — the residual fallback is the
    # documented, accepted trade-off for that case.
    expr = '([DateCol] >= ToDate("2024-01-01") AND [Name] == "foo") OR [Other] > 1'
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'column "DateCol" is compared as a date in cond_1' in code
    assert 'verify the type of column "Name" too' in code


def _simple_filter_doc(simple_config: dict) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Mode": "Simple", "Simple": simple_config},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_filter_simple_mode_string_equality() -> None:
    doc = _simple_filter_doc(
        {
            "Operator": "=",
            "Field": "CAPEX/OPEX",
            "Operands": {
                "IgnoreTimeInDateTime": "True",
                "DateType": "fixed",
                "PeriodDate": "2024-03-13 15:05:03",
                "PeriodType": None,
                "PeriodCount": "0",
                "Operand": "CAPEX",
                "StartDate": "2024-03-13 15:05:03",
                "EndDate": "2024-03-13 15:05:03",
            },
        }
    )
    code = scaffold(doc)
    assert 'df_2 = df_1[df_1["CAPEX/OPEX"] == "CAPEX"]' in code
    assert "Filter expression missing" not in code


def test_scaffold_filter_simple_mode_numeric_comparison() -> None:
    doc = _simple_filter_doc(
        {
            "Operator": ">",
            "Field": "Amount",
            "Operands": {"Operand": "100"},
        }
    )
    code = scaffold(doc)
    assert 'df_2 = df_1[df_1["Amount"] > 100]' in code


def test_scaffold_filter_simple_mode_contains_is_literal() -> None:
    # Alteryx Contains is a literal substring match — the operand must not
    # be interpreted as regex ("ta.ro" matching "taXro" etc.).
    doc = _simple_filter_doc(
        {
            "Operator": "Contains",
            "Field": "Name",
            "Operands": {"Operand": "ta.ro"},
        }
    )
    code = scaffold(doc)
    assert (
        'df_2 = df_1[df_1["Name"].str.contains("ta.ro", regex=False, na=False)]' in code
    )


def test_scaffold_filter_simple_mode_is_null() -> None:
    doc = _simple_filter_doc({"Operator": "IsNull", "Field": "Amount"})
    code = scaffold(doc)
    assert 'df_2 = df_1[df_1["Amount"].isna()]' in code


def test_scaffold_filter_simple_mode_unknown_operator_falls_back() -> None:
    doc = _simple_filter_doc(
        {
            "Operator": "InThePast",
            "Field": "Date",
            "Operands": {"Operand": ""},
        }
    )
    code = scaffold(doc)
    assert "df_2 = df_1  # TODO: Filter expression missing" in code


# ── Filter mask splitting (issue #33) ──────────────────────────────────────


def _expr_filter_doc(expr: str) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_filter_three_operands_split_into_masks() -> None:
    code = scaffold_simple(_expr_filter_doc("[a] = 1 AND [b] = 2 AND [c] = 3"))
    assert "# [a] = 1" in code
    assert 'cond_1 = df_1["a"] == 1' in code
    assert "# [b] = 2" in code
    assert 'cond_2 = df_1["b"] == 2' in code
    assert "# [c] = 3" in code
    assert 'cond_3 = df_1["c"] == 3' in code
    assert "df_2 = df_1[cond_1 & cond_2 & cond_3]" in code


def test_scaffold_filter_or_chain_split_joins_with_pipe() -> None:
    code = scaffold_simple(_expr_filter_doc("[a] = 1 OR [b] = 2 OR [c] = 3"))
    assert "df_2 = df_1[cond_1 | cond_2 | cond_3]" in code


def test_scaffold_filter_two_long_operands_split_into_masks() -> None:
    # The issue #33 headline example: two negated conditions whose one-line
    # form exceeds the 88-column limit.
    code = scaffold_simple(
        _expr_filter_doc('!Contains([Status], "drop") AND !IsEmpty([Status])')
    )
    assert '# !Contains([Status], "drop")' in code
    assert (
        "cond_1 = ~df_1[\"Status\"].str.contains('drop', case=False,"
        " regex=False, na=False)" in code
    )
    assert "# !IsEmpty([Status])" in code
    assert 'cond_2 = ~(df_1["Status"].isna() | (df_1["Status"] == ""))' in code
    assert "df_2 = df_1[cond_1 & cond_2]" in code


def test_scaffold_filter_two_short_operands_stay_one_line() -> None:
    code = scaffold_simple(_expr_filter_doc('[Age] > 18 AND [Status] = "Active"'))
    assert 'df_2 = df_1[(df_1["Age"] > 18) & (df_1["Status"] == \'Active\')]' in code
    assert "cond_1" not in code


def test_scaffold_filter_line_length_boundary_88_stays_one_line() -> None:
    # One-line form is exactly 88 columns — at the limit, not over it.
    field = "x" * 29
    code = scaffold_simple(_expr_filter_doc(f'[{field}] > 18 AND [Status] = "Active"'))
    line = f'df_2 = df_1[(df_1["{field}"] > 18) & (df_1["Status"] == \'Active\')]'
    assert len(line) == 88
    assert line in code
    assert "cond_1" not in code


def test_scaffold_filter_line_length_boundary_89_splits() -> None:
    # One character longer than the previous test: 89 columns — splits.
    field = "x" * 30
    code = scaffold_simple(_expr_filter_doc(f'[{field}] > 18 AND [Status] = "Active"'))
    assert f'cond_1 = df_1["{field}"] > 18' in code
    assert "cond_2 = df_1[\"Status\"] == 'Active'" in code
    assert "df_2 = df_1[cond_1 & cond_2]" in code


def test_scaffold_filter_multiline_expression_comment_not_broken() -> None:
    expr = '!Contains([Status],\n    "drop")\nAND !IsEmpty([Status])\nAND [a] = 1'
    code = scaffold_simple(_expr_filter_doc(expr))
    assert '# !Contains([Status], "drop")' in code
    assert "df_2 = df_1[cond_1 & cond_2 & cond_3]" in code
    # every comment line stays a comment (no raw fragment lines)
    for line in code.splitlines():
        if "drop" in line and "cond_1" not in line:
            assert line.startswith("#")


def test_scaffold_filter_if_expression_never_splits() -> None:
    # np.where filters are a single operand — excluded from mask splitting
    # even when the line is long.
    expr = (
        'IF [status_flag_long_name] > 100 THEN [category_column] = "keep"'
        ' ELSE [category_column] = "discard" ENDIF'
    )
    code = scaffold_simple(_expr_filter_doc(expr))
    assert "cond_1" not in code
    assert "np.where" in code


def test_scaffold_filter_untranslatable_expression_never_splits() -> None:
    code = scaffold_simple(
        _expr_filter_doc("[a] ?? weird AND [b] ?? syntax AND [c] ?? here")
    )
    assert "cond_1" not in code
    assert 'df_1["a"] ?? weird AND df_1["b"] ?? syntax' in code


def test_scaffold_filter_untranslatable_expression_gets_todo_marker() -> None:
    # The [field] substitution fallback keeps untranslated Alteryx syntax
    # verbatim — it reads like Python but is not runnable. A plain "review
    # translation" header is not enough to distinguish it from a fully
    # translated expression; it needs its own explicit TODO.
    code = scaffold_simple(_expr_filter_doc("[a] ?? weird syntax"))
    assert (
        "# TODO: could not translate expression — port manually:"
        " [a] ?? weird syntax" in code
    )


def test_scaffold_filter_date_warning_survives_translation_fallback() -> None:
    # translate_filter_masks() fails on the whole expression (the "?? weird"
    # operand), so pandas_expr falls back to the raw Alteryx source and
    # never contains pd.to_datetime — _DATE_EXPR_RE alone would miss that
    # this filter still compares a date. _ALTERYX_DATE_FN_RE catches it from
    # the untranslated ToDate(...) call instead.
    code = scaffold_simple(
        _expr_filter_doc('[EventDate] >= ToDate("2024-01-01") AND [Other] ?? weird')
    )
    assert "# TODO: could not translate expression" in code
    assert "# WARNING: date comparison" in code


def test_scaffold_filter_no_date_warning_on_fallback_without_date_functions() -> None:
    # Same fallback path as above, but nothing in the raw expression looks
    # like a date function — _ALTERYX_DATE_FN_RE must not fire on unrelated
    # untranslatable syntax.
    code = scaffold_simple(_expr_filter_doc("[a] ?? weird syntax"))
    assert "# TODO: could not translate expression" in code
    assert "# WARNING: date comparison" not in code


# ── Formula ────────────────────────────────────────────────────────────────


def test_scaffold_formula_translates_if_expression() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {
                        "@field": "Grade",
                        "@expression": (
                            'IF [Score] >= 80 THEN "A" '
                            'ELSEIF [Score] >= 60 THEN "B" '
                            'ELSE "C" ENDIF'
                        ),
                    }
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "import numpy as np" in code
    assert (
        'np.select([df_2["Score"] >= 80, df_2["Score"] >= 60],'
        " ['A', 'B'], default='C')" in code
    )
    assert "THEN" not in code


def _formula_doc(field: str, expression: str) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {"@field": field, "@expression": expression}
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_formula_isnull_fill_uses_fillna_without_numpy() -> None:
    code = scaffold(
        _formula_doc("Amount", "IF IsNull([Amount]) THEN 0 ELSE [Amount] ENDIF")
    )
    assert 'df_2["Amount"] = df_2["Amount"].fillna(0)' in code
    # np.where here would return an ndarray and drop the column's dtype;
    # nothing on this path emits np.*, so the import must not appear.
    assert "np.where" not in code
    assert "import numpy as np" not in code
    assert "fill_empty" not in code


def test_scaffold_formula_isempty_fill_notes_the_helper_source() -> None:
    code = scaffold(
        _formula_doc("Status", 'IF IsEmpty([Status]) THEN "N/A" ELSE [Status] ENDIF')
    )
    assert 'df_2["Status"] = fill_empty(df_2["Status"], \'N/A\')' in code
    # The definition is not generated — the block has to say where it lives.
    assert "# NOTE: fill_empty() is not generated — copy it from" in code
    assert "# reference_impl/fill_empty.py" in code
    # The NOTE belongs above the call, not after it.
    assert code.index("reference_impl/fill_empty.py") < code.index("= fill_empty(")


def test_scaffold_formula_negated_fill_reaches_the_same_code() -> None:
    # The two ways an Alteryx author writes the same fill must generate the
    # same thing — otherwise the negated form silently keeps np.where and
    # loses the column's dtype.
    positive = scaffold(
        _formula_doc("Status", 'IF IsEmpty([Status]) THEN "N/A" ELSE [Status] ENDIF')
    )
    negated = scaffold(
        _formula_doc("Status", 'IF !IsEmpty([Status]) THEN [Status] ELSE "N/A" ENDIF')
    )
    assert 'df_2["Status"] = fill_empty(df_2["Status"], \'N/A\')' in negated
    assert negated == positive


def test_scaffold_isempty_outside_a_fill_stays_inline() -> None:
    # Deliberate, not an oversight: fill_empty translates the *fill
    # pattern*, not the IsEmpty function. In boolean position IsEmpty
    # produces a mask — nothing to preserve dtype on — and hiding the
    # == "" half would leave the date/dead-code warning of
    # docs/alteryx-pandas-differences.md 17 pointing at invisible code.
    mid_expression = scaffold(
        _formula_doc("Flag", 'IF IsEmpty([S]) THEN "x" ELSE "y" ENDIF')
    )
    assert 'np.where((df_2["S"].isna() | (df_2["S"] == "")), \'x\', \'y\')' in (
        mid_expression
    )
    assert "fill_empty" not in mid_expression

    negated_filter = scaffold_simple(_expr_filter_doc("!IsEmpty([Status])"))
    assert '~(df_1["Status"].isna() | (df_1["Status"] == ""))' in negated_filter
    assert "fill_empty" not in negated_filter


def test_scaffold_formula_without_fill_omits_the_helper_note() -> None:
    code = scaffold(_formula_doc("Net", "[Gross] - [Tax]"))
    assert "fill_empty" not in code


def test_scaffold_formula_new_field_from_fill_is_valid_python() -> None:
    # Alteryx Formula can create a field, so the fill has to be an
    # expression assigned to the new column — an in-place
    # df.loc[mask, col] = value would need "Clean" to already exist.
    code = scaffold(
        _formula_doc("Clean", 'IF IsEmpty([Raw]) THEN "-" ELSE [Raw] ENDIF')
    )
    assert 'df_2["Clean"] = fill_empty(df_2["Raw"], \'-\')' in code
    compile(code, "<scaffold>", "exec")


def test_scaffold_filter_boolean_expression_parenthesized() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": '[Age] > 18 AND [Status] = "Active"'},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert '(df_1["Age"] > 18) & (df_1["Status"] == \'Active\')' in code
    assert "import numpy as np" not in code


def test_scaffold_formula_untranslatable_expression_falls_back() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {
                        "@field": "y",
                        "@expression": "[x] ?? weird syntax",
                    }
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df_2["x"] ?? weird syntax' in code
    # The [field] substitution fallback keeps untranslated Alteryx syntax
    # verbatim — it reads like Python but is not runnable (e.g. an
    # untranslated function call raises NameError). It needs its own
    # explicit TODO, distinct from the block-level "review translation"
    # header that's emitted regardless of whether translation succeeded.
    assert (
        '# TODO: could not translate expression for "y" — port manually:'
        " [x] ?? weird syntax" in code
    )


def test_scaffold_formula_field_name_with_space_is_valid_python() -> None:
    # Field names like "Sales Amount" are common in Alteryx; embedding them
    # as .assign() keyword arguments would produce a SyntaxError.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {
                        "@field": "Sales Amount",
                        "@expression": "[Price] * [Qty]",
                    }
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df_2["Sales Amount"] = df_2["Price"] * df_2["Qty"]' in code
    # The whole scaffold must be syntactically valid Python.
    compile(code, "<scaffold>", "exec")


def test_scaffold_field_name_with_quote_stays_valid_python() -> None:
    # A double-quote in a field name would break naive '"{name}"' embedding;
    # every generator routes names through py_str, so the scaffold still
    # parses. Sort is one representative generator.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Sort",
            x=10,
            y=0,
            config={
                "SortInfo": {"Field": {"@field": 'weird"name', "@order": "Ascending"}}
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    compile(code, "<scaffold>", "exec")
    assert 'weird\\"name' in code  # escaped, not a bare quote


def test_scaffold_text_input_data_value_with_quote_stays_valid_python() -> None:
    # Text Input cells are arbitrary data — a quote in a value is realistic,
    # not just theoretical, and must not break the generated DataFrame.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="TextInput",
            x=0,
            y=0,
            config={
                "Fields": {"Field": {"@name": "Note"}},
                "Data": {"r": {"c": 'say "hi"'}},
            },
        ),
    )
    code = scaffold(doc)
    compile(code, "<scaffold>", "exec")


def test_scaffold_formula_later_field_references_earlier() -> None:
    # Alteryx applies formulas top to bottom; the second formula reads the
    # column the first one created, so it must reference the built-up frame.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": [
                        {"@field": "Net", "@expression": "[Gross] - [Tax]"},
                        {"@field": "Doubled", "@expression": "[Net] * 2"},
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "df_2 = df_1.copy()" in code
    assert 'df_2["Net"] = df_2["Gross"] - df_2["Tax"]' in code
    # Doubled reads Net from the built-up frame, not the original df_1.
    assert 'df_2["Doubled"] = df_2["Net"] * 2' in code
    assert ".assign(" not in code


# ── Select ─────────────────────────────────────────────────────────────────


def test_scaffold_select_columns() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [
                        {"@field": "Name", "@selected": "True"},
                        {"@field": "Age", "@selected": "True"},
                        {"@field": "Junk", "@selected": "False"},
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert '"Name"' in code
    assert '"Age"' in code
    assert 'SelectColumnEdit("Junk", selected=False)' in code
    assert "apply_select_edits" in code


def test_scaffold_select_with_rename() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [
                        {
                            "@field": "old_col",
                            "@selected": "True",
                            "@rename": "new_col",
                        },
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert '"new_col"' in code
    assert "SelectColumnEdit" in code


def test_scaffold_select_with_type_change() -> None:
    """@type (present only when the Select changes a column's type) is
    forwarded to SelectColumnEdit; deselected columns never carry it."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [
                        {
                            "@field": "amount",
                            "@selected": "True",
                            "@type": "Double",
                        },
                        {
                            "@field": "old_col",
                            "@selected": "True",
                            "@rename": "new_col",
                            "@type": "V_WString",
                        },
                        {
                            "@field": "junk",
                            "@selected": "False",
                            "@type": "Int32",
                        },
                        {"@field": "plain", "@selected": "True"},
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'SelectColumnEdit("amount", type="Double")' in code
    assert 'SelectColumnEdit("old_col", new_name="new_col", type="V_WString")' in code
    assert 'SelectColumnEdit("junk", selected=False)' in code
    assert 'SelectColumnEdit("plain")' in code


def test_scaffold_select_does_not_emit_helper_definitions() -> None:
    """Helper definitions are no longer embedded in the generated .py;
    the scaffold emits the call plus a NOTE to provide them separately."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [{"@field": "Col", "@selected": "True"}]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "from dataclasses import dataclass" not in code
    assert "class SelectColumnEdit:" not in code
    assert "def apply_select_edits(" not in code
    assert "# NOTE: SelectColumnEdit / apply_select_edits are not generated" in code
    assert "apply_select_edits(df_1, _COLS_2)" in code


def test_scaffold_select_always_warns_about_stale_xml() -> None:
    """Every Select block — scaffold, simple scaffold, and the panel's python
    hint — carries the always-on warning that Select XML can be stale and
    must be verified against the Alteryx GUI."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [{"@field": "Name", "@selected": "True"}]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    expected = "# WARNING: Select XML may be stale"
    assert expected in scaffold(doc)
    assert expected in scaffold_simple(doc)
    assert expected in node_code_snippets(doc)[2]
    assert "Always verify in the GUI" in scaffold(doc)


def test_scaffold_select_stale_warning_even_without_columns() -> None:
    """The stale-XML warning appears even when no columns could be parsed."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "# WARNING: Select XML may be stale" in code
    assert "# TODO: Select — no columns found" in code


def test_scaffold_select_unknown_deselected_warning() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={
                "SelectFields": {
                    "SelectField": [
                        {"@field": "Name", "@selected": "True"},
                        {"@field": "*Unknown", "@selected": "False"},
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "# WARNING: *Unknown=False" in code


# ── Browse ──────────────────────────────────────────────────────────────────


def _browse_doc() -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="BrowseV2", x=10, y=0),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_browse_logs_row_count() -> None:
    code = scaffold(_browse_doc())
    assert 'logger.info("ToolID_2 (Browse): rows=%d", len(df_1))' in code
    assert "unsupported tool type" not in code


def test_scaffold_simple_browse_defines_logger() -> None:
    code = scaffold_simple(_browse_doc())
    assert "import logging" in code
    assert "logger = logging.getLogger(__name__)" in code
    assert 'logger.info("ToolID_2 (Browse): rows=%d", len(df_1))' in code


def test_scaffold_simple_without_browse_has_no_logger() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    code = scaffold_simple(doc)
    assert "logging" not in code


# ── Join ───────────────────────────────────────────────────────────────────


def test_scaffold_join_same_key() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=100),
        AlteryxNode(
            tool_id=ToolID(3),
            tool_type="Join",
            x=100,
            y=50,
            config={"JoinExpression": "[L:CustomerID] = [R:CustomerID]"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Right"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "pd.merge" in code
    assert '"CustomerID"' in code
    assert "df_1, df_2" in code


def test_scaffold_join_different_keys() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=100),
        AlteryxNode(
            tool_id=ToolID(3),
            tool_type="Join",
            x=100,
            y=50,
            config={"JoinExpression": "[L:OrdID] = [R:OrderID]"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Right"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "left_on" in code
    assert "right_on" in code
    assert '"OrdID"' in code
    assert '"OrderID"' in code


def test_scaffold_join_unparseable_expr_with_newline_stays_in_comment() -> None:
    # An unrecognized JoinExpression is echoed into a `# TODO` comment
    # verbatim from the XML; a newline in it would end the comment and
    # expose the tail as code. comment_safe flattens it to one line.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=100),
        AlteryxNode(
            tool_id=ToolID(3),
            tool_type="Join",
            x=100,
            y=50,
            config={"JoinExpression": "messy\nmulti-line cond"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Right"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "# TODO: parse join condition: messy multi-line cond" in code
    compile(code, "<scaffold>", "exec")


# ── Summarize ──────────────────────────────────────────────────────────────


def test_scaffold_summarize_groupby() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Summarize",
            x=10,
            y=0,
            config={
                "SummarizeFields": {
                    "SummarizeField": [
                        {"@field": "Region", "@action": "GroupBy"},
                        {"@field": "Sales", "@action": "Sum"},
                    ]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "groupby" in code
    assert '"Region"' in code
    assert '"Sales"' in code


# ── Union ──────────────────────────────────────────────────────────────────


def test_scaffold_union_concat() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=100),
        AlteryxNode(tool_id=ToolID(3), tool_type="Union", x=100, y=50),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Input1"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Input2"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "pd.concat" in code
    assert "pd.concat([df_1, df_2], ignore_index=True)" in code


# ── Sort / Unique ──────────────────────────────────────────────────────────


def _chain_doc(second: AlteryxNode) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        second,
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_sort_reads_nested_field_rows() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Sort",
            x=10,
            y=0,
            config={
                "SortInfo": {
                    "@locale": "0",
                    "Field": {"@field": "日付列C(p)", "@order": "Descending"},
                }
            },
        )
    )
    code = scaffold(doc)
    assert 'df_2 = df_1.sort_values(["日付列C(p)"], ascending=[False])' in code


def test_scaffold_sort_multiple_fields() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Sort",
            x=10,
            y=0,
            config={
                "SortInfo": {
                    "Field": [
                        {"@field": "A", "@order": "Ascending"},
                        {"@field": "B", "@order": "Descending"},
                    ]
                }
            },
        )
    )
    code = scaffold(doc)
    assert 'df_2 = df_1.sort_values(["A", "B"], ascending=[True, False])' in code


def test_scaffold_unique_uses_subset() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Unique",
            x=10,
            y=0,
            config={"UniqueFields": {"Field": {"@field": "ID_A"}}},
        )
    )
    code = scaffold(doc)
    assert 'df_2 = df_1.drop_duplicates(subset=["ID_A"])' in code


def test_scaffold_unique_without_fields_keeps_default() -> None:
    doc = _chain_doc(AlteryxNode(tool_id=ToolID(2), tool_type="Unique", x=10, y=0))
    code = scaffold(doc)
    assert "df_2 = df_1.drop_duplicates()" in code


# ── RecordID ───────────────────────────────────────────────────────────────


def test_scaffold_recordid_uses_configured_field_and_start() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="RecordID",
            x=10,
            y=0,
            config={
                "FieldName": {"#text": "RowNum"},
                "StartValue": {"#text": "0"},
            },
        )
    )
    code = scaffold(doc)
    assert "df_2 = df_1.reset_index(drop=True)" in code
    assert 'df_2["RowNum"] = df_2.index + 0' in code


def test_scaffold_recordid_without_config_uses_defaults() -> None:
    doc = _chain_doc(AlteryxNode(tool_id=ToolID(2), tool_type="RecordID", x=10, y=0))
    code = scaffold(doc)
    assert "df_2 = df_1.reset_index(drop=True)" in code
    assert 'df_2["RecordID"] = df_2.index + 1' in code


# ── Count Records ──────────────────────────────────────────────────────────


def test_scaffold_countrecords_has_no_config() -> None:
    doc = _chain_doc(
        AlteryxNode(tool_id=ToolID(2), tool_type="CountRecords", x=10, y=0)
    )
    code = scaffold(doc)
    assert 'df_2 = pd.DataFrame({"Count": [len(df_1)]})' in code


# ── Text Input ─────────────────────────────────────────────────────────────


def test_scaffold_text_input_builds_dataframe() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="TextInput",
            x=0,
            y=0,
            config={
                "NumRows": {"@value": "3"},
                "Fields": {"Field": {"@name": "進捗"}},
                "Data": {
                    "r": [
                        {"c": {"#text": "Not Started"}},
                        {"c": "In Progress"},
                        {"c": "Done"},
                    ]
                },
            },
        )
    )
    code = scaffold(doc)
    # The rows live in a module-level builder; main() just calls it.
    assert "def build_text_input_df_1() -> pd.DataFrame:" in code
    assert "    df = pd.DataFrame({" in code
    assert (
        '        "進捗": ["Not Started", "In Progress", "Done"],'
        in code
    )
    assert "    return df" in code
    assert "    df_1 = build_text_input_df_1()" in code
    compile(code, "<scaffold>", "exec")


def test_scaffold_text_input_builder_defined_above_main() -> None:
    # The builder is a module-level def, not nested in main(): main() must
    # stay a one-line-per-tool flow, and the call must resolve at runtime.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="TextInput",
            x=0,
            y=0,
            config={
                "Fields": {"Field": {"@name": "Note"}},
                "Data": {"r": {"c": "hello"}},
            },
        )
    )
    code = scaffold(doc)
    assert code.index("def build_text_input_df_1()") < code.index("def main()")
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 — generated scaffold must actually run
    namespace["main"]()


def test_scaffold_two_text_inputs_get_distinct_builders() -> None:
    # Two Text Input tools in one workflow must not define the same builder.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="TextInput",
            x=0,
            y=0,
            config={
                "Fields": {"Field": {"@name": "A"}},
                "Data": {"r": {"c": "left"}},
            },
        ),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="TextInput",
            x=0,
            y=10,
            config={
                "Fields": {"Field": {"@name": "B"}},
                "Data": {"r": {"c": "right"}},
            },
        ),
    )
    code = scaffold(doc)
    assert "df_1 = build_text_input_df_1()" in code
    assert "df_2 = build_text_input_df_2()" in code
    compile(code, "<scaffold>", "exec")


def test_scaffold_simple_text_input_keeps_builder_in_its_own_block() -> None:
    # The .md output is read block by block beside each <Node> XML, so the
    # data must stay in the Text Input block — and be defined before its call.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="TextInput",
            x=0,
            y=0,
            config={
                "Fields": {"Field": {"@name": "Note"}},
                "Data": {"r": {"c": "hello"}},
            },
        )
    )
    _header, blocks = scaffold_simple_blocks(doc)
    block = "\n".join(blocks[0].lines)
    assert blocks[0].helpers == ()
    assert block.index("def build_text_input_df_1()") < block.index(
        "df_1 = build_text_input_df_1()"
    )
    assert '"hello"' in block


# ── Find Replace ───────────────────────────────────────────────────────────


def _two_input_doc(
    tool_type: str,
    config: dict,
    anchor_a: str,
    anchor_b: str,
) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=10),
        AlteryxNode(tool_id=ToolID(3), tool_type=tool_type, x=10, y=0, config=config),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName(anchor_a),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName(anchor_b),
            ),
        ),
    )


def test_scaffold_findreplace_append_mode_left_join() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "ID_A",
            "FieldSearch": "ID_A",
            "ReplaceFoundField": "フィールドC",
            "FindMode": "FindWhole",
            "ReplaceMode": "Append",
            "ReplaceAppendFields": {
                "Field": [{"@field": "フィールドA"}, {"@field": "フィールドB"}],
            },
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    assert 'df_2[["ID_A", "フィールドA", "フィールドB"]]' in code
    assert 'on="ID_A"' in code
    assert 'how="left"' in code
    assert "unsupported tool type" not in code
    # duplicate lookup keys must not grow the row count: the lookup side is
    # deduplicated before the join and the last duplicate wins
    assert '.drop_duplicates("ID_A", keep="last")' in code
    assert "raise ValueError(" not in code
    # keep="last" is golden-verified (3 duplicate keys with distinct values,
    # identical output for both RMF settings) — no caveat NOTE
    assert "is inferred" not in code


def test_scaffold_findreplace_whole_match_rmf_false_still_keeps_last() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "key_a",
            "FieldSearch": "key_b",
            "FindMode": "FindWhole",
            "ReplaceMode": "Append",
            "ReplaceMultipleFound": {"@value": "False"},
            "ReplaceAppendFields": {"Field": [{"@field": "val"}]},
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    # ReplaceMultipleFound has no observed effect in Append mode: the same
    # duplicate-key workflow produced identical output with RMF=True and
    # RMF=False (golden-verified), so keep="last" is generated for both
    assert '.drop_duplicates("key_b", keep="last")' in code
    assert 'keep="first"' not in code
    assert "is inferred" not in code
    assert 'left_on="key_a"' in code
    assert 'right_on="key_b"' in code
    assert 'how="left"' in code
    # the right_on key column stays in the merge output on purpose: real
    # Alteryx FindWhole carries the search key column into the Append output
    # automatically (golden-verified) — asymmetric with FindAny
    assert ".drop(columns=" not in code


def test_scaffold_findreplace_replace_mode_lookup_map() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "Code",
            "FieldSearch": "OldCode",
            "ReplaceFoundField": "NewCode",
            "FindMode": "FindWhole",
            "ReplaceMode": "Replace",
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    assert '_MAP_3 = dict(zip(df_2["OldCode"], df_2["NewCode"]))' in code
    assert '"Code"' in code


def test_scaffold_findreplace_findany_append_helper_call() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "ID_A",
            "FieldSearch": "ID_A",
            "FindMode": "FindAny",
            "ReplaceMode": "Append",
            "ReplaceMultipleFound": {"@value": "True"},
            "ReplaceAppendFields": {
                "Field": [{"@field": "col_a"}, {"@field": "col_b"}],
            },
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    assert "find_any_append(" in code
    assert 'find_field="ID_A"' in code
    # FieldFind == FieldSearch: the helper output is "Targets columns +
    # append_fields" only — the search value is never added to the output, so
    # the key column is not duplicated and no rename/drop workaround is needed.
    assert 'search_field="ID_A"' in code
    assert ".rename(columns=" not in code
    assert ".drop(columns=" not in code
    assert 'append_fields=["col_a", "col_b"]' in code
    assert "case_sensitive=True" in code
    # ReplaceMultipleFound has no effect on Append output (golden-verified),
    # so the generated call must not emit it — showing it would suggest the
    # setting matters
    assert "replace_multiple_found" not in code
    assert 'log_label="ToolID_3"' in code
    # collect_match_diagnostics is emitted as False, matching the helper's
    # default: the ambiguity scan costs one pandas pass per Source row, so a
    # large lookup pays tens of seconds for a table nobody asked for. It is
    # still emitted (not omitted) so the line to flip while reviewing a
    # translation stays visible.
    # match the argument line itself, not the comment that names the flag
    assert "    collect_match_diagnostics=False,\n" in code
    assert "    collect_match_diagnostics=True,\n" not in code
    assert "set collect_match_diagnostics=True to log the ambiguous matches" in code
    # substring semantics live inside the helper — no equality join emitted
    assert "pd.merge" not in code
    assert "TODO: Find Replace" not in code
    assert "# NOTE: find_any_append() is not generated" in code


def test_scaffold_findreplace_findany_rmf_not_emitted() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "key_a",
            "FieldSearch": "key_b",
            "FindMode": "FindAny",
            "ReplaceMode": "Append",
            "ReplaceMultipleFound": {"@value": "False"},
            "ReplaceAppendFields": {"Field": [{"@field": "val"}]},
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    # ReplaceMultipleFound (either setting) has no effect on Append output
    # (golden-verified), so the XML tag must not surface in the generated
    # call, and substring semantics stay inside the helper
    assert "replace_multiple_found" not in code
    assert "drop_duplicates" not in code
    assert "duplicated().any()" not in code
    assert "pd.merge" not in code
    assert "TODO: Find Replace" not in code


def test_scaffold_findreplace_findany_nocase_maps_to_case_insensitive() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "key_a",
            "FieldSearch": "key_b",
            "FindMode": "FindAny",
            "ReplaceMode": "Append",
            "NoCase": {"@value": "True"},
            "ReplaceAppendFields": {"Field": [{"@field": "val"}]},
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    assert "case_sensitive=False" in code


def test_scaffold_findreplace_findany_replace_mode_falls_back() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "Name",
            "FieldSearch": "Fragment",
            "FindMode": "FindAny",
            "ReplaceMode": "Replace",
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    # the TODO must name both axes so a reviewer can tell "cannot translate"
    # apart from "forgot to translate"
    assert "TODO: Find Replace" in code
    assert "FindMode='FindAny'" in code
    assert "ReplaceMode='Replace'" in code
    assert "input passed through unchanged" in code
    assert "df_3 = df_1" in code


def test_scaffold_findreplace_stale_replace_found_field_is_ignored() -> None:
    """A stale ReplaceFoundField must not select the Replace branch.

    The XML can retain settings for the non-selected mode (switching the GUI
    from Replace to Append leaves the old ReplaceFoundField tag behind), so
    ReplaceMode is the primary discriminator. Here ReplaceMode=Append but the
    append-field list is empty: the tool must fall back to the TODO
    passthrough, not build a lookup map from the stale tag.
    """
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "Code",
            "FieldSearch": "OldCode",
            "ReplaceFoundField": "NewCode",
            "FindMode": "FindWhole",
            "ReplaceMode": "Append",
        },
        "F",
        "R",
    )
    code = scaffold(doc)
    assert "_MAP_3" not in code
    assert ".map(" not in code
    assert "TODO: Find Replace" in code
    assert "ReplaceMode='Append'" in code


def test_scaffold_findreplace_targets_source_anchors_route_correctly() -> None:
    """Alteryx XML uses Targets/Source as FindReplace anchor names.

    Targets = main stream (FieldFind column lives here),
    Source  = lookup table (FieldSearch column lives here).
    Verify that tool 1 (Targets/main) is passed as the targets frame and
    tool 2 (Source/lookup) as the source frame of the helper call.
    """
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "key_a",
            "FieldSearch": "key_b",
            "FindMode": "FindAny",
            "ReplaceMode": "Append",
            "ReplaceMultipleFound": {"@value": "True"},
            "ReplaceAppendFields": {"Field": [{"@field": "val"}]},
        },
        "Targets",  # tool 1 → main stream
        "Source",  # tool 2 → lookup table
    )
    code = scaffold(doc)
    # tool 1 (Targets / main) first, tool 2 (Source / lookup) second
    assert "find_any_append(\n        df_1,\n        df_2," in code
    assert 'find_field="key_a"' in code
    assert 'search_field="key_b"' in code
    # distinct find/search names: no rename/drop workaround emitted
    assert ".rename(columns=" not in code
    assert ".drop(columns=" not in code


# ── Append Fields ──────────────────────────────────────────────────────────


def test_scaffold_appendfields_cross_join() -> None:
    doc = _two_input_doc(
        "AppendFields",
        {"CartesianMode": "Error"},
        "Targets",
        "Sources",
    )
    code = scaffold(doc)
    assert 'df_3 = pd.merge(df_1, df_2, how="cross")' in code
    assert "unsupported tool type" not in code


# ── Spatial (CreatePoints / SpatialMatch) ──────────────────────────────────


def test_scaffold_createpoints_geopandas() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="CreatePoints",
            x=10,
            y=0,
            config={
                "Fields": {"@fieldX": "Longitude", "@fieldY": "Latitude"},
                "Mode": "Double",
            },
        )
    )
    code = scaffold(doc)
    assert "import geopandas as gpd" in code
    # the geometry column is Alteryx's hidden Centroid SpatialObj field;
    # the generated code must tell golden reviewers to drop it on the
    # comparison side instead of deleting it from the output
    assert "'geometry' is Alteryx's 'Centroid' SpatialObj field" in code
    assert "drop it on the comparison side, not here" in code
    # X/Y must be coerced to plain float64 before points_from_xy:
    # pd.NA (NAType) in nullable-dtype columns makes float() raise TypeError.
    assert (
        '_x = pd.to_numeric(df_1["Longitude"],'
        ' errors="coerce").astype("float64")' in code
    )
    assert (
        '_y = pd.to_numeric(df_1["Latitude"],'
        ' errors="coerce").astype("float64")' in code
    )
    assert "geometry=gpd.points_from_xy(_x, _y)" in code


def test_scaffold_spatialmatch_sjoin() -> None:
    doc = _two_input_doc(
        "SpatialMatch",
        {"Method": {"@method": "Intersects"}},
        "Targets",
        "Universe",
    )
    code = scaffold(doc)
    assert "import geopandas as gpd" in code
    assert "gpd.sjoin(" in code
    assert 'predicate="intersects"' in code
    # index_right is a pure sjoin artifact — Alteryx output never has it
    assert '.drop(columns=["index_right"])' in code


def _spatialmatch_doc_with_select(select_fields: list[dict]) -> WorkflowDoc:
    return _two_input_doc(
        "SpatialMatch",
        {
            "Method": {"@method": "Intersects"},
            "SelectConfiguration": {
                "Configuration": {
                    "@outputConnection": "Matched",
                    "SelectFields": {"SelectField": select_fields},
                }
            },
        },
        "Targets",
        "Universe",
    )


def test_scaffold_spatialmatch_default_embedded_select_no_warning() -> None:
    # All fields selected, no rename/type — the embedded Select is in its
    # default state, so the generated code must not carry the warning.
    doc = _spatialmatch_doc_with_select(
        [
            {"@field": "Target_ID", "@selected": "True", "@input": "Target_"},
            {"@field": "*Unknown", "@selected": "True"},
        ]
    )
    code = scaffold(doc)
    assert "embedded Select" not in code
    assert '.drop(columns=["index_right"])' in code


def test_scaffold_spatialmatch_embedded_select_deviation_warns() -> None:
    doc = _spatialmatch_doc_with_select(
        [
            {"@field": "Target_ID", "@selected": "True", "@input": "Target_"},
            {"@field": "Universe_Area", "@selected": "False", "@input": "Universe_"},
            {
                "@field": "Target_Name",
                "@selected": "True",
                "@rename": "名称",
                "@input": "Target_",
            },
            {
                "@field": "Universe_Code",
                "@selected": "True",
                "@type": "Int32",
                "@input": "Universe_",
            },
        ]
    )
    code = scaffold(doc)
    assert "embedded Select deviates" in code
    assert "#   deselected: Universe_Area" in code
    assert "#   renamed: Target_Name -> 名称" in code
    assert "#   type changed: Universe_Code (Int32)" in code
    # the warning must not turn into executable (silently no-op) edits
    assert "apply_select_edits(" not in code
    assert '.drop(columns=["index_right"])' in code


def test_scaffold_spatialmatch_unmatched_select_config_ignored() -> None:
    # Only the Matched output's embedded Select matters — the generated
    # sjoin is the Matched stream (how="inner").
    doc = _two_input_doc(
        "SpatialMatch",
        {
            "Method": {"@method": "Intersects"},
            "SelectConfiguration": {
                "Configuration": {
                    "@outputConnection": "Unmatched",
                    "SelectFields": {
                        "SelectField": [{"@field": "Target_ID", "@selected": "False"}]
                    },
                }
            },
        },
        "Targets",
        "Universe",
    )
    code = scaffold(doc)
    assert "embedded Select" not in code


def _spatialinfo_doc(
    items: list[dict] | dict, field: str = "SpatialObj"
) -> WorkflowDoc:
    return _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="SpatialInfo",
            x=10,
            y=0,
            config={
                "SpatialObj": {"@field": field},
                "SelectedItems": {"Item": items},
            },
        )
    )


def test_scaffold_spatialinfo_centroid() -> None:
    # Alteryx names the new field after the item — its output MetaInfo tags
    # it source="SpatialInfo: CentroidObj Source=SpatialObj" — and the tool
    # has no rename UI, so "Centroid" is fixed.
    code = scaffold(_spatialinfo_doc({"@name": "CentroidObj"}))
    assert "import geopandas as gpd" in code
    assert (
        '    df_1["SpatialObj"] if "SpatialObj" in df_1.columns else df_1.geometry,'
        in code
    )
    assert '    crs="EPSG:4326",' in code
    assert "df_2 = df_1.copy()" in code
    assert 'df_2["Centroid"] = _geom.centroid' in code
    # a Centroid column never reaches a golden CSV, same as geometry
    assert "drop it" in code
    assert "TODO: Spatial Info" not in code


def test_scaffold_spatialinfo_untranslated_items_stay_todo() -> None:
    # Area/Length are numeric columns golden CSVs do compare, and EPSG:4326
    # measures in degrees — emitting .area here would be a wrong number, so
    # only the CentroidObj half is translated (the _findreplace rule).
    code = scaffold(_spatialinfo_doc([{"@name": "CentroidObj"}, {"@name": "Area"}]))
    assert 'df_2["Centroid"] = _geom.centroid' in code
    assert "# TODO: Spatial Info — selected items not translated: Area" in code
    assert "projected CRS" in code
    assert ".area" not in code


def test_scaffold_spatialinfo_no_translatable_item_passes_through() -> None:
    code = scaffold(_spatialinfo_doc({"@name": "Area"}))
    assert "df_2 = df_1  # TODO: Spatial Info — no translatable items" in code
    assert "gpd.GeoSeries(" not in code
    # nothing spatial is emitted, so the block must not pull geopandas in
    assert "import geopandas as gpd" not in code


def test_scaffold_spatialinfo_without_spatial_field_is_todo() -> None:
    code = scaffold(_spatialinfo_doc({"@name": "CentroidObj"}, field=""))
    assert "df_2 = df_1  # TODO: Spatial Info — no input SpatialObj field" in code
    assert "_geom" not in code


def _distance_config(**overrides: object) -> dict:
    # The real node's configuration (ToolID anonymized): straight-line distance in
    # kilometers between two spatial fields of one record, plus a cardinal
    # direction. The drive-time settings are inert while
    # OutputDriveTimeAndDistance is False.
    config: dict = {
        "OutputDistance": {"@value": "True"},
        "ReturnNearest": {"@value": "False"},
        "DistToInsideEdge": {"@value": "True"},
        "OutputDriveTimeAndDistance": {"@value": "False"},
        "SpatialObjSource": {"#text": "Centroid"},
        "SpatialObjDest": {"#text": "SpatialObj"},
        "DriveTimeDataSet": {"#text": "Latest"},
        "AllowReverseRoute": {"@value": "True"},
        "MaxDriveTime": {"@value": "30"},
        "DriveDistanceOnly": {"@value": "False"},
        "OutputCardinalDirection": {"@value": "True"},
        "OutputDirectionDegrees": {"@value": "False"},
        "IsMetric": {"@value": "True"},
        "OutputUnits": {"#text": "Kilometers"},
    }
    config.update(overrides)
    return config


def _distance_doc(**overrides: object) -> WorkflowDoc:
    return _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Distance",
            x=10,
            y=0,
            config=_distance_config(**overrides),
        )
    )


def test_scaffold_distance_measures_in_a_metric_crs() -> None:
    # EPSG:4326 measures in degrees, but the tool outputs kilometers, so both
    # operands project into one UTM zone estimated from the data. EPSG:3857
    # would overstate by 1/cos(latitude) and must not appear.
    code = scaffold(_distance_doc())
    assert "_crs_m = _src.estimate_utm_crs()" in code
    assert "3857" not in code
    # the output field name is Distance + the XML's OutputUnits spelling,
    # confirmed by the node's MetaInfo (DistanceKilometers)
    assert 'df_2["DistanceKilometers"] = (' in code
    assert "_src.to_crs(_crs_m).distance(_dst.to_crs(_crs_m).boundary) / 1000" in code
    # a Double column golden CSVs compare — the block must not imply parity
    assert "WARNING: this is a planar UTM distance" in code


def test_scaffold_distance_guards_an_unestimatable_crs() -> None:
    # estimate_utm_crs() derives the zone from total_bounds, so it raises
    # ValueError("NaN or None values are not allowed.") when every geometry
    # is missing or empty, or there are no rows. Alteryx returns null
    # distances there instead of failing, so the block must not crash.
    code = scaffold(_distance_doc())
    assert "if pd.notna(_src.total_bounds).all():" in code
    assert "    _crs_m = _src.estimate_utm_crs()" in code
    assert "no usable Centroid geometry" in code
    assert 'df_2["DistanceKilometers"] = float("nan")' in code


def test_scaffold_simple_distance_sets_up_a_logger() -> None:
    # The empty-geometry branch warns, so the .md header must declare one.
    code = scaffold_simple(_distance_doc())
    assert "import logging" in code
    assert "logger = logging.getLogger(__name__)" in code


def test_scaffold_distance_reads_both_fields_from_one_record() -> None:
    # Source and Destination name two spatial columns of the same frame; the
    # Centroid is the column Spatial Info added upstream, so it resolves by
    # name, while SpatialObj falls back to the active geometry.
    code = scaffold(_distance_doc())
    assert "_src = gpd.GeoSeries(" in code
    assert 'df_1["Centroid"] if "Centroid" in df_1.columns else df_1.geometry' in code
    assert (
        'df_1["SpatialObj"] if "SpatialObj" in df_1.columns else df_1.geometry' in code
    )


def test_scaffold_distance_inside_edge_measures_to_the_boundary() -> None:
    # DistToInsideEdge=True means a source inside the polygon reports the
    # distance to the nearest edge instead of 0 — .boundary does exactly
    # that, and outside the polygon it is identical to plain .distance.
    assert ".boundary)" in scaffold(_distance_doc())
    plain = scaffold(_distance_doc(DistToInsideEdge={"@value": "False"}))
    assert "_src.to_crs(_crs_m).distance(_dst.to_crs(_crs_m)) / 1000" in plain
    assert ".boundary" not in plain


def test_scaffold_distance_converts_to_the_configured_unit() -> None:
    miles = scaffold(_distance_doc(OutputUnits={"#text": "Miles"}))
    assert 'df_2["DistanceMiles"] = (' in miles
    assert "/ 1609.344" in miles
    # metres need no conversion, so no division is emitted
    meters = scaffold(_distance_doc(OutputUnits={"#text": "Meters"}))
    assert 'df_2["DistanceMeters"] = (' in meters
    assert "/ 1" not in meters


def test_scaffold_distance_unknown_unit_is_todo() -> None:
    code = scaffold(_distance_doc(OutputUnits={"#text": "Leagues"}))
    assert "# TODO: Distance — unknown OutputUnits 'Leagues'" in code
    assert "df_2 = df_1" in code
    assert "estimate_utm_crs" not in code


def test_scaffold_distance_direction_stays_todo() -> None:
    # Direction is an 8-point compass string (its MetaInfo declares size=2),
    # but which point of a polygon destination the bearing runs to is not
    # settled by the XML, so it is never generated.
    code = scaffold(_distance_doc())
    assert '# TODO: Distance — "Direction" (8-point compass) is not translated' in code
    assert "Centroid -> SpatialObj" in code
    # …while the distance half is still real code
    assert 'df_2["DistanceKilometers"]' in code


def test_scaffold_distance_drive_time_mode_is_todo() -> None:
    code = scaffold(_distance_doc(OutputDriveTimeAndDistance={"@value": "True"}))
    assert "# TODO: Distance — drive-time/drive-distance mode" in code
    assert "routing service" in code
    assert "estimate_utm_crs" not in code
    assert "import geopandas as gpd" not in code


def test_scaffold_distance_two_inputs_is_todo() -> None:
    # Two streams pair rows instead of reading two fields of one record, and
    # how ReturnNearest picks them is unverified.
    doc = _two_input_doc("Distance", _distance_config(), "Target", "Destination")
    code = scaffold(doc)
    assert "# TODO: Distance — two-input mode" in code
    assert "estimate_utm_crs" not in code


def _buffer_config(**overrides: object) -> dict:
    # The real node's configuration (ToolID anonymized): a per-row buffer
    # size read from a field, in kilometers, generalized, keeping the object
    # it was built from in the output.
    config: dict = {
        "SpatialObjectField": {"#text": "SpatialObj"},
        "IncludeSourceInOutput": {"@value": "True"},
        "GeneralizeToOnePercent": {"@value": "True"},
        "BufferSizeSource": {"#text": "FromField"},
        "BufferSizeField": {"#text": "bufferSize"},
        "Units": {"#text": "Kilometers"},
    }
    config.update(overrides)
    return config


def _buffer_doc(**overrides: object) -> WorkflowDoc:
    return _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Buffer",
            x=10,
            y=0,
            config=_buffer_config(**overrides),
        )
    )


def test_scaffold_buffer_projects_buffers_and_comes_back() -> None:
    # EPSG:4326 buffers in degrees (a "1" is a ~90 km x 111 km ellipse at
    # Tokyo), so the buffer is drawn in an estimated UTM zone. Unlike
    # Distance, the result is geometry that stays in the frame, so the
    # excursion has to end back on the invariant CRS.
    code = scaffold(_buffer_doc())
    assert "import geopandas as gpd" in code
    assert "_crs_m = _geom.estimate_utm_crs()" in code
    assert "_buffered = _geom.to_crs(_crs_m).buffer(_dist_m)" in code
    assert '_buffered = _buffered.to_crs("EPSG:4326")' in code
    assert "3857" not in code


def test_scaffold_buffer_converts_the_size_field_to_metres() -> None:
    # BufferSizeSource=FromField: one size per row. to_numeric because
    # buffer() raises TypeError on a string size, and Units scales the
    # column into the metric CRS's unit.
    code = scaffold(_buffer_doc())
    assert (
        '_dist_m = pd.to_numeric(df_1["bufferSize"], errors="coerce").astype("float64")'
        in code
    )
    assert "_dist_m = _dist_m * 1000" in code
    miles = scaffold(_buffer_doc(Units={"#text": "Miles"}))
    assert "_dist_m = _dist_m * 1609.344" in miles
    # metres need no conversion, so no scaling is emitted
    meters = scaffold(_buffer_doc(Units={"#text": "Meters"}))
    assert "_dist_m = _dist_m *" not in meters


def test_scaffold_buffer_generalize_is_one_percent_of_the_size() -> None:
    # GEOS raises on a negative tolerance, and a negative buffer size
    # (shrinking a polygon) is a legal Alteryx setting, so the tolerance is
    # taken from the absolute size.
    code = scaffold(_buffer_doc())
    assert "_buffered = _buffered.simplify(_dist_m.abs() * 0.01)" in code
    plain = scaffold(_buffer_doc(GeneralizeToOnePercent={"@value": "False"}))
    assert "simplify" not in plain
    assert "_buffered = _geom.to_crs(_crs_m).buffer(_dist_m)" in plain


def test_scaffold_buffer_guards_an_unestimatable_crs() -> None:
    # Same guard as Distance: estimate_utm_crs() raises ValueError when
    # every geometry is missing or empty, or there are no rows, while
    # Alteryx just returns null objects there.
    code = scaffold(_buffer_doc())
    assert "if pd.notna(_geom.total_bounds).all():" in code
    assert "no usable SpatialObj geometry — the buffer is null" in code
    assert "    _buffered = _geom" in code


def test_scaffold_simple_buffer_sets_up_a_logger() -> None:
    code = scaffold_simple(_buffer_doc())
    assert "import logging" in code
    assert "logger = logging.getLogger(__name__)" in code


def test_scaffold_buffer_adds_a_field_named_after_its_input() -> None:
    # Buffer does not overwrite the object it buffered — its output MetaInfo
    # declares <Field name="SpatialObj_Buffer" type="SpatialObj"
    # source="Buffer: Source=SpatialObj …"/>, and the tool has no rename UI,
    # so "<input>_Buffer" is fixed.
    code = scaffold(_buffer_doc())
    assert 'df_2["SpatialObj_Buffer"] = _buffered' in code
    # the source object is still there, under its own name
    assert 'df_2["SpatialObj"] = _buffered' not in code


def test_scaffold_buffer_makes_the_buffer_the_active_geometry() -> None:
    # gen_spatialmatch joins on whatever geometry is active and ignores the
    # downstream node's SpatialObj= attribute, so leaving the source active
    # would sjoin against the un-buffered object without saying so.
    code = scaffold(_buffer_doc())
    assert 'df_2 = df_2.set_geometry("SpatialObj_Buffer")' in code
    assert code.index('df_2["SpatialObj_Buffer"] = _buffered') < code.index(
        'df_2 = df_2.set_geometry("SpatialObj_Buffer")'
    )


def test_scaffold_buffer_flags_a_dropped_source_object() -> None:
    # IncludeSourceInOutput=False means Alteryx's output carries only the
    # buffer. Dropping it here would cost the frame the geometry every
    # upstream tool built, and a SpatialObj never reaches a golden CSV, so
    # the block keeps it and says so instead.
    kept = scaffold(_buffer_doc())
    assert "IncludeSourceInOutput=False" not in kept
    dropped = scaffold(_buffer_doc(IncludeSourceInOutput={"@value": "False"}))
    assert "IncludeSourceInOutput=False: Alteryx's output has only the" in dropped
    assert 'df_2["SpatialObj_Buffer"] = _buffered' in dropped


def test_scaffold_buffer_fixed_size_is_todo() -> None:
    # Only FromField is confirmed by a real node's XML; the tag holding a
    # fixed size is not, so it is not guessed at.
    code = scaffold(_buffer_doc(BufferSizeSource={"#text": "Fixed"}))
    assert "# TODO: Buffer — BufferSizeSource 'Fixed' is not translated" in code
    assert "df_2 = df_1" in code
    assert "estimate_utm_crs" not in code
    assert "import geopandas as gpd" not in code


def test_scaffold_buffer_unknown_unit_is_todo() -> None:
    code = scaffold(_buffer_doc(Units={"#text": "Leagues"}))
    assert "# TODO: Buffer — unknown Units 'Leagues'" in code
    assert "estimate_utm_crs" not in code


def test_scaffold_buffer_without_spatial_field_is_todo() -> None:
    code = scaffold(_buffer_doc(SpatialObjectField={"#text": ""}))
    assert "# TODO: Buffer — no input SpatialObj field" in code
    assert "_geom" not in code


def test_scaffold_buffer_reads_fields_written_as_attributes() -> None:
    # Alteryx spells a field selector both ways — Spatial Info writes
    # <SpatialObj field="…"/>, Distance writes <SpatialObjSource>…</…> — and
    # reading only the text form turned a fully configured node into
    # "field not found", i.e. a TODO on a workflow that was fine.
    code = scaffold(
        _buffer_doc(
            SpatialObjectField={"@field": "SpatialObj"},
            BufferSizeField={"@field": "bufferSize"},
            Units={"@value": "Kilometers"},
            BufferSizeSource={"@value": "FromField"},
        )
    )
    assert "TODO: Buffer" not in code
    assert '_dist_m = pd.to_numeric(df_1["bufferSize"]' in code
    assert "_dist_m = _dist_m * 1000" in code
    assert 'df_2["SpatialObj_Buffer"] = _buffered' in code


def test_scaffold_distance_reads_fields_written_as_attributes() -> None:
    # Same tolerance on the tool whose text form is the verified one, so a
    # node spelled the other way does not silently degrade to a TODO.
    code = scaffold(
        _distance_doc(
            SpatialObjSource={"@field": "Centroid"},
            SpatialObjDest={"@field": "SpatialObj"},
            OutputUnits={"@value": "Kilometers"},
        )
    )
    assert 'df_2["DistanceKilometers"] = (' in code
    assert "# TODO: Distance — unknown OutputUnits" not in code


def test_scaffold_buffer_without_size_field_is_todo() -> None:
    code = scaffold(_buffer_doc(BufferSizeField={"#text": ""}))
    assert "# TODO: Buffer — BufferSizeSource=FromField, but BufferSizeField" in code
    assert "estimate_utm_crs" not in code


# ── Unsupported ────────────────────────────────────────────────────────────


def test_scaffold_unsupported_tool_todo() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="DynamicRename", x=0, y=0))
    code = scaffold(doc)
    assert "TODO" in code
    assert "df_1 = ..." in code


# ── Topo order ─────────────────────────────────────────────────────────────


def test_scaffold_topo_order() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[x] > 0"},
        ),
        AlteryxNode(
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0, config={"File": "a.csv"}
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert code.index("ToolID_1") < code.index("ToolID_2")


# ── node_code_snippets (inspect panel "python hint") ────────────────────────


def test_node_code_snippets_includes_filter() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 2 in snippets
    assert 'df_1["Age"] > 18' in snippets[2]


def test_node_code_snippets_includes_select() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={"SelectFields": {"SelectField": [{"@field": "Age"}]}},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 'SelectColumnEdit("Age")' in snippets[2]


def test_node_code_snippets_excludes_input_output() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": "a.csv"},
        ),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="OutputData",
            x=10,
            y=0,
            config={"File": "out.csv"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 1 not in snippets
    assert 2 not in snippets


# ── Requirement declarations drive header/preamble imports ─────────────────


def test_scaffold_createpoints_todo_fallback_skips_geopandas_import() -> None:
    # No X/Y fields → the generator emits a passthrough TODO with no gpd
    # code, so it declares no GEOPANDAS requirement and neither output
    # imports geopandas (previously the segment scan imported it anyway).
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="CreatePoints",
            x=10,
            y=0,
            config={},
        )
    )
    assert "import geopandas as gpd" not in scaffold(doc)
    assert "import geopandas as gpd" not in scaffold_simple(doc)
    assert "TODO: Create Points" in scaffold(doc)


def test_scaffold_simple_spatial_input_imports_geopandas() -> None:
    # gpd.read_file comes from the Input generator, which declares
    # GEOPANDAS itself — no spatial tool in the workflow.
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": r"C:\data\areas.geojson"},
        ),
    )
    code = scaffold_simple(doc)
    assert "import geopandas as gpd" in code
    assert "gpd.read_file" in code


def test_scaffold_simple_formula_numpy_import_follows_translation() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {
                        "@field": "flag",
                        "@expression": "IIF([x] > 0, 1, 0)",
                    }
                }
            },
        )
    )
    code = scaffold_simple(doc)
    assert "import numpy as np" in code


def test_scaffold_simple_no_numpy_import_without_numpy_emission() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Formula",
            x=10,
            y=0,
            config={
                "FormulaFields": {
                    "FormulaField": {
                        "@field": "total",
                        "@expression": "[Price] * [Qty]",
                    }
                }
            },
        )
    )
    code = scaffold_simple(doc)
    assert "import numpy as np" not in code
