
from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.scaffold import (
    node_code_snippets,
    scaffold,
    scaffold_simple,
)
from yxray.scaffold_filter import (
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
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
            config={"File": "master.xlsx"},
        )
    )
    code = scaffold(doc)
    assert 'INPUTS["input_1"]' in code
    assert "pd.read_excel" in code


def test_scaffold_input_csv() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": "data.csv"},
        )
    )
    code = scaffold(doc)
    assert 'INPUTS["input_1"]' in code
    assert "pd.read_csv" in code


def test_scaffold_input_paths_env_block() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
            config={"File": "data.csv"},
        )
    )
    code = scaffold(doc)
    assert 'ENV = os.getenv("APP_ENV", "test")' in code
    assert "BASE_DIR" in code
    assert 'parents[2]' in code
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'OUTPUTS["output_2"]' in code
    assert ".to_csv" in code


def test_scaffold_input_shp_uses_gpd_read_file() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.shp"},
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
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.shp"},
        )
    )
    code = scaffold(doc)
    assert "if df1.crs is None:" in code
    assert 'df1 = df1.set_crs("EPSG:4326")' in code
    assert 'df1 = df1.to_crs("EPSG:4326")' in code


def test_scaffold_simple_spatial_read_normalizes_crs_to_wgs84() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.gpkg"},
        )
    )
    code = scaffold_simple(doc)
    assert "if df1.crs is None:" in code
    assert 'df1 = df1.set_crs("EPSG:4326")' in code
    assert 'df1 = df1.to_crs("EPSG:4326")' in code


def test_scaffold_csv_read_has_no_crs_normalization() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\plain.csv"},
        )
    )
    assert "set_crs" not in scaffold(doc)


def test_scaffold_shp_restores_shx_once_in_preamble() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.shp"},
        ),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="DbFileInput", x=0, y=100,
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
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.gpkg"},
        )
    )
    assert "SHAPE_RESTORE_SHX" not in scaffold(doc)


def test_scaffold_simple_shp_notes_shx_restore() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.shp"},
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
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": r"C:\data\mesh.gpkg"},
        )
    )
    code = scaffold_simple(doc)
    assert "SHAPE_RESTORE_SHX" not in code
    assert "import os" not in code


def test_scaffold_windows_path_extracts_filename_in_test_block() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
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
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df1["Age"] > 18' in code
    assert "df2 = df1[" in code


def test_scaffold_filter_date_comparison_warning() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": '[日付列] >= ToDate("2024-01-01")'},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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


def test_scaffold_filter_isempty_plus_date_gets_precise_and_residual_warnings() -> (
    None
):
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
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'column "日付列A" is compared as a date in cond_2' in code
    assert "IsEmpty's == \"\" check on \"日付列A\"" in code
    assert 'verify the type of column "日付列B" too' in code
    assert "IsEmpty == \"\" check becomes always False afterward" in code


def test_scaffold_filter_isnull_with_date_has_no_dead_code_note() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={
                "Expression": 'IsNull([DateCol]) OR [DateCol] >= ToDate("2024-01-01")'
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Mode": "Simple", "Simple": simple_config},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
    assert 'df2 = df1[df1["CAPEX/OPEX"] == "CAPEX"]' in code
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
    assert 'df2 = df1[df1["Amount"] > 100]' in code


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
        'df2 = df1[df1["Name"].str.contains("ta.ro", regex=False, na=False)]'
        in code
    )


def test_scaffold_filter_simple_mode_is_null() -> None:
    doc = _simple_filter_doc({"Operator": "IsNull", "Field": "Amount"})
    code = scaffold(doc)
    assert 'df2 = df1[df1["Amount"].isna()]' in code


def test_scaffold_filter_simple_mode_unknown_operator_falls_back() -> None:
    doc = _simple_filter_doc(
        {
            "Operator": "InThePast",
            "Field": "Date",
            "Operands": {"Operand": ""},
        }
    )
    code = scaffold(doc)
    assert "df2 = df1  # TODO: Filter expression missing" in code


# ── Filter mask splitting (issue #33) ──────────────────────────────────────


def _expr_filter_doc(expr: str) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": expr},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_filter_three_operands_split_into_masks() -> None:
    code = scaffold_simple(_expr_filter_doc("[a] = 1 AND [b] = 2 AND [c] = 3"))
    assert "# [a] = 1" in code
    assert 'cond_1 = df1["a"] == 1' in code
    assert "# [b] = 2" in code
    assert 'cond_2 = df1["b"] == 2' in code
    assert "# [c] = 3" in code
    assert 'cond_3 = df1["c"] == 3' in code
    assert "df2 = df1[cond_1 & cond_2 & cond_3]" in code


def test_scaffold_filter_or_chain_split_joins_with_pipe() -> None:
    code = scaffold_simple(_expr_filter_doc("[a] = 1 OR [b] = 2 OR [c] = 3"))
    assert "df2 = df1[cond_1 | cond_2 | cond_3]" in code


def test_scaffold_filter_two_long_operands_split_into_masks() -> None:
    # The issue #33 headline example: two negated conditions whose one-line
    # form exceeds the 88-column limit.
    code = scaffold_simple(
        _expr_filter_doc('!Contains([Status], "drop") AND !IsEmpty([Status])')
    )
    assert '# !Contains([Status], "drop")' in code
    assert (
        "cond_1 = ~df1[\"Status\"].str.contains('drop', case=False,"
        " regex=False, na=False)" in code
    )
    assert "# !IsEmpty([Status])" in code
    assert 'cond_2 = ~(df1["Status"].isna() | (df1["Status"] == ""))' in code
    assert "df2 = df1[cond_1 & cond_2]" in code


def test_scaffold_filter_two_short_operands_stay_one_line() -> None:
    code = scaffold_simple(_expr_filter_doc('[Age] > 18 AND [Status] = "Active"'))
    assert "df2 = df1[(df1[\"Age\"] > 18) & (df1[\"Status\"] == 'Active')]" in code
    assert "cond_1" not in code


def test_scaffold_filter_line_length_boundary_88_stays_one_line() -> None:
    # One-line form is exactly 88 columns — at the limit, not over it.
    field = "x" * 33
    code = scaffold_simple(
        _expr_filter_doc(f'[{field}] > 18 AND [Status] = "Active"')
    )
    line = f"df2 = df1[(df1[\"{field}\"] > 18) & (df1[\"Status\"] == 'Active')]"
    assert len(line) == 88
    assert line in code
    assert "cond_1" not in code


def test_scaffold_filter_line_length_boundary_89_splits() -> None:
    # One character longer than the previous test: 89 columns — splits.
    field = "x" * 34
    code = scaffold_simple(
        _expr_filter_doc(f'[{field}] > 18 AND [Status] = "Active"')
    )
    assert f'cond_1 = df1["{field}"] > 18' in code
    assert "cond_2 = df1[\"Status\"] == 'Active'" in code
    assert "df2 = df1[cond_1 & cond_2]" in code


def test_scaffold_filter_multiline_expression_comment_not_broken() -> None:
    expr = '!Contains([Status],\n    "drop")\nAND !IsEmpty([Status])\nAND [a] = 1'
    code = scaffold_simple(_expr_filter_doc(expr))
    assert '# !Contains([Status], "drop")' in code
    assert "df2 = df1[cond_1 & cond_2 & cond_3]" in code
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
    assert 'df1["a"] ?? weird AND df1["b"] ?? syntax' in code


# ── Formula ────────────────────────────────────────────────────────────────


def test_scaffold_formula_translates_if_expression() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Formula", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "import numpy as np" in code
    assert (
        "np.select([df2[\"Score\"] >= 80, df2[\"Score\"] >= 60],"
        " ['A', 'B'], default='C')" in code
    )
    assert "THEN" not in code


def test_scaffold_filter_boolean_expression_parenthesized() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": '[Age] > 18 AND [Status] = "Active"'},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "(df1[\"Age\"] > 18) & (df1[\"Status\"] == 'Active')" in code
    assert "import numpy as np" not in code


def test_scaffold_formula_untranslatable_expression_falls_back() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Formula", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df2["x"] ?? weird syntax' in code


def test_scaffold_formula_field_name_with_space_is_valid_python() -> None:
    # Field names like "Sales Amount" are common in Alteryx; embedding them
    # as .assign() keyword arguments would produce a SyntaxError.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Formula", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'df2["Sales Amount"] = df2["Price"] * df2["Qty"]' in code
    # The whole scaffold must be syntactically valid Python.
    compile(code, "<scaffold>", "exec")


def test_scaffold_field_name_with_quote_stays_valid_python() -> None:
    # A double-quote in a field name would break naive '"{name}"' embedding;
    # every generator routes names through py_str, so the scaffold still
    # parses. Sort is one representative generator.
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Sort", x=10, y=0,
            config={
                "SortInfo": {
                    "Field": {"@field": 'weird"name', "@order": "Ascending"}
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(1), tool_type="TextInput", x=0, y=0,
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
            tool_id=ToolID(2), tool_type="Formula", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "df2 = df1.copy()" in code
    assert 'df2["Net"] = df2["Gross"] - df2["Tax"]' in code
    # Doubled reads Net from the built-up frame, not the original df1.
    assert 'df2["Doubled"] = df2["Net"] * 2' in code
    assert ".assign(" not in code


# ── Select ─────────────────────────────────────────────────────────────────


def test_scaffold_select_columns() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert 'SelectColumnEdit("amount", type="Double")' in code
    assert (
        'SelectColumnEdit("old_col", new_name="new_col", type="V_WString")' in code
    )
    assert 'SelectColumnEdit("junk", selected=False)' in code
    assert 'SelectColumnEdit("plain")' in code


def test_scaffold_select_does_not_emit_helper_definitions() -> None:
    """Helper definitions are no longer embedded in the generated .py;
    the scaffold emits the call plus a NOTE to provide them separately."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
            config={
                "SelectFields": {
                    "SelectField": [{"@field": "Col", "@selected": "True"}]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "from dataclasses import dataclass" not in code
    assert "class SelectColumnEdit:" not in code
    assert "def apply_select_edits(" not in code
    assert (
        "# NOTE: SelectColumnEdit / apply_select_edits are not generated"
        in code
    )
    assert "apply_select_edits(df1, _COLS_2)" in code


def test_scaffold_select_always_warns_about_stale_xml() -> None:
    """Every Select block — scaffold, simple scaffold, and the panel's python
    hint — carries the always-on warning that Select XML can be stale and
    must be verified against the Alteryx GUI."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
            config={
                "SelectFields": {
                    "SelectField": [{"@field": "Name", "@selected": "True"}]
                }
            },
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Select", x=10, y=0, config={},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_browse_logs_row_count() -> None:
    code = scaffold(_browse_doc())
    assert 'logger.info("ToolID 2 (Browse): rows=%d", len(df1))' in code
    assert "unsupported tool type" not in code


def test_scaffold_simple_browse_defines_logger() -> None:
    code = scaffold_simple(_browse_doc())
    assert "import logging" in code
    assert "logger = logging.getLogger(__name__)" in code
    assert 'logger.info("ToolID 2 (Browse): rows=%d", len(df1))' in code


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
            tool_id=ToolID(3), tool_type="Join", x=100, y=50,
            config={"JoinExpression": "[L:CustomerID] = [R:CustomerID]"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Right"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "pd.merge" in code
    assert '"CustomerID"' in code
    assert "df1, df2" in code


def test_scaffold_join_different_keys() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="InputData", x=0, y=100),
        AlteryxNode(
            tool_id=ToolID(3), tool_type="Join", x=100, y=50,
            config={"JoinExpression": "[L:OrdID] = [R:OrderID]"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Right"),
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
            tool_id=ToolID(3), tool_type="Join", x=100, y=50,
            config={"JoinExpression": "messy\nmulti-line cond"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Right"),
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
            tool_id=ToolID(2), tool_type="Summarize", x=10, y=0,
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
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
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Input1"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Input2"),
            ),
        ),
    )
    code = scaffold(doc)
    assert "pd.concat" in code
    assert "pd.concat([df1, df2], ignore_index=True)" in code


# ── Sort / Unique ──────────────────────────────────────────────────────────


def _chain_doc(second: AlteryxNode) -> WorkflowDoc:
    return _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        second,
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def test_scaffold_sort_reads_nested_field_rows() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Sort", x=10, y=0,
            config={
                "SortInfo": {
                    "@locale": "2631851",
                    "Field": {"@field": "工事完了予定日(p)", "@order": "Descending"},
                }
            },
        )
    )
    code = scaffold(doc)
    assert 'df2 = df1.sort_values(["工事完了予定日(p)"], ascending=[False])' in code


def test_scaffold_sort_multiple_fields() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Sort", x=10, y=0,
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
    assert 'df2 = df1.sort_values(["A", "B"], ascending=[True, False])' in code


def test_scaffold_unique_uses_subset() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Unique", x=10, y=0,
            config={"UniqueFields": {"Field": {"@field": "EL_ID"}}},
        )
    )
    code = scaffold(doc)
    assert 'df2 = df1.drop_duplicates(subset=["EL_ID"])' in code


def test_scaffold_unique_without_fields_keeps_default() -> None:
    doc = _chain_doc(
        AlteryxNode(tool_id=ToolID(2), tool_type="Unique", x=10, y=0)
    )
    code = scaffold(doc)
    assert "df2 = df1.drop_duplicates()" in code


# ── Text Input ─────────────────────────────────────────────────────────────


def test_scaffold_text_input_builds_dataframe() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="TextInput", x=0, y=0,
            config={
                "NumRows": {"@value": "3"},
                "Fields": {"Field": {"@name": "進捗"}},
                "Data": {
                    "r": [
                        {"c": {"#text": "No Progress-Initial Design"}},
                        {"c": "TSS-TI Ready"},
                        {"c": "On Air"},
                    ]
                },
            },
        )
    )
    code = scaffold(doc)
    assert "df1 = pd.DataFrame({" in code
    assert (
        '"進捗": ["No Progress-Initial Design", "TSS-TI Ready", "On Air"],' in code
    )


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
        AlteryxNode(
            tool_id=ToolID(3), tool_type=tool_type, x=10, y=0, config=config
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName(anchor_a),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName(anchor_b),
            ),
        ),
    )


def test_scaffold_findreplace_append_mode_left_join() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "EL_ID",
            "FieldSearch": "EL_ID",
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
    assert 'df2[["EL_ID", "フィールドA", "フィールドB"]]' in code
    assert 'on="EL_ID"' in code
    assert 'how="left"' in code
    assert "unsupported tool type" not in code
    # duplicate lookup keys must not grow the row count: the lookup side is
    # deduplicated before the join and the last duplicate wins
    assert '.drop_duplicates("EL_ID", keep="last")' in code
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
    assert '_MAP_3 = dict(zip(df2["OldCode"], df2["NewCode"]))' in code
    assert '"Code"' in code


def test_scaffold_findreplace_findany_append_helper_call() -> None:
    doc = _two_input_doc(
        "FindReplace",
        {
            "FieldFind": "EL_ID",
            "FieldSearch": "EL_ID",
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
    assert "simulate_find_any_append(" in code
    assert 'find_field="EL_ID"' in code
    # FieldFind == FieldSearch: the helper output is "Targets columns +
    # append_fields" only — the search value is never added to the output, so
    # the key column is not duplicated and no rename/drop workaround is needed.
    assert 'search_field="EL_ID"' in code
    assert ".rename(columns=" not in code
    assert ".drop(columns=" not in code
    assert 'append_fields=["col_a", "col_b"]' in code
    assert "case_sensitive=True" in code
    # ReplaceMultipleFound has no effect on Append output (golden-verified),
    # so the generated call must not emit it — showing it would suggest the
    # setting matters
    assert "replace_multiple_found" not in code
    assert 'log_label="ToolID 3"' in code
    # substring semantics live inside the helper — no equality join emitted
    assert "pd.merge" not in code
    assert "TODO: Find Replace" not in code
    assert "# NOTE: simulate_find_any_append() is not generated" in code


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
    assert "df3 = df1" in code


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
        "Source",   # tool 2 → lookup table
    )
    code = scaffold(doc)
    # tool 1 (Targets / main) first, tool 2 (Source / lookup) second
    assert "simulate_find_any_append(\n        df1,\n        df2," in code
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
    assert 'df3 = pd.merge(df1, df2, how="cross")' in code
    assert "unsupported tool type" not in code


# ── Spatial (CreatePoints / SpatialMatch) ──────────────────────────────────


def test_scaffold_createpoints_geopandas() -> None:
    doc = _chain_doc(
        AlteryxNode(
            tool_id=ToolID(2), tool_type="CreatePoints", x=10, y=0,
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
        '_x = pd.to_numeric(df1["Longitude"],'
        ' errors="coerce").astype("float64")' in code
    )
    assert (
        '_y = pd.to_numeric(df1["Latitude"],'
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


# ── Unsupported ────────────────────────────────────────────────────────────


def test_scaffold_unsupported_tool_todo() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="DynamicRename", x=0, y=0))
    code = scaffold(doc)
    assert "TODO" in code
    assert "df1 = ..." in code


# ── Topo order ─────────────────────────────────────────────────────────────


def test_scaffold_topo_order() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
                    config={"Expression": "[x] > 0"}),
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
                    config={"File": "a.csv"}),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    code = scaffold(doc)
    assert code.index("ToolID 1") < code.index("ToolID 2")


# ── node_code_snippets (inspect panel "python hint") ────────────────────────


def test_node_code_snippets_includes_filter() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 2 in snippets
    assert 'df1["Age"] > 18' in snippets[2]


def test_node_code_snippets_includes_select() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
            config={"SelectFields": {"SelectField": [{"@field": "Age"}]}},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 'SelectColumnEdit("Age")' in snippets[2]


def test_node_code_snippets_excludes_input_output() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
            config={"File": "a.csv"},
        ),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="OutputData", x=10, y=0,
            config={"File": "out.csv"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    snippets = node_code_snippets(doc)
    assert 1 not in snippets
    assert 2 not in snippets
