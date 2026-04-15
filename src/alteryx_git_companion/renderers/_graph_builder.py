# ruff: noqa: E501
"""Graph-building helpers for the visual graph renderer.

Public API:
    build_digraph(result, all_connections, all_nodes) -> nx.DiGraph
    hierarchical_positions(G) -> dict[int, tuple[float, float]]
    canvas_positions(nodes_old, nodes_new) -> dict[int, tuple[float, float]]
    load_vis_js() -> str
    build_split_node_list(result, nodes_old, nodes_new) -> tuple[list[dict], list[dict]]

This module is internal (underscore prefix); it is consumed exclusively by
graph_renderer.py in Plan 02. Unit tests import directly from here.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
from typing import Any

import networkx as nx

from alteryx_git_companion.models import DiffResult
from alteryx_git_companion.models.workflow import AlteryxConnection, AlteryxNode

# Color constants — single source of truth for both Python (graph builder) and JS (template)
COLOR_MAP: dict[str, str] = {
    "added": "#6ee7b7",
    "removed": "#fca5a5",
    "modified": "#fcd34d",
    "connection": "#93c5fd",
    "unchanged": "#e2e8f0",
}

BORDER_COLOR_MAP: dict[str, str] = {
    "added": "#059669",
    "removed": "#dc2626",
    "modified": "#b45309",
    "connection": "#1d4ed8",
    "unchanged": "#94a3b8",
}

LAYOUT_SCALE = 2000  # pixel scale factor for vis-network viewport

# ToolContainer is a visual-only grouping in Alteryx Designer — it has no data
# connections and adds noise to the diff graph.
CONTAINER_TYPE = "AlteryxGuiToolkit.ToolContainer.ToolContainer"


def build_digraph(
    result: DiffResult,
    all_connections: tuple[AlteryxConnection, ...],
    all_nodes: tuple[AlteryxNode, ...],
) -> nx.DiGraph[int]:
    """Build a directed graph from a DiffResult and the full node/connection sets.

    Args:
        result: The diff output containing added/removed/modified/edge_diffs.
        all_connections: Union of old and new workflow connections.
        all_nodes: Union of old and new workflow nodes.

    Returns:
        A nx.DiGraph where each node has ``label``, ``color``, ``status``,
        and ``title`` attributes.
    """
    added_ids: set[int] = {int(n.tool_id) for n in result.added_nodes}
    removed_ids: set[int] = {int(n.tool_id) for n in result.removed_nodes}
    modified_ids: set[int] = {int(nd.tool_id) for nd in result.modified_nodes}
    conn_changed_ids: set[int] = {int(ed.src_tool) for ed in result.edge_diffs} | {
        int(ed.dst_tool) for ed in result.edge_diffs
    }

    G: nx.DiGraph[int] = nx.DiGraph()

    for node in all_nodes:
        if node.tool_type == CONTAINER_TYPE:
            continue
        tool_id = int(node.tool_id)
        # Priority: added > removed > modified > connection > unchanged
        if tool_id in added_ids:
            status = "added"
        elif tool_id in removed_ids:
            status = "removed"
        elif tool_id in modified_ids:
            status = "modified"
        elif tool_id in conn_changed_ids:
            status = "connection"
        else:
            status = "unchanged"

        short_label = node.tool_type.split(".")[-1]
        G.add_node(
            tool_id,
            label=f"{short_label}\n({tool_id})",
            color={
                "background": COLOR_MAP[status],
                "border": BORDER_COLOR_MAP[status],
                "highlight": {
                    "background": COLOR_MAP[status],
                    "border": BORDER_COLOR_MAP[status],
                },
            },
            status=status,
            title=f"{node.tool_type} | {status}",
        )

    for conn in all_connections:
        src, dst = int(conn.src_tool), int(conn.dst_tool)
        if src in G and dst in G:
            G.add_edge(src, dst)

    return G


def hierarchical_positions(G: nx.DiGraph[int]) -> dict[int, tuple[float, float]]:
    """Compute multipartite (hierarchical) layout positions for a directed graph.

    Cycles are handled by iteratively removing back-edges until the graph is a DAG.
    Layer 0 nodes appear at smaller x than layer 1 nodes.

    Args:
        G: The directed graph produced by build_digraph().

    Returns:
        Mapping of integer tool_id -> (x, y) pixel coordinates scaled by
        LAYOUT_SCALE.
    """
    dag: nx.DiGraph[int] = G.copy()

    # Remove back-edges until the graph is a DAG
    while not nx.is_directed_acyclic_graph(dag):
        cycle = nx.find_cycle(dag)
        # cycle is a list of (u, v, ...) edge tuples; remove the last back-edge
        back_edge = cycle[-1][:2]
        dag.remove_edge(back_edge[0], back_edge[1])

    # Assign topological layer to each node
    for layer, nodes in enumerate(nx.topological_generations(dag)):
        for node in nodes:
            dag.nodes[node]["layer"] = layer

    # Compute multipartite layout (returns numpy arrays)
    raw_pos: dict[Any, Any] = nx.multipartite_layout(
        dag, subset_key="layer", align="vertical"
    )

    return {
        int(node): (float(coords[0]) * LAYOUT_SCALE, float(coords[1]) * LAYOUT_SCALE)
        for node, coords in raw_pos.items()
    }


def canvas_positions(
    nodes_old: tuple[AlteryxNode, ...],
    nodes_new: tuple[AlteryxNode, ...],
) -> dict[int, tuple[float, float]]:
    """Return raw Alteryx X/Y canvas coordinates keyed by integer tool_id.

    Old node positions are populated first; new node positions override them.
    This correctly handles added nodes (new only) and modified nodes (use new position).

    Args:
        nodes_old: Nodes from the baseline (old) workflow.
        nodes_new: Nodes from the changed (new) workflow.

    Returns:
        Mapping of integer tool_id -> (x, y) Alteryx canvas coordinates.
    """
    pos: dict[int, tuple[float, float]] = {}
    for node in nodes_old:
        pos[int(node.tool_id)] = (node.x, node.y)
    for node in nodes_new:
        pos[int(node.tool_id)] = (node.x, node.y)
    return pos


def load_vis_js() -> str:
    """Load the vendored vis-network UMD bundle as a string.

    Attempts importlib.resources first (works in installed/editable packages).
    Falls back to a filesystem read relative to this file's location for
    development environments where the package data is not yet on the path.

    Returns:
        The full vis-network.min.js source as a UTF-8 string.

    Raises:
        FileNotFoundError: If neither the package resource nor the filesystem
            fallback path can locate the file.
    """
    try:
        return (
            pkg_resources.files("alteryx_git_companion")
            .joinpath("static/vis-network.min.js")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, TypeError):
        # Fallback: read from filesystem during development
        import pathlib

        p = pathlib.Path(__file__).parent.parent / "static" / "vis-network.min.js"
        return p.read_text(encoding="utf-8")


def build_split_node_list(
    result: DiffResult,
    nodes_old: tuple[AlteryxNode, ...],
    nodes_new: tuple[AlteryxNode, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build two separate vis-network node lists for split view.

    Returns (old_vis_nodes, new_vis_nodes). Left graph contains real old nodes
    plus ghost placeholders for added nodes. Right graph contains real new nodes
    plus ghost placeholders for removed nodes. Ghost nodes use opacity:0.25 and
    borderDashes:[4,4].

    Args:
        result: The diff output containing added/removed/modified nodes.
        nodes_old: Nodes from the baseline (old) workflow.
        nodes_new: Nodes from the changed (new) workflow.

    Returns:
        A tuple of (old_vis_nodes, new_vis_nodes) where each is a list of
        vis-network node dicts ready for JSON serialization.
    """
    # Step 1 — Build ID sets
    added_ids: set[int] = {int(n.tool_id) for n in result.added_nodes}
    removed_ids: set[int] = {int(n.tool_id) for n in result.removed_nodes}
    modified_ids: set[int] = {int(nd.tool_id) for nd in result.modified_nodes}
    new_pos_lookup: dict[int, tuple[float, float]] = {
        int(n.tool_id): (n.x, n.y) for n in nodes_new
    }
    old_pos_lookup: dict[int, tuple[float, float]] = {
        int(n.tool_id): (n.x, n.y) for n in nodes_old
    }

    # Step 2 — Build left (old) node list
    old_vis_nodes: list[dict[str, Any]] = []
    for node in nodes_old:
        if node.tool_type == CONTAINER_TYPE:
            continue
        tool_id = int(node.tool_id)
        if tool_id in removed_ids:
            status = "removed"
        elif tool_id in modified_ids:
            status = "modified"
        else:
            status = "unchanged"
        short_label = node.tool_type.split(".")[-1]
        old_vis_nodes.append(
            {
                "id": tool_id,
                "label": short_label + "\n(" + str(tool_id) + ")",
                "x": node.x,
                "y": node.y,
                "fixed": False,
                "status": status,
                "color": {
                    "background": COLOR_MAP[status],
                    "border": BORDER_COLOR_MAP[status],
                    "highlight": {
                        "background": COLOR_MAP[status],
                        "border": BORDER_COLOR_MAP[status],
                    },
                },
                "title": node.tool_type + " | " + status,
            }
        )
    # Ghost nodes for added nodes (shown faintly on left/old graph)
    for n in result.added_nodes:
        if n.tool_type == CONTAINER_TYPE:
            continue
        tid = int(n.tool_id)
        pos = new_pos_lookup.get(tid, (0.0, 0.0))
        short_label = n.tool_type.split(".")[-1]
        old_vis_nodes.append(
            {
                "id": tid,
                "label": short_label + "\n(" + str(tid) + ")",
                "x": pos[0],
                "y": pos[1],
                "fixed": False,
                "status": "ghost_added",
                "opacity": 0.25,
                "borderDashes": [4, 4],
                "color": {"background": "#d1fae5", "border": "#6ee7b7"},
                "title": n.tool_type + " | added (in new workflow)",
            }
        )

    # Step 3 — Build right (new) node list
    new_vis_nodes: list[dict[str, Any]] = []
    for node in nodes_new:
        if node.tool_type == CONTAINER_TYPE:
            continue
        tool_id = int(node.tool_id)
        if tool_id in added_ids:
            status = "added"
        elif tool_id in modified_ids:
            status = "modified"
        else:
            status = "unchanged"
        short_label = node.tool_type.split(".")[-1]
        new_vis_nodes.append(
            {
                "id": tool_id,
                "label": short_label + "\n(" + str(tool_id) + ")",
                "x": node.x,
                "y": node.y,
                "fixed": False,
                "status": status,
                "color": {
                    "background": COLOR_MAP[status],
                    "border": BORDER_COLOR_MAP[status],
                    "highlight": {
                        "background": COLOR_MAP[status],
                        "border": BORDER_COLOR_MAP[status],
                    },
                },
                "title": node.tool_type + " | " + status,
            }
        )
    # Ghost nodes for removed nodes (shown faintly on right/new graph)
    for n in result.removed_nodes:
        if n.tool_type == CONTAINER_TYPE:
            continue
        tid = int(n.tool_id)
        pos = old_pos_lookup.get(tid, (0.0, 0.0))
        short_label = n.tool_type.split(".")[-1]
        new_vis_nodes.append(
            {
                "id": tid,
                "label": short_label + "\n(" + str(tid) + ")",
                "x": pos[0],
                "y": pos[1],
                "fixed": False,
                "status": "ghost_removed",
                "opacity": 0.25,
                "borderDashes": [4, 4],
                "color": {"background": "#fee2e2", "border": "#fca5a5"},
                "title": n.tool_type + " | removed (was in old workflow)",
            }
        )

    # Step 4 — Return (old_vis_nodes, new_vis_nodes)
    return old_vis_nodes, new_vis_nodes
