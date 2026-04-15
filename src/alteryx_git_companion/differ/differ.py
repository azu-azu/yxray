"""Core diff computation for alteryx_git_companion.

Three computation paths:
  1. Node additions / removals — from MatchResult.added / MatchResult.removed
  2. Field-level config modifications — matched pairs where config_hash differs
  3. Edge symmetric difference — from old_connections vs new_connections

Public entry point: diff()
"""

from __future__ import annotations

from typing import Any

from deepdiff import DeepDiff

from alteryx_git_companion.matcher.matcher import MatchResult
from alteryx_git_companion.models import (
    AlteryxConnection,
    AlteryxNode,
    DiffResult,
    EdgeDiff,
    NodeDiff,
)

# Excluded field paths (dotted notation) — start empty per research recommendation.
# Populated as GUID-like fields are discovered from real fixture inspection.
_EXCLUDED_FIELDS: frozenset[str] = frozenset()


def diff(
    match_result: MatchResult,
    old_connections: tuple[AlteryxConnection, ...],
    new_connections: tuple[AlteryxConnection, ...],
    *,
    include_positions: bool = False,
) -> DiffResult:
    """Compute the complete diff between two workflow states.

    Args:
        match_result: Output from the node matcher stage.
        old_connections: Connections from the old workflow.
        new_connections: Connections from the new workflow.
        include_positions: When True, canvas X/Y position changes are detected
            as modifications even when tool config is otherwise identical.
            Default False excludes position-only changes (layout noise).

    Returns:
        DiffResult containing added/removed nodes, modified node diffs, and edge diffs.
    """
    # Path 1: added nodes — nodes in new workflow absent from old
    added_nodes: tuple[AlteryxNode, ...] = tuple(n.source for n in match_result.added)

    # Path 2: removed nodes — nodes in old workflow absent from new
    removed_nodes: tuple[AlteryxNode, ...] = tuple(
        n.source for n in match_result.removed
    )

    # Path 3: modified nodes — matched pairs with differing config_hash or position
    modified_nodes_list: list[NodeDiff] = []
    for old_norm, new_norm in match_result.matched:
        config_changed = old_norm.config_hash != new_norm.config_hash
        position_changed = include_positions and (
            old_norm.position != new_norm.position
        )
        if config_changed or position_changed:
            if config_changed:
                node_diff = _diff_node(old_norm.source, new_norm.source)
            else:
                # Position-only change: build NodeDiff directly, bypass _diff_node()
                # (_diff_node() raises ValueError when DeepDiff finds no config diffs)
                node_diff = NodeDiff(
                    tool_id=old_norm.source.tool_id,
                    old_node=old_norm.source,
                    new_node=new_norm.source,
                    field_diffs={"position": (old_norm.position, new_norm.position)},
                )
            modified_nodes_list.append(node_diff)
    modified_nodes: tuple[NodeDiff, ...] = tuple(modified_nodes_list)

    # Path 4: edge symmetric difference
    edge_diffs = _diff_edges(old_connections, new_connections)

    return DiffResult(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        modified_nodes=modified_nodes,
        edge_diffs=edge_diffs,
    )


def _deepdiff_path_to_dotted(path: str) -> str:
    """Convert a DeepDiff path to dotted notation.

    Examples:
        "root['key1']['key2']"  -> "key1.key2"
        "root['Fields'][3]"     -> "Fields"   (numeric indices stripped)
        "root['key']"           -> "key"
    """
    # Strip leading "root" prefix
    if path.startswith("root"):
        path = path[4:]

    # Strip leading/trailing brackets
    path = path.strip("[]")

    # Split on "][" to get individual parts
    parts = path.split("][")

    dotted_parts: list[str] = []
    for part in parts:
        # Strip surrounding quotes (single or double)
        stripped = part.strip("'\"")
        # Skip numeric index parts (list indices) — lists are treated atomically
        if stripped.isdigit():
            break
        if stripped:
            dotted_parts.append(stripped)

    return ".".join(dotted_parts)


def _get_nested_value(config: dict[str, Any], deepdiff_path: str) -> Any:
    """Navigate a config dict following a DeepDiff path to retrieve the value.

    Used for dictionary_item_added / dictionary_item_removed to get the
    present side's value.

    Args:
        config: The config dict to navigate.
        deepdiff_path: A DeepDiff path string like "root['key1']['key2']".

    Returns:
        The value at the given path, or None if not found.
    """
    # Strip "root" prefix
    path = deepdiff_path
    if path.startswith("root"):
        path = path[4:]

    # Strip surrounding brackets
    path = path.strip("[]")

    if not path:
        return config

    # Split on "]["
    parts = path.split("][")
    current: Any = config
    for part in parts:
        stripped = part.strip("'\"")
        try:
            if isinstance(current, dict):
                current = current[stripped]
            elif isinstance(current, list | tuple):
                current = current[int(stripped)]
            else:
                return None
        except (KeyError, IndexError, ValueError, TypeError):
            return None
    return current


def _diff_node(old_node: AlteryxNode, new_node: AlteryxNode) -> NodeDiff:
    """Compute field-level config diff between two matched nodes.

    Uses DeepDiff to identify changed fields. List fields are treated as
    atomic values — if any element differs, the whole list appears as before/after.

    Args:
        old_node: The node from the old workflow.
        new_node: The node from the new workflow.

    Returns:
        NodeDiff with field_diffs populated for all changed fields.

    Raises:
        ValueError: If config_hash differed but DeepDiff found no changes after
                    exclusions — this indicates a developer bug (hash collision or
                    incorrect exclusion list).
    """
    dd = DeepDiff(
        old_node.config,
        new_node.config,
        ignore_order=False,
        verbose_level=2,
    )

    field_diffs: dict[str, tuple[Any, Any]] = {}

    # Process each change type from DeepDiff output
    for change_type, changes in dd.items():
        if change_type == "values_changed":
            for path, change in changes.items():
                dotted = _deepdiff_path_to_dotted(path)
                if dotted not in _EXCLUDED_FIELDS:
                    field_diffs[dotted] = (change["old_value"], change["new_value"])

        elif change_type == "dictionary_item_added":
            for path in changes:
                dotted = _deepdiff_path_to_dotted(path)
                if dotted not in _EXCLUDED_FIELDS:
                    new_val = _get_nested_value(new_node.config, path)
                    field_diffs[dotted] = (None, new_val)

        elif change_type == "dictionary_item_removed":
            for path in changes:
                dotted = _deepdiff_path_to_dotted(path)
                if dotted not in _EXCLUDED_FIELDS:
                    old_val = _get_nested_value(old_node.config, path)
                    field_diffs[dotted] = (old_val, None)

        elif change_type in ("iterable_item_added", "iterable_item_removed"):
            # List fields are treated atomically — surface the PARENT list as
            # before/after rather than individual element changes.
            for path in changes:
                parent_dotted = _deepdiff_path_to_dotted(path)
                if parent_dotted not in _EXCLUDED_FIELDS:
                    # Get the full list from both sides (atomic treatment)
                    # Find the parent path by stripping the numeric index
                    parent_path = _get_parent_path(path)
                    old_list = _get_nested_value(old_node.config, parent_path)
                    new_list = _get_nested_value(new_node.config, parent_path)
                    field_diffs[parent_dotted] = (old_list, new_list)

        elif change_type == "type_changes":
            for path, change in changes.items():
                dotted = _deepdiff_path_to_dotted(path)
                if dotted not in _EXCLUDED_FIELDS:
                    field_diffs[dotted] = (
                        change.get("old_value"),
                        change.get("new_value"),
                    )

    if not field_diffs:
        raise ValueError(
            f"config_hash differed for tool_id={old_node.tool_id!r} but DeepDiff "
            f"found no changes after exclusions. This is a developer bug — check "
            f"_EXCLUDED_FIELDS or the hash computation."
        )

    return NodeDiff(
        tool_id=old_node.tool_id,
        old_node=old_node,
        new_node=new_node,
        field_diffs=field_diffs,
    )


def _get_parent_path(path: str) -> str:
    """Strip the final numeric index from a DeepDiff path to get the parent path.

    Example: "root['Fields'][3]" -> "root['Fields']"
    """
    # Find the last "[N]" numeric index segment and strip it
    import re

    return re.sub(r"\[\d+\]$", "", path)


def _diff_edges(
    old_connections: tuple[AlteryxConnection, ...],
    new_connections: tuple[AlteryxConnection, ...],
) -> tuple[EdgeDiff, ...]:
    """Compute edge symmetric difference between two connection sets.

    Args:
        old_connections: Connections from the old workflow.
        new_connections: Connections from the new workflow.

    Returns:
        Tuple of EdgeDiff entries for all removed and added connections,
        sorted deterministically by (src_tool, src_anchor, dst_tool, dst_anchor).
    """
    old_set = frozenset(old_connections)
    new_set = frozenset(new_connections)

    removed = old_set - new_set
    added = new_set - old_set

    edge_diffs: list[EdgeDiff] = []

    # Sort removed connections for deterministic output
    for conn in sorted(
        removed, key=lambda c: (c.src_tool, c.src_anchor, c.dst_tool, c.dst_anchor)
    ):
        edge_diffs.append(
            EdgeDiff(
                src_tool=conn.src_tool,
                src_anchor=conn.src_anchor,
                dst_tool=conn.dst_tool,
                dst_anchor=conn.dst_anchor,
                change_type="removed",
            )
        )

    # Sort added connections for deterministic output
    for conn in sorted(
        added, key=lambda c: (c.src_tool, c.src_anchor, c.dst_tool, c.dst_anchor)
    ):
        edge_diffs.append(
            EdgeDiff(
                src_tool=conn.src_tool,
                src_anchor=conn.src_anchor,
                dst_tool=conn.dst_tool,
                dst_anchor=conn.dst_anchor,
                change_type="added",
            )
        )

    return tuple(edge_diffs)
