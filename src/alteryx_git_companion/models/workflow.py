"""Workflow document and node models parsed from .yxmd XML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alteryx_git_companion.models.types import AnchorName, ToolID


@dataclass(frozen=True, kw_only=True, slots=True)
class AlteryxNode:
    """A single tool on the Alteryx canvas."""

    tool_id: ToolID
    tool_type: str
    x: float
    y: float
    config: dict[str, Any] = field(default_factory=dict)
    """Parsed tool configuration as flat key/value map.
    Set once at parse time. Phase 3 (normalizer) iterates this dict to strip
    metadata and produce a ConfigHash. Phase 5 (differ) compares dicts field-by-field.
    Raw XML is NOT stored here — the parser must produce a structured dict.
    """


@dataclass(frozen=True, kw_only=True, slots=True)
class AlteryxConnection:
    """A directed edge connecting two tool anchors."""

    src_tool: ToolID
    src_anchor: AnchorName
    dst_tool: ToolID
    dst_anchor: AnchorName


@dataclass(frozen=True, kw_only=True, slots=True)
class WorkflowDoc:
    """Root document parsed from a single .yxmd file."""

    filepath: str
    nodes: tuple[AlteryxNode, ...] = field(default_factory=tuple)
    connections: tuple[AlteryxConnection, ...] = field(default_factory=tuple)
    """All connections for this workflow. Stored on WorkflowDoc, not on AlteryxNode.
    AlteryxNode is topology-free — it has no references to connections.
    """
