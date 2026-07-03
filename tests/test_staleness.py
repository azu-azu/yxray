"""Tests for staleness.detect_stale_select_fields().

Phase 1 scope:
  - Select ツール間の Rename 追跡のみ
  - 1-hop のみ（A→B→C の連鎖は A→B どまり）
  - non-goals: DynamicRename, Join/Union prefix, same-Select swap
"""

from __future__ import annotations

import pytest

from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.staleness import RenameRecord, StaleFieldWarning, detect_stale_select_fields

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _select_node(tool_id: int, rows: list[dict]) -> AlteryxNode:
    """AlteryxSelect node whose config holds the given SelectField rows."""
    return AlteryxNode(
        tool_id=ToolID(tool_id),
        tool_type="AlteryxSelect",
        x=0.0,
        y=0.0,
        config={"SelectFields": {"SelectField": rows}},
    )


def _non_select_node(tool_id: int, tool_type: str = "Filter") -> AlteryxNode:
    return AlteryxNode(tool_id=ToolID(tool_id), tool_type=tool_type, x=0.0, y=0.0)


def _rename_row(field: str, rename: str) -> dict:
    return {"@field": field, "@rename": rename, "@selected": "True"}


def _drop_row(field: str) -> dict:
    return {"@field": field, "@selected": "False"}


def _keep_row(field: str) -> dict:
    return {"@field": field, "@selected": "True"}


def _conn(src: int, dst: int) -> AlteryxConnection:
    return AlteryxConnection(
        src_tool=ToolID(src),
        src_anchor=AnchorName("Output"),
        dst_tool=ToolID(dst),
        dst_anchor=AnchorName("Input"),
    )


def _doc(
    *nodes: AlteryxNode, connections: tuple[AlteryxConnection, ...] = ()
) -> WorkflowDoc:
    return WorkflowDoc(filepath="test.yxmd", nodes=nodes, connections=connections)


# ---------------------------------------------------------------------------
# No-warning cases
# ---------------------------------------------------------------------------


def test_no_warnings_empty_workflow() -> None:
    doc = WorkflowDoc(filepath="t.yxmd")
    assert detect_stale_select_fields(doc) == []


def test_no_warnings_no_select_tools() -> None:
    doc = _doc(
        _non_select_node(1, "InputData"),
        _non_select_node(2, "Filter"),
        connections=(_conn(1, 2),),
    )
    assert detect_stale_select_fields(doc) == []


def test_no_warnings_valid_reference() -> None:
    # Select(1): A→B; Select(2): Drop B (current name) → valid, no warning
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_drop_row("B")]),
        connections=(_conn(1, 2),),
    )
    assert detect_stale_select_fields(doc) == []


def test_no_warnings_disjoint_selects() -> None:
    # Two Select tools with no connection: history should not cross
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_drop_row("A")]),
        # no connections
    )
    assert detect_stale_select_fields(doc) == []


def test_no_warnings_keep_valid_field() -> None:
    # Select(1): A→B; Select(2): Keep A — but A is stale... wait, this SHOULD warn.
    # Contrast: Select(2) keeps B (the new name) → no warning
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_keep_row("B")]),
        connections=(_conn(1, 2),),
    )
    assert detect_stale_select_fields(doc) == []


# ---------------------------------------------------------------------------
# Basic stale-warning cases
# ---------------------------------------------------------------------------


def test_warns_stale_drop() -> None:
    # Issue example: Select(166) abc→def, Select(108) drops abc → stale
    doc = _doc(
        _select_node(166, [_rename_row("abc", "def")]),
        _select_node(108, [_drop_row("abc")]),
        connections=(_conn(166, 108),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.tool_id == 108
    assert w.field_name == "abc"
    assert w.renamed_to == "def"
    assert w.renamed_at == 166


def test_warns_stale_keep() -> None:
    # Select(1): A→B; Select(2): keeps A (selected=True) → stale warning
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_keep_row("A")]),
        connections=(_conn(1, 2),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    assert warnings[0].field_name == "A"


def test_warns_stale_rename() -> None:
    # Select(1): A→B; Select(2): A→C (rename stale field) → stale warning
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_rename_row("A", "C")]),
        connections=(_conn(1, 2),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.tool_id == 2
    assert w.field_name == "A"
    assert w.renamed_to == "B"
    assert w.renamed_at == 1


def test_warning_message_contains_key_info() -> None:
    doc = _doc(
        _select_node(1, [_rename_row("col_old", "col_new")]),
        _select_node(2, [_drop_row("col_old")]),
        connections=(_conn(1, 2),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    msg = warnings[0].message
    assert "col_old" in msg
    assert "col_new" in msg
    assert "1" in msg  # renamed_at tool id


def test_multiple_stale_fields_one_select() -> None:
    # Select(1): A→B, X→Y; Select(2): drops both A and X → 2 warnings
    doc = _doc(
        _select_node(1, [_rename_row("A", "B"), _rename_row("X", "Y")]),
        _select_node(2, [_drop_row("A"), _drop_row("X")]),
        connections=(_conn(1, 2),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 2
    stale_names = {w.field_name for w in warnings}
    assert stale_names == {"A", "X"}


# ---------------------------------------------------------------------------
# History propagation
# ---------------------------------------------------------------------------


def test_history_propagates_through_non_select() -> None:
    # Select(1): A→B, Filter(2): pass-through, Select(3): drops A → warns at 3
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _non_select_node(2, "Filter"),
        _select_node(3, [_drop_row("A")]),
        connections=(_conn(1, 2), _conn(2, 3)),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    assert warnings[0].tool_id == 3


def test_history_propagates_two_hops() -> None:
    # Select(1): A→B, Filter(2), Filter(3), Select(4): drops A → warns
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _non_select_node(2),
        _non_select_node(3),
        _select_node(4, [_drop_row("A")]),
        connections=(_conn(1, 2), _conn(2, 3), _conn(3, 4)),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1
    assert warnings[0].tool_id == 4


def test_rename_chain_warns_at_first_downstream() -> None:
    # Select(1): A→B; Select(2): B→C; Select(3): drops A
    # A is stale (renamed to B at tool 1). B is valid at tool 2 and renamed to C.
    # Select(3): drops A → warns (A→B, from tool 1)
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_rename_row("B", "C")]),
        _select_node(3, [_drop_row("A")]),
        connections=(_conn(1, 2), _conn(2, 3)),
    )
    warnings = detect_stale_select_fields(doc)
    stale_at_3 = [w for w in warnings if w.tool_id == 3]
    assert len(stale_at_3) == 1
    assert stale_at_3[0].field_name == "A"
    assert stale_at_3[0].renamed_to == "B"  # 1-hop only


def test_stale_rename_does_not_propagate_further() -> None:
    # Select(1): A→B; Select(2): A→C (stale, warns here); Select(3): drops A
    # After Select(2) processes A as stale, A must NOT appear in history
    # going into Select(3) — prevents cascading duplicate warnings.
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_rename_row("A", "C")]),
        _select_node(3, [_drop_row("A")]),
        connections=(_conn(1, 2), _conn(2, 3)),
    )
    warnings = detect_stale_select_fields(doc)
    tool_ids = [w.tool_id for w in warnings]
    assert 2 in tool_ids          # stale at Select(2)
    assert 3 not in tool_ids      # NOT cascaded to Select(3)


# ---------------------------------------------------------------------------
# Branching / merging
# ---------------------------------------------------------------------------


def test_no_cross_branch_contamination() -> None:
    # Branch A: Select(1): A→B → Select(3)
    # Branch B: Select(2): X→Y → Select(3) (Join/Union at 3)
    # Select(3) drops A and X → both stale
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _select_node(2, [_rename_row("X", "Y")]),
        _select_node(3, [_drop_row("A"), _drop_row("X")]),
        connections=(_conn(1, 3), _conn(2, 3)),
    )
    warnings = detect_stale_select_fields(doc)
    stale_names = {w.field_name for w in warnings}
    assert "A" in stale_names
    assert "X" in stale_names


def test_independent_branch_no_cross_warning() -> None:
    # Branch A: Select(1): A→B → Output(3)
    # Branch B: Select(2): independent → Output(4)
    # No shared downstream: no warnings
    doc = _doc(
        _select_node(1, [_rename_row("A", "B")]),
        _non_select_node(2, "InputData"),
        _select_node(3, [_drop_row("A")]),  # downstream of branch A only? no...
        # Actually: 1→3, 2→4 (no 4 in doc). Let's just test 1→3 with no rename
        # upstream of 3 via 2
        connections=(_conn(1, 3),),
    )
    warnings = detect_stale_select_fields(doc)
    assert len(warnings) == 1  # only A→B stale at 3
    assert warnings[0].tool_id == 3


# ---------------------------------------------------------------------------
# Dataclass structure
# ---------------------------------------------------------------------------


def test_rename_record_is_frozen() -> None:
    rec = RenameRecord(old_name="A", new_name="B", renamed_at=1)
    with pytest.raises((AttributeError, TypeError)):
        rec.old_name = "X"  # type: ignore[misc]


def test_stale_field_warning_is_frozen() -> None:
    w = StaleFieldWarning(
        tool_id=1,
        field_name="A",
        renamed_to="B",
        renamed_at=1,
        message="test",
    )
    with pytest.raises((AttributeError, TypeError)):
        w.field_name = "X"  # type: ignore[misc]
