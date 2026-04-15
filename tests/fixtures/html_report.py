"""DiffResult fixtures for HTMLRenderer tests.

ToolIDs 701+ allocated for Phase 7. No collision with:
- Phase 2: 1-2
- Phase 3: 101-201
- Phase 4: 301-399
- Phase 5: 401-499
- Phase 6: 601-699
"""

from __future__ import annotations

from alteryx_git_companion.models.diff import DiffResult, EdgeDiff, NodeDiff
from alteryx_git_companion.models.types import AnchorName, ToolID
from alteryx_git_companion.models.workflow import AlteryxNode

# ---------------------------------------------------------------------------
# EMPTY_DIFF — no changes between the two workflows
# ---------------------------------------------------------------------------

EMPTY_DIFF: DiffResult = DiffResult()

# ---------------------------------------------------------------------------
# SINGLE_ADDED — one tool added in the new workflow
# ---------------------------------------------------------------------------

_NODE_701 = AlteryxNode(
    tool_id=ToolID(701),
    tool_type="AlteryxBasePluginsGui.Filter",
    x=0.0,
    y=0.0,
    config={"Expression": "Field1 > 0", "Mode": "Simple"},
)

SINGLE_ADDED: DiffResult = DiffResult(
    added_nodes=(_NODE_701,),
)

# ---------------------------------------------------------------------------
# SINGLE_REMOVED — one tool removed from the old workflow
# ---------------------------------------------------------------------------

_NODE_702 = AlteryxNode(
    tool_id=ToolID(702),
    tool_type="AlteryxBasePluginsGui.Select",
    x=0.0,
    y=0.0,
    config={"SelectFields": "Field1,Field2"},
)

SINGLE_REMOVED: DiffResult = DiffResult(
    removed_nodes=(_NODE_702,),
)

# ---------------------------------------------------------------------------
# SINGLE_MODIFIED — one tool has a changed config field
# ---------------------------------------------------------------------------

_NODE_703_OLD = AlteryxNode(
    tool_id=ToolID(703),
    tool_type="AlteryxBasePluginsGui.Filter",
    x=0.0,
    y=0.0,
    config={"Expression": "Amount > 0"},
)
_NODE_703_NEW = AlteryxNode(
    tool_id=ToolID(703),
    tool_type="AlteryxBasePluginsGui.Filter",
    x=0.0,
    y=0.0,
    config={"Expression": "Amount > 100"},
)
_NODE_DIFF_703 = NodeDiff(
    tool_id=ToolID(703),
    old_node=_NODE_703_OLD,
    new_node=_NODE_703_NEW,
    field_diffs={"Expression": ("Amount > 0", "Amount > 100")},
)

SINGLE_MODIFIED: DiffResult = DiffResult(
    modified_nodes=(_NODE_DIFF_703,),
)

# ---------------------------------------------------------------------------
# WITH_CONNECTION — one connection change (edge added between tools 704 -> 705)
# ---------------------------------------------------------------------------

_EDGE_DIFF = EdgeDiff(
    src_tool=ToolID(704),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(705),
    dst_anchor=AnchorName("Input"),
    change_type="added",
)

WITH_CONNECTION: DiffResult = DiffResult(
    edge_diffs=(_EDGE_DIFF,),
)
