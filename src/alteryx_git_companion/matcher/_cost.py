"""Internal cost computation helpers for the Hungarian algorithm pass.

This module is NOT part of the public surface (underscore prefix).
It is consumed exclusively by _hungarian_match() in matcher.py.
"""

from __future__ import annotations

import math

import numpy as np

from alteryx_git_companion.models import NormalizedNode


def _position_cost(
    pos_a: tuple[float, float],
    pos_b: tuple[float, float],
    x_range: float,
    y_range: float,
) -> float:
    """Normalized Euclidean canvas distance in [0.0, 1.0].

    Each axis is independently normalized by its range. The maximum possible
    normalized distance for a unit square is sqrt(2), so dividing by sqrt(2)
    clamps the result to [0.0, 1.0].

    Args:
        pos_a: (x, y) canvas coordinates of node A.
        pos_b: (x, y) canvas coordinates of node B.
        x_range: horizontal spread of all nodes (union of old and new groups).
        y_range: vertical spread of all nodes (union of old and new groups).

    Returns:
        Float in [0.0, 1.0]. 0.0 means identical position; 1.0 means maximum
        possible distance within the canvas bounds.
    """
    dx = (pos_a[0] - pos_b[0]) / x_range
    dy = (pos_a[1] - pos_b[1]) / y_range
    dist = math.hypot(dx, dy)
    return min(dist / math.sqrt(2), 1.0)


def _hash_cost(old_node: NormalizedNode, new_node: NormalizedNode) -> float:
    """Binary config-hash similarity cost.

    Returns 0.0 if the nodes share the same config hash (identical tool
    configuration), or 1.0 if they differ. No partial credit — equality only,
    per project CONTEXT.md design decision.

    Args:
        old_node: Node from the old workflow.
        new_node: Node from the new workflow.

    Returns:
        0.0 (identical config) or 1.0 (different config).
    """
    return 0.0 if old_node.config_hash == new_node.config_hash else 1.0


def _build_cost_matrix(
    old_group: list[NormalizedNode],
    new_group: list[NormalizedNode],
) -> np.ndarray:
    """Build a float64 cost matrix of shape (len(old_group), len(new_group)).

    Cost is the equal-weighted (0.5 / 0.5) combination of normalised canvas
    distance and binary config-hash similarity:

        cost[i, j] = 0.5 * _position_cost(...) + 0.5 * _hash_cost(...)

    Canvas bounds are derived from the UNION of both groups so that the
    normalisation is consistent across both sides of the assignment.

    Zero-range axes default to 1.0 to prevent ZeroDivisionError when all nodes
    in a type group share the same x or y coordinate.

    Args:
        old_group: Nodes from the old workflow for a single tool_type.
        new_group: Nodes from the new workflow for the same tool_type.

    Returns:
        numpy float64 array of shape (len(old_group), len(new_group)) with
        all values in [0.0, 1.0].
    """
    all_positions = [n.position for n in old_group] + [n.position for n in new_group]
    xs = [p[0] for p in all_positions]
    ys = [p[1] for p in all_positions]

    x_range = (max(xs) - min(xs)) if len(xs) > 1 else 1.0
    y_range = (max(ys) - min(ys)) if len(ys) > 1 else 1.0

    # Guard: 0-range axes collapse to 1.0 (prevents ZeroDivisionError)
    if x_range == 0.0:
        x_range = 1.0
    if y_range == 0.0:
        y_range = 1.0

    m = len(old_group)
    n = len(new_group)
    cost = np.empty((m, n), dtype=np.float64)

    for i, old in enumerate(old_group):
        for j, new in enumerate(new_group):
            pos_c = _position_cost(old.position, new.position, x_range, y_range)
            hash_c = _hash_cost(old, new)
            cost[i, j] = 0.5 * pos_c + 0.5 * hash_c

    return cost
