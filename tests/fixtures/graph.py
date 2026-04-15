"""Graph renderer test fixtures.

ToolIDs 801-820: reserved for Phase 8 graph fixtures.
No collision with Phase 7 (701-720) or prior phases.
"""

from __future__ import annotations

from alteryx_git_companion.models.diff import DiffResult, EdgeDiff, NodeDiff
from alteryx_git_companion.models.types import AnchorName, ToolID
from alteryx_git_companion.models.workflow import AlteryxConnection, AlteryxNode

# --- Node builders (with distinct canvas positions for canvas_layout tests) ---


def _node(
    tid: int, tool_type: str, x: float = 0.0, y: float = 0.0, config: dict | None = None
) -> AlteryxNode:
    return AlteryxNode(
        tool_id=ToolID(tid),
        tool_type=tool_type,
        x=x,
        y=y,
        config=config or {},
    )


# --- Fixture: EMPTY_DIFF ---
# All nodes unchanged; no additions/removals/modifications/edge_diffs
NODE_UNCHANGED_A = _node(801, "InputData", x=0.0, y=0.0)
NODE_UNCHANGED_B = _node(802, "Select", x=200.0, y=0.0)
CONN_A_TO_B = AlteryxConnection(
    src_tool=ToolID(801),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(802),
    dst_anchor=AnchorName("Input"),
)
EMPTY_DIFF = DiffResult()

# --- Fixture: ADDED_NODE ---
# One node added to new workflow; edges from new workflow
NODE_ADDED = _node(803, "Formula", x=400.0, y=0.0)
ADDED_DIFF = DiffResult(added_nodes=(NODE_ADDED,))

# --- Fixture: REMOVED_NODE ---
NODE_REMOVED = _node(804, "Filter", x=0.0, y=100.0)
REMOVED_DIFF = DiffResult(removed_nodes=(NODE_REMOVED,))

# --- Fixture: MODIFIED_NODE ---
NODE_MODIFIED_OLD = _node(
    805, "Select", x=200.0, y=100.0, config={"SelectField": "old_value"}
)
NODE_MODIFIED_NEW = _node(
    805, "Select", x=200.0, y=100.0, config={"SelectField": "new_value"}
)
MODIFIED_NODE_DIFF = NodeDiff(
    tool_id=ToolID(805),
    old_node=NODE_MODIFIED_OLD,
    new_node=NODE_MODIFIED_NEW,
    field_diffs={"SelectField": ("old_value", "new_value")},
)
MODIFIED_DIFF = DiffResult(modified_nodes=(MODIFIED_NODE_DIFF,))

# --- Fixture: CONNECTION_CHANGE ---
EDGE_ADDED = EdgeDiff(
    src_tool=ToolID(806),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(807),
    dst_anchor=AnchorName("Input"),
    change_type="added",
)
NODE_CONN_SRC = _node(806, "Join", x=0.0, y=200.0)
NODE_CONN_DST = _node(807, "Output", x=200.0, y=200.0)
CONN_CHANGED_DIFF = DiffResult(edge_diffs=(EDGE_ADDED,))

# --- Fixture: ALL_CHANGE_TYPES ---
# One node of each category for comprehensive color-mapping test
NODE_ALL_ADDED = _node(810, "InputData", x=0.0, y=0.0)
NODE_ALL_REMOVED = _node(811, "Union", x=200.0, y=0.0)
NODE_ALL_MOD_OLD = _node(812, "Formula", x=400.0, y=0.0, config={"expr": "x+1"})
NODE_ALL_MOD_NEW = _node(812, "Formula", x=400.0, y=0.0, config={"expr": "x+2"})
NODE_ALL_CONN_SRC = _node(813, "Select", x=0.0, y=100.0)
NODE_ALL_CONN_DST = _node(814, "Filter", x=200.0, y=100.0)
NODE_ALL_UNCHANGED = _node(815, "Browse", x=600.0, y=0.0)

ALL_MOD_DIFF = NodeDiff(
    tool_id=ToolID(812),
    old_node=NODE_ALL_MOD_OLD,
    new_node=NODE_ALL_MOD_NEW,
    field_diffs={"expr": ("x+1", "x+2")},
)
ALL_EDGE_ADDED = EdgeDiff(
    src_tool=ToolID(813),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(814),
    dst_anchor=AnchorName("Input"),
    change_type="added",
)
ALL_CHANGE_TYPES_DIFF = DiffResult(
    added_nodes=(NODE_ALL_ADDED,),
    removed_nodes=(NODE_ALL_REMOVED,),
    modified_nodes=(ALL_MOD_DIFF,),
    edge_diffs=(ALL_EDGE_ADDED,),
)

# Combined node sets for ALL_CHANGE_TYPES_DIFF
ALL_NODES_OLD = (
    NODE_ALL_REMOVED,
    NODE_ALL_MOD_OLD,
    NODE_ALL_CONN_SRC,
    NODE_ALL_CONN_DST,
    NODE_ALL_UNCHANGED,
)
ALL_NODES_NEW = (
    NODE_ALL_ADDED,
    NODE_ALL_MOD_NEW,
    NODE_ALL_CONN_SRC,
    NODE_ALL_CONN_DST,
    NODE_ALL_UNCHANGED,
)
ALL_CONNECTIONS = (
    AlteryxConnection(
        src_tool=ToolID(813),
        src_anchor=AnchorName("Output"),
        dst_tool=ToolID(814),
        dst_anchor=AnchorName("Input"),
    ),
)
