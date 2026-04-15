"""Node matcher implementation for alteryx_git_companion.

Two-pass node matching:
  Pass 1 (this file): Exact ToolID lookup — O(n), handles common case.
  Pass 2 (this file): Hungarian algorithm per tool-type — handles ToolID churn.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from alteryx_git_companion.matcher._cost import _build_cost_matrix
from alteryx_git_companion.models import NormalizedNode

COST_THRESHOLD = 0.8


@dataclass(frozen=True, kw_only=True, slots=True)
class MatchResult:
    """Output of the two-pass node matcher.

    matched: pairs of (old_node, new_node) successfully paired
    removed: nodes in old workflow absent from new (genuine removals)
    added:   nodes in new workflow absent from old (genuine additions)
    """

    matched: tuple[tuple[NormalizedNode, NormalizedNode], ...]
    removed: tuple[NormalizedNode, ...]
    added: tuple[NormalizedNode, ...]


def match(
    old_nodes: list[NormalizedNode],
    new_nodes: list[NormalizedNode],
) -> MatchResult:
    """Two-pass node matcher. Pass 1: exact ToolID. Pass 2: Hungarian per-type."""
    matched: list[tuple[NormalizedNode, NormalizedNode]] = []

    # Pass 1: exact ToolID lookup — O(n)
    new_by_id = {n.source.tool_id: n for n in new_nodes}
    unmatched_old: list[NormalizedNode] = []
    matched_new_ids: set[int] = set()

    for old in old_nodes:
        if old.source.tool_id in new_by_id:
            matched.append((old, new_by_id[old.source.tool_id]))
            matched_new_ids.add(old.source.tool_id)
        else:
            unmatched_old.append(old)

    unmatched_new = [n for n in new_nodes if n.source.tool_id not in matched_new_ids]

    # Pass 2: Hungarian fallback — skip entirely if nothing left to match
    if unmatched_old and unmatched_new:
        extra_matched, remaining_old, remaining_new = _hungarian_match(
            unmatched_old, unmatched_new
        )
        matched.extend(extra_matched)
        unmatched_old = remaining_old
        unmatched_new = remaining_new

    return MatchResult(
        matched=tuple(matched),
        removed=tuple(unmatched_old),
        added=tuple(unmatched_new),
    )


def _hungarian_match(
    unmatched_old: list[NormalizedNode],
    unmatched_new: list[NormalizedNode],
) -> tuple[
    list[tuple[NormalizedNode, NormalizedNode]],
    list[NormalizedNode],
    list[NormalizedNode],
]:
    """Run Hungarian algorithm per tool_type group.

    Groups unmatched nodes by tool_type (cross-type pairs are never compared),
    then runs one linear_sum_assignment call per type group. Threshold rejection
    is applied AFTER assignment at the pair level — pre-filtering with inf/nan
    corrupts scipy's solver.

    Returns:
        (matched, leftover_old, leftover_new) where:
        - matched:       pairs accepted by cost <= COST_THRESHOLD
        - leftover_old:  old nodes with no acceptable match (go to removed)
        - leftover_new:  new nodes with no acceptable match (go to added)
    """
    # Group by tool_type — cross-type pairs are NEVER compared (hard block)
    old_by_type: dict[str, list[NormalizedNode]] = defaultdict(list)
    new_by_type: dict[str, list[NormalizedNode]] = defaultdict(list)
    for node in unmatched_old:
        old_by_type[node.source.tool_type].append(node)
    for node in unmatched_new:
        new_by_type[node.source.tool_type].append(node)

    # Union — catches types present only in old or only in new (avoids dropping nodes)
    all_types = set(old_by_type) | set(new_by_type)

    matched: list[tuple[NormalizedNode, NormalizedNode]] = []
    leftover_old: list[NormalizedNode] = []
    leftover_new: list[NormalizedNode] = []

    for tool_type in all_types:
        old_group = old_by_type.get(tool_type, [])
        new_group = new_by_type.get(tool_type, [])

        # No old of this type — all new go to additions
        if not old_group:
            leftover_new.extend(new_group)
            continue
        # No new of this type — all old go to removals
        if not new_group:
            leftover_old.extend(old_group)
            continue

        # Build cost matrix and run Hungarian assignment
        cost: np.ndarray = _build_cost_matrix(old_group, new_group)
        row_ind: np.ndarray
        col_ind: np.ndarray
        row_ind, col_ind = linear_sum_assignment(cost)
        # IMPORTANT: threshold applied AFTER assignment (not before)
        # Pre-filtering with inf/nan corrupts the scipy solver

        matched_old_idx: set[int] = set()
        matched_new_idx: set[int] = set()

        for r, c in zip(row_ind.tolist(), col_ind.tolist(), strict=True):
            if cost[r, c] <= COST_THRESHOLD:
                matched.append((old_group[r], new_group[c]))
                matched_old_idx.add(r)
                matched_new_idx.add(c)
            # cost > COST_THRESHOLD: rejected — both sides fall through to leftovers

        leftover_old.extend(
            n for i, n in enumerate(old_group) if i not in matched_old_idx
        )
        leftover_new.extend(
            n for i, n in enumerate(new_group) if i not in matched_new_idx
        )

    return matched, leftover_old, leftover_new
