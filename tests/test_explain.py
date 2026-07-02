from yxray.explain import ExplainStep, explain
from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc


def _doc(
    *nodes: AlteryxNode,
    connections: tuple[AlteryxConnection, ...] = (),
) -> WorkflowDoc:
    return WorkflowDoc(filepath="test.yxmd", nodes=nodes, connections=connections)


def test_explain_returns_explain_steps() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(tool_id=ToolID(2), tool_type="Filter", x=10, y=0),
    )
    steps = explain(doc)
    assert all(isinstance(s, ExplainStep) for s in steps)
    assert len(steps) == 2


def test_explain_input_data_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    steps = explain(doc)
    assert len(steps) == 1
    assert "pd.read_csv" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_dbfileinput_hint() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
            x=0,
            y=0,
        )
    )
    steps = explain(doc)
    assert "pd.read_csv" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_join_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="Join", x=0, y=0))
    steps = explain(doc)
    assert "pd.merge" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_summarize_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="Summarize", x=0, y=0))
    steps = explain(doc)
    assert "groupby" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_unsupported_tool_flagged() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="MultiFieldFormula", x=0, y=0))
    steps = explain(doc)
    assert steps[0].supported is False
    assert "TODO" in steps[0].python_hint


def test_explain_unknown_tool_falls_back() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="SomeFutureTool", x=0, y=0))
    steps = explain(doc)
    assert steps[0].supported is False
    assert "TODO" in steps[0].python_hint


def test_explain_topo_order() -> None:
    """Input tool (no predecessors) should appear before downstream tools."""
    doc = _doc(
        AlteryxNode(tool_id=ToolID(2), tool_type="Filter", x=10, y=0),
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    steps = explain(doc)
    ids = [s.tool_id for s in steps]
    assert ids.index(1) < ids.index(2)


def test_explain_filter_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="Filter", x=0, y=0))
    steps = explain(doc)
    assert "mask" in steps[0].python_hint
    assert "str.contains" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_union_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="Union", x=0, y=0))
    steps = explain(doc)
    assert "pd.concat" in steps[0].python_hint
    assert steps[0].supported is True


def test_explain_output_data_hint() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="OutputData", x=0, y=0))
    steps = explain(doc)
    assert "to_csv" in steps[0].python_hint
    assert steps[0].supported is True
