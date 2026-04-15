"""Fixture MatchResult and connection tuple pairs for the differ test suite.

All ToolIDs start at 401 to avoid collision with prior phase fixtures:
- Phase 2: 1-2
- Phase 3: 101-201
- Phase 4: 301-399

Each scenario is exported as a 3-tuple:
    (MatchResult, old_connections_tuple, new_connections_tuple)

Config hashes are computed via SHA-256 of json.dumps(config, sort_keys=True),
matching the Phase 3 normalizer convention.

Plan 05-03 imports these constants and writes tests against well-understood inputs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from alteryx_git_companion.matcher.matcher import MatchResult
from alteryx_git_companion.models import (
    AlteryxConnection,
    AlteryxNode,
    ConfigHash,
    NormalizedNode,
    ToolID,
)
from alteryx_git_companion.models.types import AnchorName

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_node(tool_id: int, tool_type: str, config: dict[str, Any]) -> AlteryxNode:
    """Reduce boilerplate: build an AlteryxNode with default position (0, 0)."""
    return AlteryxNode(
        tool_id=ToolID(tool_id),
        tool_type=tool_type,
        x=0.0,
        y=0.0,
        config=config,
    )


def _hash(config: dict[str, Any]) -> ConfigHash:
    """Compute SHA-256 of json.dumps(config, sort_keys=True).

    Matches the Phase 3 normalizer convention exactly.
    """
    raw = json.dumps(config, sort_keys=True).encode()
    return ConfigHash(hashlib.sha256(raw).hexdigest())


def _norm(node: AlteryxNode) -> NormalizedNode:
    """Wrap an AlteryxNode as a NormalizedNode with position=(0.0, 0.0)."""
    return NormalizedNode(
        source=node,
        config_hash=_hash(node.config),
        position=(0.0, 0.0),
    )


# ---------------------------------------------------------------------------
# SCENARIO_ADDED_NODE — new workflow has one extra node
# ---------------------------------------------------------------------------
# old workflow: one Filter node (401)
# new workflow: same Filter (401) + new Select (402)
# MatchResult: matched=((norm_401, norm_401),), removed=(), added=(norm_402,)

_filter_401 = _make_node(401, "Filter", {"Expression": "[Amount] > 1000"})
_select_402 = _make_node(402, "Select", {"Fields": ["ID"]})

_norm_401 = _norm(_filter_401)
_norm_402 = _norm(_select_402)

SCENARIO_ADDED_NODE: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_401, _norm_401),),
        removed=(),
        added=(_norm_402,),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_REMOVED_NODE — old workflow has one extra node
# ---------------------------------------------------------------------------
# old workflow: Filter (403) + Select (404)
# new workflow: Filter (403) only
# MatchResult: matched=((norm_403, norm_403),), removed=(norm_404,), added=()

_filter_403 = _make_node(403, "Filter", {"Expression": "[Amount] > 1000"})
_select_404 = _make_node(404, "Select", {"Fields": ["ID"]})

_norm_403 = _norm(_filter_403)
_norm_404 = _norm(_select_404)

SCENARIO_REMOVED_NODE: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_403, _norm_403),),
        removed=(_norm_404,),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_MODIFIED_FLAT_FIELD — flat config field changed
# ---------------------------------------------------------------------------
# old node: Filter 405, Expression "[Amount] > 1000"
# new node: Filter 405, Expression "[Amount] > 5000"
# config_hashes MUST differ

_filter_405_old = _make_node(
    405, "Filter", {"Expression": "[Amount] > 1000", "NumOutputs": 2}
)
_filter_405_new = _make_node(
    405, "Filter", {"Expression": "[Amount] > 5000", "NumOutputs": 2}
)

_norm_405_old = _norm(_filter_405_old)
_norm_405_new = _norm(_filter_405_new)

# Sanity: hashes must differ for this scenario to be meaningful
assert _norm_405_old.config_hash != _norm_405_new.config_hash, (
    "SCENARIO_MODIFIED_FLAT_FIELD: config hashes must differ"
)

SCENARIO_MODIFIED_FLAT_FIELD: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_405_old, _norm_405_new),),
        removed=(),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_MODIFIED_NESTED_FIELD — nested config field changed
# ---------------------------------------------------------------------------
# old node: Output 406, path "out.csv"
# new node: Output 406, path "results.csv"

_output_406_old = _make_node(
    406, "Output", {"OutputFile": {"path": "out.csv", "overwrite": True}}
)
_output_406_new = _make_node(
    406, "Output", {"OutputFile": {"path": "results.csv", "overwrite": True}}
)

_norm_406_old = _norm(_output_406_old)
_norm_406_new = _norm(_output_406_new)

assert _norm_406_old.config_hash != _norm_406_new.config_hash, (
    "SCENARIO_MODIFIED_NESTED_FIELD: config hashes must differ"
)

SCENARIO_MODIFIED_NESTED_FIELD: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_406_old, _norm_406_new),),
        removed=(),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_ABSENT_KEY_AFTER — key present in old is absent in new
# ---------------------------------------------------------------------------
# old node: Filter 407, has SortOrder key
# new node: Filter 407, SortOrder absent

_filter_407_old = _make_node(
    407, "Filter", {"Expression": "[Amount] > 1000", "SortOrder": "Ascending"}
)
_filter_407_new = _make_node(407, "Filter", {"Expression": "[Amount] > 1000"})

_norm_407_old = _norm(_filter_407_old)
_norm_407_new = _norm(_filter_407_new)

assert _norm_407_old.config_hash != _norm_407_new.config_hash, (
    "SCENARIO_ABSENT_KEY_AFTER: config hashes must differ"
)

SCENARIO_ABSENT_KEY_AFTER: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_407_old, _norm_407_new),),
        removed=(),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_ABSENT_KEY_BEFORE — key absent in old is present in new
# ---------------------------------------------------------------------------
# old node: Filter 408, no SortOrder key
# new node: Filter 408, SortOrder present

_filter_408_old = _make_node(408, "Filter", {"Expression": "[Amount] > 1000"})
_filter_408_new = _make_node(
    408, "Filter", {"Expression": "[Amount] > 1000", "SortOrder": "Ascending"}
)

_norm_408_old = _norm(_filter_408_old)
_norm_408_new = _norm(_filter_408_new)

assert _norm_408_old.config_hash != _norm_408_new.config_hash, (
    "SCENARIO_ABSENT_KEY_BEFORE: config hashes must differ"
)

SCENARIO_ABSENT_KEY_BEFORE: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_408_old, _norm_408_new),),
        removed=(),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_LIST_FIELD_ATOMIC — list-valued field changed (one element added)
# ---------------------------------------------------------------------------
# old node: Select 409, Fields: ["ID", "Name", "Amount"]
# new node: Select 409, Fields: ["ID", "Name", "Amount", "Region"]

_select_409_old = _make_node(409, "Select", {"Fields": ["ID", "Name", "Amount"]})
_select_409_new = _make_node(
    409, "Select", {"Fields": ["ID", "Name", "Amount", "Region"]}
)

_norm_409_old = _norm(_select_409_old)
_norm_409_new = _norm(_select_409_new)

assert _norm_409_old.config_hash != _norm_409_new.config_hash, (
    "SCENARIO_LIST_FIELD_ATOMIC: config hashes must differ"
)

SCENARIO_LIST_FIELD_ATOMIC: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_409_old, _norm_409_new),),
        removed=(),
        added=(),
    ),
    (),
    (),
)


# ---------------------------------------------------------------------------
# SCENARIO_EDGE_ADDED — new connection appears in new_connections only
# ---------------------------------------------------------------------------
# ToolIDs: 410 (source), 411 (middle), 412 (new destination)
# old_connections: 410 -> 411
# new_connections: 410 -> 411 + 411 -> 412
# All nodes matched with identical configs (no node modifications)

_node_410 = _make_node(410, "Filter", {"Expression": "[Amount] > 1000"})
_node_411 = _make_node(411, "Select", {"Fields": ["ID"]})
_node_412 = _make_node(412, "Output", {"OutputFile": {"path": "out.csv"}})

_norm_410 = _norm(_node_410)
_norm_411 = _norm(_node_411)
_norm_412 = _norm(_node_412)

_conn_410_411 = AlteryxConnection(
    src_tool=ToolID(410),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(411),
    dst_anchor=AnchorName("Input"),
)
_conn_411_412 = AlteryxConnection(
    src_tool=ToolID(411),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(412),
    dst_anchor=AnchorName("Input"),
)

# Export individual nodes for tests that need to assert on specific ToolIDs
EDGE_ADDED_NODE_410 = _norm_410
EDGE_ADDED_NODE_411 = _norm_411
EDGE_ADDED_NODE_412 = _norm_412

SCENARIO_EDGE_ADDED: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=(
            (_norm_410, _norm_410),
            (_norm_411, _norm_411),
            (_norm_412, _norm_412),
        ),
        removed=(),
        added=(),
    ),
    (_conn_410_411,),
    (_conn_410_411, _conn_411_412),
)


# ---------------------------------------------------------------------------
# SCENARIO_EDGE_REMOVED — connection in old_connections absent in new_connections
# ---------------------------------------------------------------------------
# ToolIDs: A=413, B=414, C=415
# old_connections: A->B and B->C
# new_connections: A->B only (B->C removed)

_node_413 = _make_node(413, "Filter", {"Expression": "[Amount] > 1000"})
_node_414 = _make_node(414, "Select", {"Fields": ["ID"]})
_node_415 = _make_node(415, "Output", {"OutputFile": {"path": "out.csv"}})

_norm_413 = _norm(_node_413)
_norm_414 = _norm(_node_414)
_norm_415 = _norm(_node_415)

_conn_413_414 = AlteryxConnection(
    src_tool=ToolID(413),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(414),
    dst_anchor=AnchorName("Input"),
)
_conn_414_415 = AlteryxConnection(
    src_tool=ToolID(414),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(415),
    dst_anchor=AnchorName("Input"),
)

# Export individual nodes for tests that need to assert on specific ToolIDs
EDGE_REMOVED_NODE_413 = _norm_413
EDGE_REMOVED_NODE_414 = _norm_414
EDGE_REMOVED_NODE_415 = _norm_415

SCENARIO_EDGE_REMOVED: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=(
            (_norm_413, _norm_413),
            (_norm_414, _norm_414),
            (_norm_415, _norm_415),
        ),
        removed=(),
        added=(),
    ),
    (_conn_413_414, _conn_414_415),
    (_conn_413_414,),
)


# ---------------------------------------------------------------------------
# SCENARIO_EDGE_REWIRED — same source, destination anchor changes
# ---------------------------------------------------------------------------
# ToolIDs: 416 (source), 417 (destination)
# old_connections: 416 -> 417 at anchor "Input"
# new_connections: 416 -> 417 at anchor "Right"  (rewired = 1 removed + 1 added)

_node_416 = _make_node(416, "Filter", {"Expression": "[Amount] > 1000"})
_node_417 = _make_node(417, "Join", {"JoinByRecordPos": False})

_norm_416 = _norm(_node_416)
_norm_417 = _norm(_node_417)

_conn_rewired_old = AlteryxConnection(
    src_tool=ToolID(416),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(417),
    dst_anchor=AnchorName("Input"),
)
_conn_rewired_new = AlteryxConnection(
    src_tool=ToolID(416),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(417),
    dst_anchor=AnchorName("Right"),
)

# Export individual nodes for tests that need to assert on specific ToolIDs
EDGE_REWIRED_NODE_416 = _norm_416
EDGE_REWIRED_NODE_417 = _norm_417

SCENARIO_EDGE_REWIRED: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_416, _norm_416), (_norm_417, _norm_417)),
        removed=(),
        added=(),
    ),
    (_conn_rewired_old,),
    (_conn_rewired_new,),
)


# ---------------------------------------------------------------------------
# SCENARIO_IDENTICAL_WORKFLOWS — two functionally identical workflows
# ---------------------------------------------------------------------------
# Both old and new have two nodes: Filter 418 and Output 419
# Same configs on both sides → same config_hashes
# One connection: 418 -> 419
# Expected: DiffResult.is_empty == True

_filter_418_config = {"Expression": "[Amount] > 1000"}
_output_419_config = {"OutputFile": {"path": "out.csv"}}

_filter_418 = _make_node(418, "Filter", _filter_418_config)
_output_419 = _make_node(419, "Output", _output_419_config)

# Two NormalizedNode instances with identical configs (same config_hash)
_norm_418_a = _norm(_filter_418)
_norm_418_b = _norm(_filter_418)  # same config → identical config_hash
_norm_419_a = _norm(_output_419)
_norm_419_b = _norm(_output_419)  # same config → identical config_hash

assert _norm_418_a.config_hash == _norm_418_b.config_hash, (
    "SCENARIO_IDENTICAL_WORKFLOWS: hashes for node 418 must be equal"
)
assert _norm_419_a.config_hash == _norm_419_b.config_hash, (
    "SCENARIO_IDENTICAL_WORKFLOWS: hashes for node 419 must be equal"
)

_conn_418_419 = AlteryxConnection(
    src_tool=ToolID(418),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(419),
    dst_anchor=AnchorName("Input"),
)

SCENARIO_IDENTICAL_WORKFLOWS: tuple[
    MatchResult, tuple[AlteryxConnection, ...], tuple[AlteryxConnection, ...]
] = (
    MatchResult(
        matched=((_norm_418_a, _norm_418_b), (_norm_419_a, _norm_419_b)),
        removed=(),
        added=(),
    ),
    (_conn_418_419,),
    (_conn_418_419,),
)
