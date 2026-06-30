from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.scaffold import scaffold


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


# ── Input / Output ──────────────────────────────────────────────────────────


def test_scaffold_input_excel() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
            config={"File": "master.xlsx"},
        )
    )
    code = scaffold(doc)
    assert 'df_1 = pd.read_excel("master.xlsx")' in code


def test_scaffold_input_csv() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="DbFileInput", x=0, y=0,
            config={"FileName": "data.csv"},
        )
    )
    code = scaffold(doc)
    assert 'df_1 = pd.read_csv("data.csv")' in code


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
    assert 'df_1.to_csv("out.csv", index=False)' in code


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
    assert '"Junk"' not in code


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
    assert "rename" in code
    assert '"new_col"' in code


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
