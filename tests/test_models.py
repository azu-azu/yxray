"""Model contract tests for Phase 1: Scaffold and Data Models.

Tests verify:
1. All six dataclasses construct correctly with typed fields
2. Default values are correct (empty tuples/dicts, not None)
3. Frozen semantics raise FrozenInstanceError on mutation attempts
4. Single import surface: all 9 symbols importable from alteryx_git_companion.models
5. NewType aliases wrap correctly at runtime
"""

import dataclasses
from typing import Any

import pytest

from alteryx_git_companion.models import (
    AlteryxConnection,
    AlteryxNode,
    AnchorName,
    ConfigHash,
    DiffResult,
    EdgeDiff,
    NodeDiff,
    ToolID,
    WorkflowDoc,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_node() -> AlteryxNode:
    return AlteryxNode(
        tool_id=ToolID(1),
        tool_type="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
        x=100.0,
        y=200.0,
    )


@pytest.fixture()
def sample_connection() -> AlteryxConnection:
    return AlteryxConnection(
        src_tool=ToolID(1),
        src_anchor=AnchorName("1"),
        dst_tool=ToolID(2),
        dst_anchor=AnchorName("Input"),
    )


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestAlteryxNodeConstruction:
    def test_required_fields(self) -> None:
        node = AlteryxNode(
            tool_id=ToolID(42),
            tool_type="SomePlugin",
            x=50.5,
            y=75.0,
        )
        assert node.tool_id == ToolID(42)
        assert node.tool_type == "SomePlugin"
        assert node.x == 50.5
        assert node.y == 75.0

    def test_config_default_is_empty_dict(self, sample_node: AlteryxNode) -> None:
        assert sample_node.config == {}
        assert isinstance(sample_node.config, dict)

    def test_config_with_values(self) -> None:
        node = AlteryxNode(
            tool_id=ToolID(1),
            tool_type="Filter",
            x=0.0,
            y=0.0,
            config={"expression": "IIF([Field1] > 0, True, False)"},
        )
        assert node.config["expression"] == "IIF([Field1] > 0, True, False)"

    def test_position_is_flat_float_fields(self, sample_node: AlteryxNode) -> None:
        """x and y must be direct float fields — no nested Position type."""
        assert isinstance(sample_node.x, float)
        assert isinstance(sample_node.y, float)
        # Confirm fields exist directly on node, not nested
        assert hasattr(sample_node, "x")
        assert hasattr(sample_node, "y")
        assert not hasattr(sample_node, "position")


class TestAlteryxConnectionConstruction:
    def test_required_fields(self, sample_connection: AlteryxConnection) -> None:
        assert sample_connection.src_tool == ToolID(1)
        assert sample_connection.src_anchor == AnchorName("1")
        assert sample_connection.dst_tool == ToolID(2)
        assert sample_connection.dst_anchor == AnchorName("Input")


class TestWorkflowDocConstruction:
    def test_filepath_only(self) -> None:
        doc = WorkflowDoc(filepath="workflow.yxmd")
        assert doc.filepath == "workflow.yxmd"
        assert doc.nodes == ()
        assert doc.connections == ()

    def test_with_nodes_and_connections(
        self,
        sample_node: AlteryxNode,
        sample_connection: AlteryxConnection,
    ) -> None:
        doc = WorkflowDoc(
            filepath="workflow.yxmd",
            nodes=(sample_node,),
            connections=(sample_connection,),
        )
        assert len(doc.nodes) == 1
        assert len(doc.connections) == 1
        assert doc.nodes[0] is sample_node

    def test_connections_on_doc_not_node(self, sample_node: AlteryxNode) -> None:
        """AlteryxNode must be topology-free — no connections attribute."""
        assert not hasattr(sample_node, "connections")
        assert not hasattr(sample_node, "upstream")
        assert not hasattr(sample_node, "downstream")


class TestDiffModelsConstruction:
    def test_node_diff(self, sample_node: AlteryxNode) -> None:
        nd = NodeDiff(
            tool_id=ToolID(1),
            old_node=sample_node,
            new_node=sample_node,
            field_diffs={"x": (100.0, 200.0)},
        )
        assert nd.tool_id == ToolID(1)
        assert nd.field_diffs == {"x": (100.0, 200.0)}

    def test_node_diff_field_diffs_default(self, sample_node: AlteryxNode) -> None:
        nd = NodeDiff(tool_id=ToolID(1), old_node=sample_node, new_node=sample_node)
        assert nd.field_diffs == {}

    def test_edge_diff(self) -> None:
        ed = EdgeDiff(
            src_tool=ToolID(1),
            src_anchor=AnchorName("1"),
            dst_tool=ToolID(2),
            dst_anchor=AnchorName("Input"),
            change_type="added",
        )
        assert ed.change_type == "added"

    def test_diff_result_defaults(self) -> None:
        result = DiffResult()
        assert result.added_nodes == ()
        assert result.removed_nodes == ()
        assert result.modified_nodes == ()
        assert result.edge_diffs == ()

    def test_diff_result_with_data(self, sample_node: AlteryxNode) -> None:
        result = DiffResult(added_nodes=(sample_node,))
        assert len(result.added_nodes) == 1
        assert result.added_nodes[0] is sample_node


# ---------------------------------------------------------------------------
# Frozen semantics tests
# ---------------------------------------------------------------------------


class TestFrozenSemantics:
    def test_node_is_frozen(self, sample_node: AlteryxNode) -> None:
        # Direct assignment triggers frozen=True __setattr__ correctly.
        # Note: object.__setattr__ bypasses frozen enforcement when slots=True
        # is also set — direct attribute assignment is the correct test pattern.
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_node.tool_type = "OtherPlugin"  # type: ignore[misc]

    def test_connection_is_frozen(self, sample_connection: AlteryxConnection) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_connection.src_anchor = AnchorName("2")  # type: ignore[misc]

    def test_workflow_doc_is_frozen(self) -> None:
        doc = WorkflowDoc(filepath="test.yxmd")
        with pytest.raises(dataclasses.FrozenInstanceError):
            doc.filepath = "other.yxmd"  # type: ignore[misc]

    def test_diff_result_is_frozen(self) -> None:
        result = DiffResult()
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.added_nodes = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NewType runtime behavior
# ---------------------------------------------------------------------------


class TestNewTypeAliases:
    def test_tool_id_wraps_int(self) -> None:
        tid = ToolID(42)
        assert tid == 42
        assert isinstance(tid, int)

    def test_config_hash_wraps_str(self) -> None:
        ch = ConfigHash("abc123")
        assert ch == "abc123"
        assert isinstance(ch, str)

    def test_anchor_name_wraps_str(self) -> None:
        an = AnchorName("True")
        assert an == "True"
        assert isinstance(an, str)

    def test_all_symbols_importable(self) -> None:
        """All 9 symbols are importable from alteryx_git_companion.models."""
        symbols: list[Any] = [
            ToolID,
            ConfigHash,
            AnchorName,
            WorkflowDoc,
            AlteryxNode,
            AlteryxConnection,
            DiffResult,
            NodeDiff,
            EdgeDiff,
        ]
        assert len(symbols) == 9
        for sym in symbols:
            assert sym is not None
