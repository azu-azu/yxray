"""Diff result types returned by the differ stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alteryx_git_companion.models.types import AnchorName, ToolID
from alteryx_git_companion.models.workflow import AlteryxNode


@dataclass(frozen=True, kw_only=True, slots=True)
class NodeDiff:
    """A modification detected for a single matched tool."""

    tool_id: ToolID
    old_node: AlteryxNode
    new_node: AlteryxNode
    field_diffs: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    """Maps field name -> (old_value, new_value) for each changed field only."""


@dataclass(frozen=True, kw_only=True, slots=True)
class EdgeDiff:
    """A connection change (addition or removal) in the diff."""

    src_tool: ToolID
    src_anchor: AnchorName
    dst_tool: ToolID
    dst_anchor: AnchorName
    change_type: str  # Literal["added", "removed"] — str for frozen compatibility


@dataclass(frozen=True, kw_only=True)  # slots=True removed — required for @property
class DiffResult:
    """Complete diff result between two WorkflowDoc instances."""

    added_nodes: tuple[AlteryxNode, ...] = field(default_factory=tuple)
    removed_nodes: tuple[AlteryxNode, ...] = field(default_factory=tuple)
    modified_nodes: tuple[NodeDiff, ...] = field(default_factory=tuple)
    edge_diffs: tuple[EdgeDiff, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        """True when no additions, removals, modifications, or edge diffs."""
        return (
            not self.added_nodes
            and not self.removed_nodes
            and not self.modified_nodes
            and not self.edge_diffs
        )
