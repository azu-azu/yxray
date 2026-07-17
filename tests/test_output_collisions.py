"""Tests for output_collisions.detect_duplicate_outputs()."""

from __future__ import annotations

from yxray.models.types import ToolID
from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.output_collisions import detect_duplicate_outputs


def _output_node(
    tool_id: int, path: str, tool_type: str = "DbFileOutput"
) -> AlteryxNode:
    return AlteryxNode(
        tool_id=ToolID(tool_id),
        tool_type=tool_type,
        x=0.0,
        y=0.0,
        config={"File": path},
    )


def _doc(*nodes: AlteryxNode) -> WorkflowDoc:
    return WorkflowDoc(filepath="test.yxmd", nodes=nodes, connections=())


def test_no_warning_for_distinct_paths() -> None:
    doc = _doc(
        _output_node(1, r"C:\out\a.csv"),
        _output_node(2, r"C:\out\b.csv"),
    )
    assert detect_duplicate_outputs(doc) == []


def test_no_warning_for_single_output() -> None:
    doc = _doc(_output_node(1, r"C:\out\a.csv"))
    assert detect_duplicate_outputs(doc) == []


def test_two_outputs_sharing_a_path_each_warn_about_the_other() -> None:
    doc = _doc(
        _output_node(10, r"C:\out\same.kml"),
        _output_node(20, r"C:\out\same.kml"),
    )
    warnings = detect_duplicate_outputs(doc)

    assert len(warnings) == 2
    by_tool = {w.tool_id: w for w in warnings}
    assert by_tool[10].other_tool_ids == (20,)
    assert by_tool[20].other_tool_ids == (10,)
    assert "same.kml" in by_tool[10].message
    assert "Tool 20" in by_tool[10].message


def test_three_outputs_sharing_a_path_each_reference_the_other_two() -> None:
    doc = _doc(
        _output_node(1, r"C:\out\shared.csv"),
        _output_node(2, r"C:\out\shared.csv"),
        _output_node(3, r"C:\out\shared.csv"),
    )
    warnings = detect_duplicate_outputs(doc)

    assert len(warnings) == 3
    by_tool = {w.tool_id: w for w in warnings}
    assert by_tool[1].other_tool_ids == (2, 3)
    assert by_tool[2].other_tool_ids == (1, 3)
    assert by_tool[3].other_tool_ids == (1, 2)


def test_ignores_non_output_tools() -> None:
    doc = _doc(
        _output_node(1, r"C:\out\a.csv"),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="DbFileInput",
            x=0.0,
            y=0.0,
            config={"File": r"C:\out\a.csv"},
        ),
    )
    assert detect_duplicate_outputs(doc) == []


def test_ignores_outputs_with_no_configured_path() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="DbFileOutput", x=0.0, y=0.0),
        AlteryxNode(tool_id=ToolID(2), tool_type="DbFileOutput", x=0.0, y=0.0),
    )
    assert detect_duplicate_outputs(doc) == []
