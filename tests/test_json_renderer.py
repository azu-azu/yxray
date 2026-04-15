"""Unit tests for JSONRenderer."""

from __future__ import annotations

import json

from alteryx_git_companion.models import AlteryxNode, DiffResult, EdgeDiff
from alteryx_git_companion.models.types import AnchorName, ToolID
from alteryx_git_companion.renderers import JSONRenderer

# --- fixture helpers ---


def _make_node(tool_id: int, tool_type: str = "Filter") -> AlteryxNode:
    return AlteryxNode(
        tool_id=ToolID(tool_id),
        tool_type=tool_type,
        x=0.0,
        y=0.0,
        config={},
    )


def _empty_result() -> DiffResult:
    return DiffResult(
        added_nodes=(),
        removed_nodes=(),
        modified_nodes=(),
        edge_diffs=(),
    )


# --- tests ---


def test_render_empty_diff_result() -> None:
    """render() on an empty DiffResult returns valid JSON with zero counts."""
    renderer = JSONRenderer()
    json_text = renderer.render(_empty_result())

    data = json.loads(json_text)

    assert data["summary"]["added"] == 0
    assert data["summary"]["removed"] == 0
    assert data["summary"]["modified"] == 0
    assert data["summary"]["connections"] == 0
    assert data["tools"] == []
    assert data["connections"] == []


def test_render_summary_counts() -> None:
    """summary counts match the actual DiffResult content."""
    node_a = _make_node(601, "Filter")
    node_b = _make_node(602, "Select")
    result = DiffResult(
        added_nodes=(node_a,),
        removed_nodes=(node_b,),
        modified_nodes=(),
        edge_diffs=(),
    )
    renderer = JSONRenderer()
    data = json.loads(renderer.render(result))

    assert data["summary"]["added"] == 1
    assert data["summary"]["removed"] == 1
    assert data["summary"]["modified"] == 0
    assert data["summary"]["connections"] == 0


def test_render_connections_count_matches_summary() -> None:
    """summary.connections always equals len(connections array)."""
    edge = EdgeDiff(
        src_tool=ToolID(601),
        src_anchor=AnchorName("Output"),
        dst_tool=ToolID(602),
        dst_anchor=AnchorName("Input"),
        change_type="added",
    )
    result = DiffResult(
        added_nodes=(),
        removed_nodes=(),
        modified_nodes=(),
        edge_diffs=(edge,),
    )
    renderer = JSONRenderer()
    data = json.loads(renderer.render(result))

    # Invariant: summary.connections == len(connections array)
    assert data["summary"]["connections"] == len(data["connections"])
    assert data["summary"]["connections"] == 1


def test_render_tools_sorted_alphabetically() -> None:
    """tools array is sorted alphabetically by tool_name."""
    node_z = _make_node(603, "ZTool")
    node_a = _make_node(604, "ATool")
    result = DiffResult(
        added_nodes=(node_z, node_a),
        removed_nodes=(),
        modified_nodes=(),
        edge_diffs=(),
    )
    renderer = JSONRenderer()
    data = json.loads(renderer.render(result))

    tool_names = [t["tool_name"] for t in data["tools"]]
    assert tool_names == sorted(tool_names)
    assert tool_names[0] == "ATool"
    assert tool_names[1] == "ZTool"


def test_render_connections_schema() -> None:
    """Each connection record has all required fields with correct types."""
    edge = EdgeDiff(
        src_tool=ToolID(601),
        src_anchor=AnchorName("Output"),
        dst_tool=ToolID(602),
        dst_anchor=AnchorName("Input"),
        change_type="removed",
    )
    result = DiffResult(
        added_nodes=(),
        removed_nodes=(),
        modified_nodes=(),
        edge_diffs=(edge,),
    )
    renderer = JSONRenderer()
    data = json.loads(renderer.render(result))

    conn = data["connections"][0]
    assert conn["src_tool"] == 601
    assert conn["src_anchor"] == "Output"
    assert conn["dst_tool"] == 602
    assert conn["dst_anchor"] == "Input"
    assert conn["change_type"] == "removed"
    assert isinstance(conn["src_tool"], int)  # not ToolID NewType
    assert isinstance(conn["src_anchor"], str)  # not AnchorName NewType
