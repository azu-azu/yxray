"""Contract tests for the two-pass node matcher (DIFF-04).

Tests are ordered: exact match -> full regen -> partial regen ->
genuine add -> genuine remove -> threshold rejection -> empty inputs ->
cross-type isolation -> count invariant.
"""

from __future__ import annotations

from alteryx_git_companion.matcher import MatchResult, match
from alteryx_git_companion.models import NormalizedNode
from tests.fixtures.matching import (
    CROSS_TYPE_NEW,
    CROSS_TYPE_OLD,
    EXACT_MATCH_NEW,
    EXACT_MATCH_OLD,
    FULL_REGEN_NEW,
    FULL_REGEN_OLD,
    GENUINE_ADD_NEW,
    GENUINE_ADD_OLD,
    GENUINE_REMOVE_NEW,
    GENUINE_REMOVE_OLD,
    PARTIAL_REGEN_NEW,
    PARTIAL_REGEN_OLD,
    THRESHOLD_NEW,
    THRESHOLD_OLD,
)


def _check_invariant(
    result: MatchResult,
    old_nodes: list[NormalizedNode],
    new_nodes: list[NormalizedNode],
) -> None:
    """Every node must appear exactly once across matched/removed/added."""
    total_old = len(result.matched) + len(result.removed)
    total_new = len(result.matched) + len(result.added)
    assert total_old == len(old_nodes), (
        f"Old count mismatch: {total_old} accounted, {len(old_nodes)} total"
    )
    assert total_new == len(new_nodes), (
        f"New count mismatch: {total_new} accounted, {len(new_nodes)} total"
    )


def test_exact_id_match() -> None:
    """3 nodes with identical ToolIDs must all match via Pass 1 exactly."""
    result = match(EXACT_MATCH_OLD, EXACT_MATCH_NEW)
    assert len(result.matched) == 3
    assert len(result.removed) == 0
    assert len(result.added) == 0
    _check_invariant(result, EXACT_MATCH_OLD, EXACT_MATCH_NEW)


def test_full_toolid_regeneration() -> None:
    """2 Filter nodes with fully regenerated ToolIDs must match via Pass 2 Hungarian."""
    # FULL_REGEN: old IDs 310/311, new IDs 390/391
    # same type, same hash, nearby positions
    result = match(FULL_REGEN_OLD, FULL_REGEN_NEW)
    assert len(result.matched) == 2
    assert len(result.removed) == 0
    assert len(result.added) == 0
    # Matched pairs must link correct old/new nodes (same config_hash on each side)
    for old_node, new_node in result.matched:
        assert old_node.config_hash == new_node.config_hash
    _check_invariant(result, FULL_REGEN_OLD, FULL_REGEN_NEW)


def test_partial_toolid_regeneration() -> None:
    """First 2 nodes match via Pass 1 exact; third matches via Pass 2 Hungarian."""
    # PARTIAL_REGEN: IDs 320, 321 stable; ID 322 regenerated to 399
    result = match(PARTIAL_REGEN_OLD, PARTIAL_REGEN_NEW)
    assert len(result.matched) == 3  # two exact + one via Hungarian
    assert len(result.removed) == 0
    assert len(result.added) == 0
    _check_invariant(result, PARTIAL_REGEN_OLD, PARTIAL_REGEN_NEW)


def test_genuine_addition() -> None:
    """New node with no matching old counterpart must appear in added."""
    # GENUINE_ADD: old has ID 330; new adds ID 331 (no match in old)
    result = match(GENUINE_ADD_OLD, GENUINE_ADD_NEW)
    assert len(result.matched) == 1
    assert len(result.removed) == 0
    assert len(result.added) == 1
    assert result.added[0].source.tool_id == 331
    _check_invariant(result, GENUINE_ADD_OLD, GENUINE_ADD_NEW)


def test_genuine_removal() -> None:
    """Old node with no new counterpart must appear in removed."""
    # GENUINE_REMOVE: old has IDs 340, 341; new only has ID 340
    result = match(GENUINE_REMOVE_OLD, GENUINE_REMOVE_NEW)
    assert len(result.matched) == 1
    assert len(result.removed) == 1
    assert len(result.added) == 0
    assert result.removed[0].source.tool_id == 341
    _check_invariant(result, GENUINE_REMOVE_OLD, GENUINE_REMOVE_NEW)


def test_threshold_rejection() -> None:
    """Node pair with cost > 0.8 must be rejected — appears as removed + added."""
    # THRESHOLD: old ID 350 Join at (0,0) hash "threshold_old"
    #            new ID 360 Join at (10000,10000) hash "threshold_new"
    # Pass 1: no ToolID match. Pass 2: Hungarian assigns pair; cost > 0.8 rejects.
    result = match(THRESHOLD_OLD, THRESHOLD_NEW)
    assert len(result.matched) == 0
    assert len(result.removed) == 1
    assert len(result.added) == 1
    _check_invariant(result, THRESHOLD_OLD, THRESHOLD_NEW)


def test_empty_inputs() -> None:
    """Empty input lists produce empty MatchResult in all combinations."""
    # Sub-case A: both empty
    result_a = match([], [])
    assert result_a.matched == ()
    assert result_a.removed == ()
    assert result_a.added == ()
    _check_invariant(result_a, [], [])

    # Sub-case B: empty new — all old become removed
    result_b = match(EXACT_MATCH_OLD, [])
    assert result_b.matched == ()
    assert len(result_b.removed) == 3
    assert result_b.added == ()
    _check_invariant(result_b, EXACT_MATCH_OLD, [])

    # Sub-case C: empty old — all new become added
    result_c = match([], EXACT_MATCH_NEW)
    assert result_c.matched == ()
    assert result_c.removed == ()
    assert len(result_c.added) == 3
    _check_invariant(result_c, [], EXACT_MATCH_NEW)


def test_cross_type_isolation() -> None:
    """Filter in old and Join in new must never be paired (type isolation)."""
    # CROSS_TYPE: same position, same hash — but different tool_type
    result = match(CROSS_TYPE_OLD, CROSS_TYPE_NEW)
    assert len(result.matched) == 0
    assert len(result.removed) == 1
    assert len(result.added) == 1
    assert result.removed[0].source.tool_type == "Filter"
    assert result.added[0].source.tool_type == "Join"
    _check_invariant(result, CROSS_TYPE_OLD, CROSS_TYPE_NEW)


def test_match_result_count_invariant() -> None:
    """Count invariant holds across all 7 fixture pairs."""
    fixture_pairs = [
        (EXACT_MATCH_OLD, EXACT_MATCH_NEW),
        (FULL_REGEN_OLD, FULL_REGEN_NEW),
        (PARTIAL_REGEN_OLD, PARTIAL_REGEN_NEW),
        (GENUINE_ADD_OLD, GENUINE_ADD_NEW),
        (GENUINE_REMOVE_OLD, GENUINE_REMOVE_NEW),
        (THRESHOLD_OLD, THRESHOLD_NEW),
        (CROSS_TYPE_OLD, CROSS_TYPE_NEW),
    ]
    for old_nodes, new_nodes in fixture_pairs:
        result = match(old_nodes, new_nodes)
        _check_invariant(result, old_nodes, new_nodes)
