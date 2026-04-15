"""Fixture pairs for normalization contract tests.

Each fixture pair documents what the normalization pipeline MUST produce.
Pairs are consumed by tests/test_normalizer.py.

Fixture naming convention:
  *_PAIR: A NamedTuple with (a, b, expect_equal: bool)
    expect_equal=True  -> normalize(a).config_hash == normalize(b).config_hash
    expect_equal=False -> normalize(a).config_hash != normalize(b).config_hash

All AlteryxNode instances use integer ToolIDs starting at 101 to avoid conflicts
with any fixture nodes in other test files.
"""

from __future__ import annotations

from typing import NamedTuple

from alteryx_git_companion.models.types import AnchorName, ToolID
from alteryx_git_companion.models.workflow import (
    AlteryxConnection,
    AlteryxNode,
    WorkflowDoc,
)


class NodePair(NamedTuple):
    """A pair of AlteryxNode instances with a documented hash equality expectation."""

    a: AlteryxNode
    b: AlteryxNode
    expect_equal: bool
    description: str


# ---------------------------------------------------------------------------
# ATTR_ORDER_PAIR — NORM-01: C14N / attribute-order independence
# ---------------------------------------------------------------------------
# Two nodes with identical config values but different dict key ordering.
# json.dumps(sort_keys=True) must produce identical canonical bytes for both.
ATTR_ORDER_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(101),
        tool_type="TextInput",
        x=100.0,
        y=100.0,
        config={
            "File": {
                "@type": "csv",
                "@RecordLimit": "0",
                "#text": "data.csv",
            }
        },
    ),
    b=AlteryxNode(
        tool_id=ToolID(102),
        tool_type="TextInput",
        x=100.0,
        y=100.0,
        config={
            "File": {
                "@RecordLimit": "0",
                "#text": "data.csv",
                "@type": "csv",
            }
        },
    ),
    expect_equal=True,
    description=(
        "Identical config with different key order must hash equally (NORM-01)"
    ),
)


# ---------------------------------------------------------------------------
# POSITION_DRIFT_PAIR — NORM-03: Position excluded from config_hash
# ---------------------------------------------------------------------------
# Two nodes with identical config but different canvas X/Y positions.
# config_hash must be EQUAL (position is a separate data path).
# NormalizedNode.position will differ between the two nodes — that is correct.
POSITION_DRIFT_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(103),
        tool_type="Filter",
        x=200.0,
        y=300.0,
        config={"Expression": "[Amount] > 1000"},
    ),
    b=AlteryxNode(
        tool_id=ToolID(104),
        tool_type="Filter",
        x=750.0,  # nudged on canvas
        y=125.0,  # nudged on canvas
        config={"Expression": "[Amount] > 1000"},
    ),
    expect_equal=True,
    description=(
        "Identical config with different canvas positions must hash equally (NORM-03)"
    ),
)


# ---------------------------------------------------------------------------
# TEMPFILE_PAIR — NORM-02: TempFile path stripping
# ---------------------------------------------------------------------------
# One node has a real Windows TempFile engine path; the other has the sentinel.
# After stripping, both reduce to {"TempFile": "__TEMPFILE__"} — hashes must be EQUAL.
# Path format confirmed from real .yxmd files: Engine_{PID}_{hexhash}
TEMPFILE_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(105),
        tool_type="BrowseV2",
        x=0.0,
        y=0.0,
        config={
            "TempFile": (
                r"C:\Users\analyst\AppData\Local\Temp\2"
                r"\Engine_3640_96bb13fd499947b58eac9db8a9db378a"
                r"\Engine_1952_94164fc329fc43f9b6f37832878b4181.yxdb"
            )
        },
    ),
    b=AlteryxNode(
        tool_id=ToolID(106),
        tool_type="BrowseV2",
        x=0.0,
        y=0.0,
        config={"TempFile": "__TEMPFILE__"},
    ),
    expect_equal=True,
    description=(
        "Real TempFile engine path must hash same as __TEMPFILE__ sentinel (NORM-02)"
    ),
)


# ---------------------------------------------------------------------------
# TEMPFILE_VS_NOFILE_PAIR — NORM-02: TempFile presence differs
# ---------------------------------------------------------------------------
# One node has a TempFile key (workflow has been run); the other has no TempFile key.
# These are genuinely different structures — hashes must DIFFER.
# This is correct behavior: the normalizer equalizes paths, not presence/absence.
TEMPFILE_VS_NOFILE_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(107),
        tool_type="BrowseV2",
        x=0.0,
        y=0.0,
        config={
            "TempFile": (
                r"C:\Users\analyst\AppData\Local\Temp\Engine_1111_aabbccdd.yxdb"
            )
        },
    ),
    b=AlteryxNode(
        tool_id=ToolID(108),
        tool_type="BrowseV2",
        x=0.0,
        y=0.0,
        config={},  # no TempFile — workflow not yet run
    ),
    expect_equal=False,
    description=(
        "Node with TempFile key vs node without TempFile key must hash differently"
        " (structure differs)"
    ),
)


# ---------------------------------------------------------------------------
# TIMESTAMP_PAIR — NORM-02: ISO 8601 timestamp stripping
# ---------------------------------------------------------------------------
# One node config has an ISO 8601 timestamp; the other has the sentinel.
# Both must hash EQUALLY after stripping.
# The timestamp simulates an auto-generated LastModified or RunDate field.
TIMESTAMP_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(109),
        tool_type="ReportingSnapshot",
        x=0.0,
        y=0.0,
        config={"LastRunDate": "2024-03-15T14:30:00Z", "ReportTitle": "Q1 Summary"},
    ),
    b=AlteryxNode(
        tool_id=ToolID(110),
        tool_type="ReportingSnapshot",
        x=0.0,
        y=0.0,
        config={"LastRunDate": "__TIMESTAMP__", "ReportTitle": "Q1 Summary"},
    ),
    expect_equal=True,
    description="ISO 8601 timestamp must hash same as __TIMESTAMP__ sentinel (NORM-02)",
)


# ---------------------------------------------------------------------------
# GUID_PAIR — NORM-02: GUID key-targeted stripping
# ---------------------------------------------------------------------------
# One node has a GUID injected at a known key; the other has the sentinel.
# IMPORTANT: This pair only demonstrates equal hashes when the key is in
# GUID_VALUE_KEYS in patterns.py. The key used here ("@GUID") is injected as
# a representative example — add it to GUID_VALUE_KEYS in patterns.py when
# confirmed from real .yxmd file inspection.
# If GUID_VALUE_KEYS is empty (initial state), this pair will NOT hash equally.
# The test in test_normalizer.py must skip or xfail when GUID_VALUE_KEYS is empty.
GUID_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(111),
        tool_type="Join",
        x=0.0,
        y=0.0,
        config={
            "JoinConfig": {
                "@GUID": "550e8400-e29b-41d4-a716-446655440000",
                "Mode": "Inner",
            }
        },
    ),
    b=AlteryxNode(
        tool_id=ToolID(112),
        tool_type="Join",
        x=0.0,
        y=0.0,
        config={"JoinConfig": {"@GUID": "__GUID__", "Mode": "Inner"}},
    ),
    expect_equal=True,
    description=(
        "GUID at known key must hash same as __GUID__ sentinel (NORM-02). "
        "Requires '@GUID' in GUID_VALUE_KEYS — test must xfail if key not registered."
    ),
)

# Key that GUID_PAIR uses — referenced in test file to skip/xfail appropriately
GUID_PAIR_KEY: str = "@GUID"


# ---------------------------------------------------------------------------
# US_DATE_PAIR — Negative test: MM/DD/YYYY must NOT be stripped
# ---------------------------------------------------------------------------
# User-supplied US-format filter dates must survive normalization unchanged.
# Two nodes with different US dates must hash DIFFERENTLY (dates are real config).
US_DATE_PAIR = NodePair(
    a=AlteryxNode(
        tool_id=ToolID(113),
        tool_type="Filter",
        x=0.0,
        y=0.0,
        config={"Expression": "[Date] > '03/15/2024'"},
    ),
    b=AlteryxNode(
        tool_id=ToolID(114),
        tool_type="Filter",
        x=0.0,
        y=0.0,
        config={"Expression": "[Date] > '12/31/2024'"},
    ),
    expect_equal=False,
    description=(
        "US-format dates (MM/DD/YYYY) must NOT be stripped — different user dates"
        " must hash differently"
    ),
)


# ---------------------------------------------------------------------------
# ROUND_TRIP_WORKFLOW — Idempotency: normalize twice, same output
# ---------------------------------------------------------------------------
# A complete WorkflowDoc with multiple nodes and a connection.
# normalize(doc) called twice must produce the same NormalizedWorkflowDoc
# (same config_hash values, same position values, same connection count).
_node_a = AlteryxNode(
    tool_id=ToolID(201),
    tool_type="TextInput",
    x=100.0,
    y=200.0,
    config={"NumRows": "10", "Fields": {"Field": {"@name": "ID", "@type": "Int32"}}},
)
_node_b = AlteryxNode(
    tool_id=ToolID(202),
    tool_type="Filter",
    x=300.0,
    y=200.0,
    config={"Expression": "[Amount] > 1000"},
)
_connection = AlteryxConnection(
    src_tool=ToolID(201),
    src_anchor=AnchorName("Output"),
    dst_tool=ToolID(202),
    dst_anchor=AnchorName("Input"),
)
ROUND_TRIP_WORKFLOW = WorkflowDoc(
    filepath="tests/fixtures/round_trip.yxmd",
    nodes=(_node_a, _node_b),
    connections=(_connection,),
)
