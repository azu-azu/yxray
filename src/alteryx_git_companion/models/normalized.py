"""Normalized pipeline output models produced by the normalization stage."""

from __future__ import annotations

from dataclasses import dataclass

from alteryx_git_companion.models.types import ConfigHash
from alteryx_git_companion.models.workflow import (
    AlteryxConnection,
    AlteryxNode,
    WorkflowDoc,
)


@dataclass(frozen=True, kw_only=True, slots=True)
class NormalizedNode:
    """A single tool node after normalization.

    Carries the original AlteryxNode for identity fields, plus the two separate
    data paths produced by normalization:
    - config_hash: SHA-256 hex digest of the canonicalized tool configuration
    - position: (x, y) canvas coordinates, separated from config_hash so that
      layout-only moves never affect the config_hash comparison path
    """

    source: AlteryxNode
    """Original parsed node. Downstream stages read tool_id and tool_type from here."""

    config_hash: ConfigHash
    """SHA-256 hex digest produced by the normalizer from source.config.
    This field is the config comparison path (NORM-03).
    """

    position: tuple[float, float]
    """Canvas coordinates (x, y) carried from source.x and source.y.
    This field is the position comparison path (NORM-04), kept separate from
    config_hash so that layout noise cannot cause false-positive config diffs.
    """


@dataclass(frozen=True, kw_only=True, slots=True)
class NormalizedWorkflowDoc:
    """A workflow document after all nodes have been normalized.

    Carries the original WorkflowDoc for downstream metadata access.
    Connections are preserved unchanged — normalization only affects node config.
    """

    source: WorkflowDoc
    """Original parsed workflow document."""

    nodes: tuple[NormalizedNode, ...]
    """All nodes replaced by their normalized forms, in the same order as source.nodes.
    """

    connections: tuple[AlteryxConnection, ...]
    """Preserved unchanged from source.connections.
    Normalization does not touch topology.
    """
