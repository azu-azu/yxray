"""Contract tests for the differ stage (DIFF-01, DIFF-02, DIFF-03).

Tests are ordered: added node -> removed node -> modified flat field ->
filter expression -> nested field -> absent key after -> absent key before ->
list field atomic -> rewired connection -> added connection ->
removed connection -> identical workflows.
"""

from __future__ import annotations

from alteryx_git_companion.differ import diff
from alteryx_git_companion.models import AnchorName, ToolID
from tests.fixtures.diffing import (
    SCENARIO_ABSENT_KEY_AFTER,
    SCENARIO_ABSENT_KEY_BEFORE,
    SCENARIO_ADDED_NODE,
    SCENARIO_EDGE_ADDED,
    SCENARIO_EDGE_REMOVED,
    SCENARIO_EDGE_REWIRED,
    SCENARIO_IDENTICAL_WORKFLOWS,
    SCENARIO_LIST_FIELD_ATOMIC,
    SCENARIO_MODIFIED_FLAT_FIELD,
    SCENARIO_MODIFIED_NESTED_FIELD,
    SCENARIO_REMOVED_NODE,
)


def test_added_node() -> None:
    """A tool added to the new workflow appears in DiffResult.added_nodes (DIFF-01)."""
    match_result, old_conns, new_conns = SCENARIO_ADDED_NODE
    result = diff(match_result, old_conns, new_conns)

    assert len(result.added_nodes) == 1
    assert result.added_nodes[0].tool_id == ToolID(402)
    assert len(result.removed_nodes) == 0
    assert len(result.modified_nodes) == 0


def test_removed_node() -> None:
    """A tool removed from old workflow appears in DiffResult.removed_nodes."""
    match_result, old_conns, new_conns = SCENARIO_REMOVED_NODE
    result = diff(match_result, old_conns, new_conns)

    assert len(result.removed_nodes) == 1
    assert result.removed_nodes[0].tool_id == ToolID(404)
    assert len(result.added_nodes) == 0
    assert len(result.modified_nodes) == 0


def test_modified_node_changed_fields_only() -> None:
    """Only changed fields appear in field_diffs; unchanged fields are excluded."""
    match_result, old_conns, new_conns = SCENARIO_MODIFIED_FLAT_FIELD
    result = diff(match_result, old_conns, new_conns)

    assert len(result.modified_nodes) == 1
    nd = result.modified_nodes[0]
    assert nd.tool_id == ToolID(405)
    assert "Expression" in nd.field_diffs
    assert "NumOutputs" not in nd.field_diffs


def test_filter_expression_change() -> None:
    """A changed filter expression reports the correct before/after values (DIFF-02)."""
    match_result, old_conns, new_conns = SCENARIO_MODIFIED_FLAT_FIELD
    result = diff(match_result, old_conns, new_conns)

    nd = result.modified_nodes[0]
    assert nd.field_diffs["Expression"] == ("[Amount] > 1000", "[Amount] > 5000")


def test_nested_field_change() -> None:
    """A nested field change reports the full dotted path in field_diffs (DIFF-02)."""
    match_result, old_conns, new_conns = SCENARIO_MODIFIED_NESTED_FIELD
    result = diff(match_result, old_conns, new_conns)

    assert len(result.modified_nodes) == 1
    nd = result.modified_nodes[0]
    assert "OutputFile.path" in nd.field_diffs
    assert nd.field_diffs["OutputFile.path"] == ("out.csv", "results.csv")


def test_absent_key_after() -> None:
    """Key present in old but absent in new -> field_diffs[key] = (old_value, None)."""
    match_result, old_conns, new_conns = SCENARIO_ABSENT_KEY_AFTER
    result = diff(match_result, old_conns, new_conns)

    nd = result.modified_nodes[0]
    assert "SortOrder" in nd.field_diffs
    assert nd.field_diffs["SortOrder"] == ("Ascending", None)


def test_absent_key_before() -> None:
    """Key absent in old but present in new -> field_diffs[key] = (None, new_value)."""
    match_result, old_conns, new_conns = SCENARIO_ABSENT_KEY_BEFORE
    result = diff(match_result, old_conns, new_conns)

    nd = result.modified_nodes[0]
    assert "SortOrder" in nd.field_diffs
    assert nd.field_diffs["SortOrder"] == (None, "Ascending")


def test_list_field_atomic() -> None:
    """List field changed: whole list reported as before/after (atomic, DIFF-02)."""
    match_result, old_conns, new_conns = SCENARIO_LIST_FIELD_ATOMIC
    result = diff(match_result, old_conns, new_conns)

    nd = result.modified_nodes[0]
    assert "Fields" in nd.field_diffs

    before, after = nd.field_diffs["Fields"]
    assert before == ["ID", "Name", "Amount"]
    assert after == ["ID", "Name", "Amount", "Region"]

    # No element-level paths — lists are treated atomically
    for key in nd.field_diffs:
        assert not key.startswith("Fields."), (
            f"Found element-level path {key!r} — expected atomic list treatment"
        )


def test_rewired_connection() -> None:
    """Rewired connection = one removed EdgeDiff + one added EdgeDiff (DIFF-03)."""
    match_result, old_conns, new_conns = SCENARIO_EDGE_REWIRED
    result = diff(match_result, old_conns, new_conns)

    assert len(result.edge_diffs) == 2

    removed_diffs = [e for e in result.edge_diffs if e.change_type == "removed"]
    added_diffs = [e for e in result.edge_diffs if e.change_type == "added"]

    assert len(removed_diffs) == 1
    assert len(added_diffs) == 1

    assert removed_diffs[0].dst_anchor == AnchorName("Input")
    assert added_diffs[0].dst_anchor == AnchorName("Right")


def test_added_connection() -> None:
    """A new connection appears in edge_diffs with change_type='added' (DIFF-03)."""
    match_result, old_conns, new_conns = SCENARIO_EDGE_ADDED
    result = diff(match_result, old_conns, new_conns)

    added_diffs = [e for e in result.edge_diffs if e.change_type == "added"]
    removed_diffs = [e for e in result.edge_diffs if e.change_type == "removed"]

    assert len(added_diffs) == 1
    assert len(removed_diffs) == 0

    ed = added_diffs[0]
    assert ed.src_tool == ToolID(411)
    assert ed.src_anchor == AnchorName("Output")
    assert ed.dst_tool == ToolID(412)
    assert ed.dst_anchor == AnchorName("Input")


def test_removed_connection() -> None:
    """A removed connection appears in edge_diffs with change_type='removed'."""
    match_result, old_conns, new_conns = SCENARIO_EDGE_REMOVED
    result = diff(match_result, old_conns, new_conns)

    removed_diffs = [e for e in result.edge_diffs if e.change_type == "removed"]
    added_diffs = [e for e in result.edge_diffs if e.change_type == "added"]

    assert len(removed_diffs) == 1
    assert len(added_diffs) == 0

    ed = removed_diffs[0]
    assert ed.src_tool == ToolID(414)
    assert ed.dst_tool == ToolID(415)


def test_identical_workflows_empty_result() -> None:
    """Identical workflows produce DiffResult.is_empty == True (Success Criterion 5)."""
    match_result, old_conns, new_conns = SCENARIO_IDENTICAL_WORKFLOWS
    result = diff(match_result, old_conns, new_conns)

    assert result.is_empty is True
    assert len(result.added_nodes) == 0
    assert len(result.removed_nodes) == 0
    assert len(result.modified_nodes) == 0
    assert len(result.edge_diffs) == 0
