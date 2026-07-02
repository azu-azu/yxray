"""Workflow graph topology helpers."""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

from yxray.models.workflow import WorkflowDoc


def topo_order(doc: WorkflowDoc) -> list[int]:
    """Return tool IDs in topological order (Kahn's algorithm, sources first).

    Ties among simultaneously-ready nodes are broken by ascending tool_id
    (via a min-heap) rather than readiness order, so that branches of
    uneven length still come out close to numeric/flow order instead of
    being interleaved by whichever branch resolves first.

    ToolContainer nodes are excluded — they carry no data-flow information
    and would otherwise appear as spurious sources (in_degree == 0).
    Any remaining nodes after cycle detection are appended in original order.
    """
    node_ids = [
        int(n.tool_id) for n in doc.nodes if "ToolContainer" not in n.tool_type
    ]
    in_degree: dict[int, int] = {nid: 0 for nid in node_ids}
    successors: dict[int, list[int]] = {nid: [] for nid in node_ids}
    for edge in doc.connections:
        s, d = int(edge.src_tool), int(edge.dst_tool)
        if s in successors and d in in_degree:
            successors[s].append(d)
            in_degree[d] += 1
    heap: list[int] = [nid for nid in node_ids if in_degree[nid] == 0]
    heapq.heapify(heap)
    result: list[int] = []
    while heap:
        nid = heapq.heappop(heap)
        result.append(nid)
        for s in successors[nid]:
            in_degree[s] -= 1
            if in_degree[s] == 0:
                heapq.heappush(heap, s)
    visited = set(result)
    for nid in node_ids:
        if nid not in visited:
            result.append(nid)
    return result


def compute_node_layer(doc: WorkflowDoc) -> dict[int, int]:
    node_ids = [
        node.tool_id for node in doc.nodes if "ToolContainer" not in node.tool_type
    ]
    degree: dict[Any, int] = {node_id: 0 for node_id in node_ids}
    successors: dict[Any, list[Any]] = {node_id: [] for node_id in node_ids}
    for edge in doc.connections:
        if edge.src_tool in successors and edge.dst_tool in degree:
            successors[edge.src_tool].append(edge.dst_tool)
            degree[edge.dst_tool] += 1
    layer: dict[Any, int] = {node_id: 0 for node_id in node_ids if degree[node_id] == 0}
    queue: deque[Any] = deque(layer)
    while queue:
        node_id = queue.popleft()
        for successor in successors[node_id]:
            layer[successor] = max(layer.get(successor, 0), layer[node_id] + 1)
            degree[successor] -= 1
            if degree[successor] == 0:
                queue.append(successor)
    for node_id in node_ids:
        layer.setdefault(node_id, len(node_ids))
    return {int(node_id): value for node_id, value in layer.items()}
