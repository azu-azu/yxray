"""Workflow graph topology helpers."""

from __future__ import annotations

from collections import deque
from typing import Any

from yxray.models.workflow import WorkflowDoc


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
