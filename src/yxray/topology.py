"""Workflow graph topology helpers."""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

from yxray.models.workflow import WorkflowDoc
from yxray.tool_registry import is_dataflow_tool


def topo_order(doc: WorkflowDoc) -> list[int]:
    """Return tool IDs in topological order (Kahn's algorithm, sources first).

    Ties among simultaneously-ready nodes are broken by ascending tool_id
    (via a min-heap) rather than readiness order, so that branches of
    uneven length still come out close to numeric/flow order instead of
    being interleaved by whichever branch resolves first.

    AlteryxGuiToolkit nodes are excluded — ToolContainer groups tools
    visually, and the interface tools (Action, Control Parameter, …) rewrite
    configuration at runtime rather than passing rows. Both would otherwise
    appear as spurious sources (in_degree == 0).
    Any remaining nodes after cycle detection are appended in original order.
    """

    # 1. 対象ノードを集める。AlteryxGuiToolkit.* はデータを運ばないので
    #    除外する（残すと入次数0の「偽のソース」として順序に混ざる）。
    #    ToolContainer は見た目のグループ化、Action/ControlParam は実行時の
    #    設定書き換えで、どちらも行を流さない。
    node_ids = [int(n.tool_id) for n in doc.nodes if is_dataflow_tool(n.tool_type)]

    # 2. Connection を依存グラフとしてモデル化し、入次数と後続ノードを作る。
    #    除外済みノード（ToolContainer 等）や未知ノードに触れる接続は無視する。
    in_degree: dict[int, int] = {nid: 0 for nid in node_ids}
    successors: dict[int, list[int]] = {nid: [] for nid in node_ids}
    for edge in doc.connections:
        s, d = int(edge.src_tool), int(edge.dst_tool)
        if s in successors and d in in_degree:
            successors[s].append(d)
            in_degree[d] += 1

    # 3. 入次数0のノード（依存のないソース）を min-heap に積む。
    #    同時に実行可能なノードが複数ある場合、ToolID が小さいものから
    #    取り出すため。
    heap: list[int] = [nid for nid in node_ids if in_degree[nid] == 0]
    heapq.heapify(heap)
    result: list[int] = []

    # 4. ノードを取り出しては後続の依存を減らし、入次数が0になったものを
    #    順次 heap に追加する（Kahn's algorithm 本体）。
    while heap:
        nid = heapq.heappop(heap)
        result.append(nid)
        for s in successors[nid]:
            in_degree[s] -= 1
            if in_degree[s] == 0:
                heapq.heappush(heap, s)

    # 5. heap が空になっても取り出せなかったノードはサイクルに含まれる。
    #    落とさずに元の並び順のまま末尾へ追加する。
    visited = set(result)
    for nid in node_ids:
        if nid not in visited:
            result.append(nid)
    return result


def build_predecessor_map(doc: WorkflowDoc) -> dict[int, list[int]]:
    """Return {dst_tool_id: [src_tool_ids]} for the data-flow connections.

    Only sources that are data tools present in *doc* are listed. Both
    exclusions matter to callers that read preds[0] as "the input frame":

    - Connections are parsed whole, so filtering interface nodes out of
      `doc.nodes` leaves their edges behind. An Action wired into a Filter
      would otherwise make the Filter's first predecessor a tool that has no
      frame, and scaffold emitted `df_2 = df_?[...]` — invalid Python, and
      only when the Action's edge happened to be listed first in the XML.
    - With filtering off those nodes do exist, and would then contribute a
      real-looking `df_<action id>` that is never assigned.
    """
    known_data_tools = {
        int(n.tool_id) for n in doc.nodes if is_dataflow_tool(n.tool_type)
    }
    preds: dict[int, list[int]] = {}
    for c in doc.connections:
        src = int(c.src_tool)
        if src not in known_data_tools:
            continue
        preds.setdefault(int(c.dst_tool), []).append(src)
    return preds


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
