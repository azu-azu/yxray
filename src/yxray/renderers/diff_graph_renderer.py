# ruff: noqa: E501
"""Interactive vis-network graph HTML fragment renderer for diff output.

DiffGraphRenderer.render() produces a self-contained HTML fragment (not a full
document) that is embedded into the full report by HTMLRenderer via the
``{{ graph_html | safe }}`` template placeholder.

vis-network standalone UMD is inlined — zero CDN references.
Physics is disabled; positions are pre-computed in Python.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment

from yxray.models import DiffResult
from yxray.models.workflow import AlteryxConnection, AlteryxNode
from yxray.renderers._graph_builder import (
    _safe_json,
    build_digraph,
    build_split_node_list,
    canvas_positions,
    hierarchical_positions,
    load_vis_js,
)
from yxray.renderers._report_assets import CONTRAST_COLOR_JS
from yxray.renderers._templates import load_template

_GRAPH_FRAGMENT_TEMPLATE = load_template("diff_graph_fragment.html")


class DiffGraphRenderer:
    """Render a DiffResult as an interactive vis-network graph HTML fragment.

    Produces: <section id="graph-section"> containing:
        - Split View (default): two vis-network canvases side-by-side with
          synchronized pan/zoom and a center change panel
        - Overlay View: single merged graph with slide-in diff panel (existing behavior)
        - inline <style> for all UI elements
        - inline <script> with vis-network UMD embedded + graph logic

    Fragment is embedded by HTMLRenderer via ``{{ graph_html | safe }}``.
    vis-network standalone UMD is inlined — zero CDN references.
    Physics is disabled; positions are pre-computed in Python.
    """

    def render(
        self,
        result: DiffResult,
        all_connections: tuple[AlteryxConnection, ...],
        nodes_old: tuple[AlteryxNode, ...],
        nodes_new: tuple[AlteryxNode, ...],
        *,
        canvas_layout: bool = False,
    ) -> str:
        """Render a DiffResult as a self-contained HTML fragment with vis-network.

        Args:
            result: The diff output with added/removed/modified nodes and edge diffs.
            all_connections: Combined connections from both old and new workflows.
            nodes_old: Nodes from the baseline (old) workflow.
            nodes_new: Nodes from the changed (new) workflow.
            canvas_layout: If True, use raw Alteryx X/Y canvas coordinates instead
                of the hierarchical topological layout.

        Returns:
            An HTML fragment string (no <html>/<head>/<body> tags) containing
            a <section id="graph-section"> with the interactive vis-network graph.
        """
        all_nodes_tuple = self._merged_nodes(nodes_old, nodes_new)
        graph = build_digraph(result, all_connections, all_nodes_tuple)
        positions = self._positions(graph, nodes_old, nodes_new, canvas_layout)
        nodes_json = self._overlay_nodes(result, graph, positions)
        edges_json = self._overlay_edges(result, graph)
        old_vis_nodes, new_vis_nodes = build_split_node_list(
            result, nodes_old, nodes_new
        )

        return self._render_template(
            nodes_json=nodes_json,
            edges_json=edges_json,
            old_vis_nodes=old_vis_nodes,
            new_vis_nodes=new_vis_nodes,
        )

    def _merged_nodes(
        self,
        nodes_old: tuple[AlteryxNode, ...],
        nodes_new: tuple[AlteryxNode, ...],
    ) -> tuple[AlteryxNode, ...]:
        nodes_map: dict[int, AlteryxNode] = {}
        for n in nodes_old:
            nodes_map[int(n.tool_id)] = n
        for n in nodes_new:
            nodes_map[int(n.tool_id)] = n
        return tuple(nodes_map.values())

    def _positions(
        self,
        graph: Any,
        nodes_old: tuple[AlteryxNode, ...],
        nodes_new: tuple[AlteryxNode, ...],
        canvas_layout: bool,
    ) -> dict[int, tuple[float, float]]:
        if canvas_layout:
            return canvas_positions(nodes_old, nodes_new)
        canvas_y: dict[int, float] = {}
        for n in nodes_old:
            canvas_y[int(n.tool_id)] = n.y
        for n in nodes_new:
            canvas_y[int(n.tool_id)] = n.y
        return hierarchical_positions(graph, canvas_y=canvas_y)

    def _overlay_nodes(
        self,
        result: DiffResult,
        graph: Any,
        positions: dict[int, tuple[float, float]],
    ) -> list[dict[str, Any]]:
        field_counts: dict[int, int] = {
            int(nd.tool_id): len(nd.field_diffs) for nd in result.modified_nodes
        }

        nodes_json: list[dict[str, Any]] = []
        for node_id, (px, py) in positions.items():
            attrs = graph.nodes[node_id]
            label: str = attrs["label"]
            status: str = attrs["status"]
            title: str = attrs["title"]
            entry: dict[str, Any] = {
                "id": node_id,
                "label": label,
                "color": attrs["color"],
                "status": status,
                "title": title,
                "x": px,
                "y": py,
                "fixed": False,
            }
            nodes_json.append(entry)

        for entry in nodes_json:
            if entry["status"] == "modified":
                count = field_counts.get(int(entry["id"]), 0)
                entry["title"] = (
                    f"{entry['label']} | modified | {count} field(s) changed"
                )
        return nodes_json

    def _overlay_edges(
        self, result: DiffResult, graph: Any
    ) -> list[dict[str, Any]]:
        edge_removed_set = {
            (int(e.src_tool), int(e.dst_tool))
            for e in result.edge_diffs
            if e.change_type == "removed"
        }
        edge_added_set = {
            (int(e.src_tool), int(e.dst_tool))
            for e in result.edge_diffs
            if e.change_type == "added"
        }
        edges_json: list[dict[str, Any]] = []
        for src, dst in graph.edges():
            edge: dict[str, Any] = {"id": f"{src}-{dst}", "from": src, "to": dst}
            if (src, dst) in edge_removed_set:
                edge["color"] = {"color": "#fca5a5", "highlight": "#dc2626", "hover": "#dc2626"}
                edge["width"] = 2.5
                edge["status"] = "removed"
            elif (src, dst) in edge_added_set:
                edge["color"] = {"color": "#6ee7b7", "highlight": "#059669", "hover": "#059669"}
                edge["width"] = 2.5
                edge["status"] = "added"
            else:
                edge["status"] = "unchanged"
            edges_json.append(edge)
        return edges_json

    def _render_template(
        self,
        *,
        nodes_json: list[dict[str, Any]],
        edges_json: list[dict[str, Any]],
        old_vis_nodes: list[dict[str, Any]],
        new_vis_nodes: list[dict[str, Any]],
    ) -> str:
        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_GRAPH_FRAGMENT_TEMPLATE)
        return template.render(
            nodes_json=_safe_json(nodes_json),
            edges_json=_safe_json(edges_json),
            nodes_old_json=_safe_json(old_vis_nodes),
            nodes_new_json=_safe_json(new_vis_nodes),
            vis_js=load_vis_js(),
            contrast_color_js=CONTRAST_COLOR_JS,
        )
