from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.scaffold import node_code_snippets, scaffold


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
    assert 'df_1["Age"] > 18' in code
    assert "df_2 = df_1[" in code


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


def test_scaffold_select_emits_helpers() -> None:
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
    assert "from dataclasses import dataclass" in code
    assert "class SelectColumnEdit:" in code
    assert "def apply_select_edits(" in code


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
    assert "df_1" in code
    assert "df_2" in code


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
    assert "df_1" in code
    assert "df_2" in code


# ── Unsupported ────────────────────────────────────────────────────────────


def test_scaffold_unsupported_tool_todo() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="SpatialMatch", x=0, y=0))
    code = scaffold(doc)
    assert "TODO" in code
    assert "df_1 = ..." in code


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
    assert 'df_1["Age"] > 18' in snippets[2]


def test_node_code_snippets_excludes_select() -> None:
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
    assert 2 not in snippets


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
