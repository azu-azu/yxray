"""Fixture NormalizedNode instances for node matcher tests.

All ToolIDs start at 301 to avoid collision with Phase 1 (1-100),
Phase 2 (1-2), and Phase 3 (101-201) fixtures.

Config hashes are short strings for readability — the matcher treats
them as opaque strings; real SHA-256 is only required in Phase 3 normalizer tests.
"""

from __future__ import annotations

from alteryx_git_companion.models import NormalizedNode
from alteryx_git_companion.models.types import ConfigHash, ToolID
from alteryx_git_companion.models.workflow import AlteryxNode


def make_node(
    tid: int,
    tool_type: str,
    x: float,
    y: float,
    config_hash: str,
) -> NormalizedNode:
    """Convenience builder for test NormalizedNodes."""
    src = AlteryxNode(tool_id=ToolID(tid), tool_type=tool_type, x=x, y=y, config={})
    return NormalizedNode(
        source=src, config_hash=ConfigHash(config_hash), position=(x, y)
    )


# ---------------------------------------------------------------------------
# EXACT_MATCH — 3 nodes, same ToolIDs in old and new, same config/position
# ---------------------------------------------------------------------------
EXACT_MATCH_OLD: list[NormalizedNode] = [
    make_node(301, "Filter", 100.0, 100.0, "h1"),
    make_node(302, "Join", 200.0, 100.0, "h2"),
    make_node(303, "Select", 300.0, 100.0, "h3"),
]

EXACT_MATCH_NEW: list[NormalizedNode] = [
    make_node(301, "Filter", 100.0, 100.0, "h1"),
    make_node(302, "Join", 200.0, 100.0, "h2"),
    make_node(303, "Select", 300.0, 100.0, "h3"),
]


# ---------------------------------------------------------------------------
# FULL_REGEN — 2 Filter nodes; old IDs 310/311, new IDs 390/391
# Same config hash and nearby positions — should match via Hungarian Pass 2
# ---------------------------------------------------------------------------
FULL_REGEN_OLD: list[NormalizedNode] = [
    make_node(310, "Filter", 100.0, 100.0, "regen_hash"),
    make_node(311, "Filter", 200.0, 100.0, "regen_hash"),
]

FULL_REGEN_NEW: list[NormalizedNode] = [
    make_node(390, "Filter", 105.0, 100.0, "regen_hash"),
    make_node(391, "Filter", 205.0, 100.0, "regen_hash"),
]


# ---------------------------------------------------------------------------
# PARTIAL_REGEN — 3 nodes; first two keep IDs, third gets a new ID
# IDs 320, 321 match via Pass 1; ID 322 vs 399 matches via Pass 2 Hungarian
# ---------------------------------------------------------------------------
PARTIAL_REGEN_OLD: list[NormalizedNode] = [
    make_node(320, "Select", 100.0, 100.0, "ph1"),
    make_node(321, "Select", 200.0, 100.0, "ph2"),
    make_node(322, "Select", 300.0, 100.0, "ph3"),
]

PARTIAL_REGEN_NEW: list[NormalizedNode] = [
    make_node(320, "Select", 100.0, 100.0, "ph1"),
    make_node(321, "Select", 200.0, 100.0, "ph2"),
    make_node(399, "Select", 305.0, 100.0, "ph3"),
]


# ---------------------------------------------------------------------------
# GENUINE_ADD — old has 1 Filter; new has 2 (1 same ID + 1 genuinely new)
# ---------------------------------------------------------------------------
GENUINE_ADD_OLD: list[NormalizedNode] = [
    make_node(330, "Filter", 100.0, 100.0, "ga_old"),
]

GENUINE_ADD_NEW: list[NormalizedNode] = [
    make_node(330, "Filter", 100.0, 100.0, "ga_old"),
    make_node(331, "Filter", 200.0, 100.0, "ga_new"),
]


# ---------------------------------------------------------------------------
# GENUINE_REMOVE — old has 2 Filter nodes; new has 1 (1 same ID, 1 removed)
# ---------------------------------------------------------------------------
GENUINE_REMOVE_OLD: list[NormalizedNode] = [
    make_node(340, "Filter", 100.0, 100.0, "gr_h1"),
    make_node(341, "Filter", 200.0, 100.0, "gr_h2"),
]

GENUINE_REMOVE_NEW: list[NormalizedNode] = [
    make_node(340, "Filter", 100.0, 100.0, "gr_h1"),
]


# ---------------------------------------------------------------------------
# THRESHOLD_REJECT — cost > 0.8: different hash (0.5) + distant positions (~0.5)
# One Join in old at (0, 0); one Join in new at (10000, 10000) with diff hash
# ---------------------------------------------------------------------------
THRESHOLD_OLD: list[NormalizedNode] = [
    make_node(350, "Join", 0.0, 0.0, "threshold_old"),
]

THRESHOLD_NEW: list[NormalizedNode] = [
    make_node(360, "Join", 10000.0, 10000.0, "threshold_new"),
]


# ---------------------------------------------------------------------------
# CROSS_TYPE — one Filter in old, one Join in new
# Same position and hash prefix — cross-type match must NEVER happen
# ---------------------------------------------------------------------------
CROSS_TYPE_OLD: list[NormalizedNode] = [
    make_node(370, "Filter", 100.0, 100.0, "ct_hash"),
]

CROSS_TYPE_NEW: list[NormalizedNode] = [
    make_node(380, "Join", 100.0, 100.0, "ct_hash"),
]
