# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow.

SingleGraphRenderer.render(doc) produces a full standalone HTML document
(not a fragment) containing an interactive vis-network graph.

vis-network UMD is inlined via load_vis_js() — zero CDN references.
Physics is disabled; nodes are placed at their Alteryx canvas coordinates.
Same-type BFS clusters (purple) and ToolContainer dashed borders are drawn.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
import pathlib
from typing import Any

from jinja2 import Environment

from yxray.explain import explain as _explain_workflow
from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.renderers._graph_builder import _safe_json, load_vis_js
from yxray.renderers._report_assets import CONTRAST_COLOR_JS, STEP_DETAIL_JS
from yxray.renderers._templates import load_template
from yxray.scaffold import node_code_snippets
from yxray.topology import compute_node_layer


def _load_single_graph_js() -> str:
    """Load the single-graph JavaScript bundle from the static package directory."""
    try:
        return (
            pkg_resources.files("yxray")
            .joinpath("static/single_graph.js")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, TypeError):
        p = pathlib.Path(__file__).parent.parent / "static" / "single_graph.js"
        return p.read_text(encoding="utf-8")


_HTML_TEMPLATE = load_template("single_graph.html")


class SingleGraphRenderer:
    """Render a single WorkflowDoc as a standalone vis-network HTML file.

    Returns a full HTML document (not a fragment).
    vis-network UMD is inlined — zero CDN references.
    """

    def render(
        self,
        doc: WorkflowDoc,
        *,
        workflow_steps: list[Any] | None = None,
        key_insights: list[Any] | None = None,
        manual_cluster_config: dict[str, Any] | None = None,
    ) -> str:
        """WorkflowDoc → standalone HTML string.

        Args:
            doc: The parsed workflow document.
            workflow_steps: Optional list of WorkflowStep objects. When provided,
                a collapsible Summary panel is shown.
            key_insights: Optional list of KeyInsight objects shown as an
                at-a-glance summary at the top of the Summary panel.
            manual_cluster_config: Optional validated manual cluster config to
                embed into the report.
        """
        nodes_list, edges_list, config_map, containers_list = self._build_graph_data(
            doc
        )
        self._add_python_hints(doc, config_map)

        # Sort containers by canvas position (x, y) to match the left-to-right visual flow.
        if containers_list:
            containers_list = sorted(containers_list, key=lambda c: (c["x"], c["y"]))

        return self._render_template(
            doc=doc,
            graph_data_json=self._graph_data_json(
                doc,
                nodes_list,
                edges_list,
                config_map,
                containers_list,
                manual_cluster_config,
            ),
            workflow_steps=self._workflow_steps_to_dicts(workflow_steps),
            key_insights=self._key_insights_to_dicts(key_insights),
            containers_for_panel=self._containers_for_panel(containers_list),
        )

    def _add_python_hints(self, doc: WorkflowDoc, config_map: dict[str, Any]) -> None:
        detail_snippets = node_code_snippets(doc)
        for step in _explain_workflow(doc):
            entry = config_map.get(str(step.tool_id))
            if entry is not None:
                hint = detail_snippets.get(step.tool_id, step.python_hint)
                entry["python_hint"] = self._format_hint(step.tool_id, hint)
                entry["supported"] = step.supported

    @staticmethod
    def _format_hint(tool_id: int, hint: str) -> str:
        """Panel-only hint format: prepend a '# ToolID <id>' header."""
        return "\n".join([f"# ToolID {tool_id}", hint])

    def _workflow_steps_to_dicts(
        self, workflow_steps: list[Any] | None
    ) -> list[Any] | None:
        if not workflow_steps:
            return None
        return [
            s.to_dict(include_change=False) if hasattr(s, "to_dict") else s
            for s in workflow_steps
        ]

    def _key_insights_to_dicts(
        self, key_insights: list[Any] | None
    ) -> list[Any] | None:
        if not key_insights:
            return None
        return [i.to_dict() if hasattr(i, "to_dict") else i for i in key_insights]

    def _graph_data_json(
        self,
        doc: WorkflowDoc,
        nodes_list: list[dict[str, Any]],
        edges_list: list[dict[str, Any]],
        config_map: dict[str, Any],
        containers_list: list[dict[str, Any]],
        manual_cluster_config: dict[str, Any] | None,
    ) -> str:
        return _safe_json(
            {
                "nodes": nodes_list,
                "edges": edges_list,
                "config_map": config_map,
                "containers": containers_list,
                "node_layer": compute_node_layer(doc),
                "manual_clusters": manual_cluster_config,
            },
            ensure_ascii=False,
        )

    def _containers_for_panel(
        self, containers_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]] | None:
        return [
            {
                "label": c["label"],
                "fill_color": c.get("fillColor"),
                "tool_id": c.get("tool_id"),
            }
            for c in containers_list
        ] or None

    def _render_template(
        self,
        *,
        doc: WorkflowDoc,
        graph_data_json: str,
        workflow_steps: list[Any] | None,
        key_insights: list[Any] | None,
        containers_for_panel: list[dict[str, Any]] | None,
    ) -> str:
        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_HTML_TEMPLATE)
        data_node_count = sum(
            1 for n in doc.nodes if "ToolContainer" not in n.tool_type
        )
        return template.render(
            title=pathlib.Path(doc.filepath).name,
            node_count=data_node_count,
            edge_count=len(doc.connections),
            graph_data_json=graph_data_json,
            vis_js=load_vis_js(),
            single_graph_js=_load_single_graph_js(),
            step_detail_js=STEP_DETAIL_JS,
            contrast_color_js=CONTRAST_COLOR_JS,
            workflow_steps=workflow_steps,
            key_insights=key_insights,
            containers_for_panel=containers_for_panel,
        )

    def _build_graph_data(
        self, doc: WorkflowDoc
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]
    ]:
        data_nodes = [n for n in doc.nodes if "ToolContainer" not in n.tool_type]
        data_node_ids = {int(n.tool_id) for n in data_nodes}

        nodes_json: list[dict[str, Any]] = [
            self._vis_node(int(node.tool_id), node) for node in data_nodes
        ]

        edges_json: list[dict[str, Any]] = [
            {"id": i, "from": int(c.src_tool), "to": int(c.dst_tool)}
            for i, c in enumerate(doc.connections)
            if int(c.src_tool) in data_node_ids and int(c.dst_tool) in data_node_ids
        ]

        config_map: dict[str, Any] = {
            str(int(node.tool_id)): {
                "label": f"{node.tool_type.split('.')[-1]} (ID: {int(node.tool_id)})",
                "tool_type": node.tool_type.split(".")[-1],
                "containerId": node.container_id,
                "config": self._clean_config(node),
                "raw_xml": node.raw_xml,
            }
            for node in data_nodes
        }

        containers_json: list[dict[str, Any]] = [
            {
                "x": node.x,
                "y": node.y,
                "w": node.width,
                "h": node.height,
                "label": self._container_label(node),
                "fillColor": self._container_fill_color(node),
                "tool_id": int(node.tool_id),
            }
            for node in doc.nodes
            if "ToolContainer" in node.tool_type and node.width > 0 and node.height > 0
        ]

        return nodes_json, edges_json, config_map, containers_json

    def _container_fill_color(self, node: AlteryxNode) -> str | None:
        """Return '#rrggbb' extracted from container config, or None if absent/white.

        Alteryx stores container color inside the <Style> element's attributes:
          <Style FillColor="xxx" TextColor="xxx" BorderColor="xxx" .../>
        parsed as config["Style"]["@FillColor"].
        Value may be hex (#RRGGBB, AARRGGBB) or a decimal ARGB integer.

        Fallback: <Tint> (Qt ARGB32 int), <FillColor> hex string.
        """
        config = node.config

        def _hex_or_int_to_rgb(raw: str) -> str | None:
            raw = raw.strip().lstrip("#")
            if not raw:
                return None
            # 8-char hex AARRGGBB → take RGB part
            if len(raw) == 8 and all(c in "0123456789abcdefABCDEF" for c in raw):
                return f"#{raw[2:8].lower()}"
            # 6-char hex RRGGBB
            if len(raw) == 6 and all(c in "0123456789abcdefABCDEF" for c in raw):
                return f"#{raw.lower()}"
            # Decimal integer → ARGB32
            try:
                val = int(raw)
                if val > 0:
                    r = (val >> 16) & 0xFF
                    g = (val >> 8) & 0xFF
                    b = val & 0xFF
                    return f"#{r:02x}{g:02x}{b:02x}"
            except ValueError:
                pass
            return None

        # Primary: Style/@FillColor attribute
        style_entry = config.get("Style")
        if isinstance(style_entry, dict):
            fill_attr = style_entry.get("@FillColor", "")
            if fill_attr:
                result = _hex_or_int_to_rgb(fill_attr)
                if result:
                    return result
            # Fallback: Style as plain integer index (old format)
            text = style_entry.get("#text", "").strip()
            try:
                style_int = int(text)
                if style_int > 9:
                    return _hex_or_int_to_rgb(text)
                _STYLE_COLORS: dict[int, str] = {
                    1: "#dbeafe",
                    2: "#dcfce7",
                    3: "#fef9c3",
                    4: "#ffedd5",
                    5: "#fce7f3",
                    6: "#ede9fe",
                    7: "#d1fae5",
                    8: "#e0f2fe",
                    9: "#fee2e2",
                }
                return _STYLE_COLORS.get(style_int)
            except ValueError:
                pass

        # Tint: Qt ARGB32 packed integer
        tint_entry = config.get("Tint")
        if tint_entry:
            raw = (
                tint_entry.get("#text", "")
                if isinstance(tint_entry, dict)
                else str(tint_entry)
            )
            result = _hex_or_int_to_rgb(raw)
            if result:
                return result

        # FillColor: top-level hex string (some versions)
        fill_entry = config.get("FillColor") or config.get("fillColor")
        if fill_entry:
            raw = (
                fill_entry.get("#text", "")
                if isinstance(fill_entry, dict)
                else str(fill_entry)
            )
            result = _hex_or_int_to_rgb(raw)
            if result:
                return result

        return None

    def _container_label(self, node: AlteryxNode) -> str:
        caption_entry = node.config.get("Caption", {})
        if isinstance(caption_entry, dict):
            text = caption_entry.get("#text", "")
        else:
            text = str(caption_entry) if caption_entry else ""
        return text or f"Container ({int(node.tool_id)})"

    def _vis_node(self, node_id: int, node: AlteryxNode) -> dict[str, Any]:
        short_type = node.tool_type.split(".")[-1]
        result: dict[str, Any] = {
            "id": node_id,
            "label": f"{short_type}\n({node_id})",
            "title": node.tool_type,
            "containerId": node.container_id,
            "x": node.x,
            "y": node.y,
        }
        subtitle = self._node_subtitle(node)
        if subtitle:
            result["subtitle"] = subtitle
        return result

    def _node_subtitle(self, node: AlteryxNode) -> str | None:
        """Return the File path from config for input/output nodes, else None."""
        file_entry = node.config.get("File")
        if file_entry is None:
            return None
        raw = (
            file_entry.get("#text", "")
            if isinstance(file_entry, dict)
            else str(file_entry)
        )
        return raw.strip() or None

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
