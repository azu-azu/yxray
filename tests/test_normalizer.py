"""Normalization contract tests.

Validates NORM-01 through NORM-04 behavioral requirements using fixture pairs
from tests.fixtures.normalization. These tests are the regression safety net
for the normalization pipeline stage.

Coverage:
  NORM-01 -- Attribute ordering / canonical serialization
  NORM-02 -- GUID, timestamp, and TempFile path stripping
  NORM-03 -- Position excluded from config_hash; stored as separate field
  NORM-04 -- normalize() is flag-agnostic; --include-positions is Phase 5/9 concern
  Contract -- Source immutability, frozen dataclass, idempotency, hash format
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from alteryx_git_companion.models.types import ToolID
from alteryx_git_companion.models.workflow import AlteryxNode, WorkflowDoc
from alteryx_git_companion.normalizer import normalize
from alteryx_git_companion.normalizer.patterns import GUID_VALUE_KEYS
from tests.fixtures.normalization import (
    ATTR_ORDER_PAIR,
    GUID_PAIR,
    GUID_PAIR_KEY,
    POSITION_DRIFT_PAIR,
    ROUND_TRIP_WORKFLOW,
    TEMPFILE_PAIR,
    TEMPFILE_VS_NOFILE_PAIR,
    TIMESTAMP_PAIR,
    US_DATE_PAIR,
    NodePair,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow(node: AlteryxNode) -> WorkflowDoc:
    """Wrap a single node in a minimal WorkflowDoc for normalization."""
    return WorkflowDoc(filepath="fixture.yxmd", nodes=(node,), connections=())


def _hash_of(node: AlteryxNode) -> str:
    """Return the config_hash for a single node after normalization."""
    return normalize(_make_workflow(node)).nodes[0].config_hash


def _hash_pair(pair: NodePair) -> tuple[str, str]:
    """Return (hash_a, hash_b) for a NodePair's two nodes."""
    return _hash_of(pair.a), _hash_of(pair.b)


# ---------------------------------------------------------------------------
# NORM-01: Canonical serialization -- attribute-order independence
# ---------------------------------------------------------------------------


def test_attr_order_produces_equal_hashes() -> None:
    """Identical configs with different dict key order must hash equally (NORM-01)."""
    hash_a, hash_b = _hash_pair(ATTR_ORDER_PAIR)
    assert hash_a == hash_b, (
        f"Attribute reordering must not change config_hash.\n"
        f"  hash_a = {hash_a!r}\n  hash_b = {hash_b!r}"
    )


# ---------------------------------------------------------------------------
# NORM-02: Noise stripping -- TempFile, timestamps, GUIDs
# ---------------------------------------------------------------------------


def test_tempfile_path_stripped_to_sentinel() -> None:
    """Real Engine_PID_hex TempFile path must hash identically to __TEMPFILE__.

    NORM-02: TempFile noise stripping.
    """
    hash_a, hash_b = _hash_pair(TEMPFILE_PAIR)
    assert hash_a == hash_b, (
        f"TempFile engine path must reduce to __TEMPFILE__ sentinel before hashing.\n"
        f"  hash_a (real path) = {hash_a!r}\n  hash_b (sentinel)  = {hash_b!r}"
    )


def test_tempfile_presence_vs_absence_hashes_differ() -> None:
    """Node with TempFile key vs node without TempFile key must hash differently.

    Stripping equalizes engine paths, not presence/absence of the TempFile key.
    An unrun workflow (no TempFile) and a run workflow (TempFile present) are
    structurally different -- this difference is intentional and must be preserved.
    """
    hash_a, hash_b = _hash_pair(TEMPFILE_VS_NOFILE_PAIR)
    assert hash_a != hash_b, (
        f"Node with TempFile key must hash differently from node without TempFile key."
        f"\n"
        f"  hash_with_tempfile = {hash_a!r}\n"
        f"  hash_without_tempfile = {hash_b!r}"
    )


def test_iso_timestamp_stripped_to_sentinel() -> None:
    """ISO 8601 timestamp must hash identically to __TIMESTAMP__ sentinel (NORM-02)."""
    hash_a, hash_b = _hash_pair(TIMESTAMP_PAIR)
    assert hash_a == hash_b, (
        f"ISO 8601 timestamp must reduce to __TIMESTAMP__ sentinel before hashing.\n"
        f"  hash_a (real timestamp) = {hash_a!r}\n"
        f"  hash_b (sentinel)       = {hash_b!r}"
    )


def test_us_date_not_stripped() -> None:
    """US-format dates (MM/DD/YYYY) must NOT be stripped -- user-supplied filter values.

    Stripping MM/DD/YYYY would cause false-positive hash equality for nodes with
    different user-supplied date filter expressions.
    """
    hash_a, hash_b = _hash_pair(US_DATE_PAIR)
    assert hash_a != hash_b, (
        f"US-format dates must NOT be stripped. "
        f"Different user dates must produce different hashes.\n"
        f"  hash_a = {hash_a!r}\n  hash_b = {hash_b!r}"
    )


@pytest.mark.xfail(
    GUID_PAIR_KEY not in GUID_VALUE_KEYS,
    reason=(
        f"'{GUID_PAIR_KEY}' not yet registered in GUID_VALUE_KEYS in patterns.py. "
        f"Add it when confirmed from real .yxmd file inspection. "
        f"This test becomes a real passing test when the key is registered."
    ),
    strict=True,
)
def test_guid_key_stripped_to_sentinel() -> None:
    """GUID at a known key must hash identically to __GUID__ sentinel (NORM-02).

    Requires GUID_PAIR_KEY to be registered in GUID_VALUE_KEYS in patterns.py.
    Test is marked xfail when GUID_VALUE_KEYS is empty (initial Phase 3 state).
    """
    hash_a, hash_b = _hash_pair(GUID_PAIR)
    assert hash_a == hash_b, (
        f"GUID at key '{GUID_PAIR_KEY}' must reduce to __GUID__ sentinel.\n"
        f"  hash_a (real GUID) = {hash_a!r}\n  hash_b (sentinel)  = {hash_b!r}"
    )


# ---------------------------------------------------------------------------
# NORM-03: Position separation
# ---------------------------------------------------------------------------


def test_position_drift_does_not_affect_hash() -> None:
    """Identical configs with different canvas positions must produce equal config_hash.

    NORM-03: position drift must not affect config_hash.
    """
    hash_a, hash_b = _hash_pair(POSITION_DRIFT_PAIR)
    assert hash_a == hash_b, (
        f"Canvas position drift must not affect config_hash.\n"
        f"  node_a position = ({POSITION_DRIFT_PAIR.a.x}, {POSITION_DRIFT_PAIR.a.y})\n"
        f"  node_b position = ({POSITION_DRIFT_PAIR.b.x}, {POSITION_DRIFT_PAIR.b.y})\n"
        f"  hash_a = {hash_a!r}\n  hash_b = {hash_b!r}"
    )


def test_position_stored_separately_from_hash() -> None:
    """NormalizedNode.position carries source (x, y) and differs when positions differ.

    NORM-03: position data path is separate from config_hash.
    """
    doc = WorkflowDoc(
        filepath="fixture.yxmd",
        nodes=(POSITION_DRIFT_PAIR.a, POSITION_DRIFT_PAIR.b),
        connections=(),
    )
    result = normalize(doc)
    node_a = result.nodes[0]
    node_b = result.nodes[1]

    # Positions must carry source coordinates
    assert node_a.position == (POSITION_DRIFT_PAIR.a.x, POSITION_DRIFT_PAIR.a.y), (
        f"NormalizedNode.position must equal (source.x, source.y). "
        f"Got {node_a.position!r}"
    )
    assert node_b.position == (POSITION_DRIFT_PAIR.b.x, POSITION_DRIFT_PAIR.b.y), (
        f"NormalizedNode.position must equal (source.x, source.y). "
        f"Got {node_b.position!r}"
    )

    # Positions must differ (the nodes have different canvas coordinates)
    assert node_a.position != node_b.position, (
        f"Position data path must preserve canvas differences. "
        f"Got identical positions: {node_a.position!r}"
    )

    # Hashes must still be equal (confirmed by test_position_drift_does_not_affect_hash
    # above, but validated here in context of the full workflow)
    assert node_a.config_hash == node_b.config_hash, (
        f"Hashes must be equal despite position difference.\n"
        f"  hash_a = {node_a.config_hash!r}\n  hash_b = {node_b.config_hash!r}"
    )


# ---------------------------------------------------------------------------
# NORM-04: normalize() is flag-agnostic; --include-positions is Phase 5/9 concern
# ---------------------------------------------------------------------------


def test_normalize_accepts_only_workflow_doc_parameter() -> None:
    """normalize() must accept exactly one parameter: workflow_doc.

    The --include-positions flag is a Phase 5 (differ) and Phase 9 (CLI) concern.
    normalize() is flag-agnostic and must not accept an include_positions parameter.
    Phase 5 reads NormalizedNode.position directly when the flag is set.
    """
    sig = inspect.signature(normalize)
    params = list(sig.parameters.keys())
    assert params == ["workflow_doc"], (
        f"normalize() must have exactly one parameter 'workflow_doc'. "
        f"Found: {params!r}. "
        f"The --include-positions flag is a Phase 5/9 concern, not a normalizer param."
    )


# ---------------------------------------------------------------------------
# Contract: Source immutability, frozen dataclass, idempotency, hash format
# ---------------------------------------------------------------------------


def test_source_config_not_mutated_after_normalize() -> None:
    """Normalization must not mutate the source AlteryxNode.config dict.

    Even though frozen=True prevents attribute reassignment, dict content
    mutation is possible and must not occur.
    """
    original_value = r"C:\Temp\Engine_9999_deadbeef.yxdb"
    node = AlteryxNode(
        tool_id=ToolID(501),
        tool_type="BrowseV2",
        x=0.0,
        y=0.0,
        config={"TempFile": original_value},
    )
    doc = _make_workflow(node)
    normalize(doc)
    assert node.config["TempFile"] == original_value, (
        f"Source AlteryxNode.config was mutated during normalization. "
        f"Expected {original_value!r}, got {node.config['TempFile']!r}. "
        f"Ensure strip_noise() uses copy.deepcopy() before mutation."
    )


def test_normalized_node_is_frozen() -> None:
    """NormalizedNode must be frozen -- assignment must raise FrozenInstanceError."""
    node = AlteryxNode(
        tool_id=ToolID(502),
        tool_type="Filter",
        x=0.0,
        y=0.0,
        config={"Expression": "[x] > 0"},
    )
    result = normalize(_make_workflow(node))
    normalized = result.nodes[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        normalized.config_hash = "newvalue"  # type: ignore[misc]


def test_normalized_workflow_doc_is_frozen() -> None:
    """NormalizedWorkflowDoc is frozen -- FrozenInstanceError raised on assignment."""
    node = AlteryxNode(
        tool_id=ToolID(503),
        tool_type="Filter",
        x=0.0,
        y=0.0,
        config={"Expression": "[x] > 0"},
    )
    result = normalize(_make_workflow(node))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.nodes = ()  # type: ignore[misc]


def test_normalize_is_idempotent() -> None:
    """Calling normalize() twice on the same WorkflowDoc must produce identical hashes.

    normalize() must depend only on its input -- no mutable state, no side effects.
    """
    result_1 = normalize(ROUND_TRIP_WORKFLOW)
    result_2 = normalize(ROUND_TRIP_WORKFLOW)

    assert len(result_1.nodes) == len(result_2.nodes)
    for i, (n1, n2) in enumerate(zip(result_1.nodes, result_2.nodes, strict=True)):
        assert n1.config_hash == n2.config_hash, (
            f"Node {i}: config_hash differs between normalize() calls. "
            f"normalize() must be a pure function with no mutable state."
        )
        assert n1.position == n2.position, (
            f"Node {i}: position differs between normalize() calls."
        )

    assert len(result_1.connections) == len(result_2.connections)


def test_config_hash_is_64_char_hex() -> None:
    """config_hash must be a 64-character lowercase hexadecimal SHA-256 digest."""
    import re

    hex_pattern = re.compile(r"^[0-9a-f]{64}$")
    result = normalize(ROUND_TRIP_WORKFLOW)
    for node in result.nodes:
        assert hex_pattern.match(node.config_hash), (
            f"config_hash must be 64-char lowercase hex. Got: {node.config_hash!r} "
            f"(length={len(node.config_hash)})"
        )


def test_connections_preserved_unchanged() -> None:
    """NormalizedWorkflowDoc.connections must equal source WorkflowDoc.connections."""
    result = normalize(ROUND_TRIP_WORKFLOW)
    assert result.connections == ROUND_TRIP_WORKFLOW.connections, (
        "connections must be preserved unchanged through normalization."
    )
    assert result.source is ROUND_TRIP_WORKFLOW, (
        "NormalizedWorkflowDoc.source must reference the original WorkflowDoc."
    )
