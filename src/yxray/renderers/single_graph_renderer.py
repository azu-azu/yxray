# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow.

SingleGraphRenderer.render(doc) produces a full standalone HTML document
(not a fragment) containing an interactive vis-network graph.

vis-network UMD is inlined via load_vis_js() — zero CDN references.
Physics is disabled; nodes are placed at their Alteryx canvas coordinates.
Same-type BFS clusters (purple) and ToolContainer dashed borders are drawn.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import importlib.resources as pkg_resources

from jinja2 import Environment

from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.renderers._graph_builder import load_vis_js


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


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-2: #334155;
      --border: #334155;
      --border-subtle: #1e293b;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --node-bg: #1d4ed8;
      --node-border: #3b82f6;
      --node-font: #e2e8f0;
      --node-hover: #2563eb;
      --node-select: #1e40af;
      --edge-color: #475569;
    }
    html.light {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-2: #f1f5f9;
      --border: #e2e8f0;
      --border-subtle: #f1f5f9;
      --text: #0f172a;
      --text-muted: #64748b;
      --accent: #0284c7;
      --node-bg: #93c5fd;
      --node-border: #1d4ed8;
      --node-font: #1e293b;
      --node-hover: #bfdbfe;
      --node-select: #60a5fa;
      --edge-color: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      overflow: hidden;
      display: flex; flex-direction: column; height: 100vh;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
    }
    .header-title { font-size: 15px; font-weight: 600; color: var(--text); }
    .header-meta { font-size: 12px; color: var(--text-muted); }
    .header-hints { font-size: 11px; color: var(--text-muted); margin-top: 3px; display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
    .hint-item { opacity: 0.7; }
    .hint-sep { opacity: 0.35; }
    .header-right { display: flex; align-items: center; gap: 10px; }
    .ctrl-btn {
      padding: 5px 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      background: var(--surface-2);
      color: var(--text);
      transition: background 0.15s;
    }
    .ctrl-btn:hover { background: var(--border); }
    .search-wrap { position: relative; display: flex; align-items: center; }
    .search-input {
      width: 200px; padding: 5px 28px 5px 10px;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--surface-2); color: var(--text);
      font-size: 12px; outline: none;
      transition: border-color 0.15s, width 0.2s;
    }
    .search-input:focus { border-color: var(--accent); width: 260px; }
    .search-input::placeholder { color: var(--text-muted); }
    .search-clear {
      position: absolute; right: 6px;
      background: none; border: none;
      color: var(--text-muted); cursor: pointer;
      font-size: 14px; line-height: 1; display: none; padding: 0;
    }
    .search-clear:hover { color: var(--text); }
    header { flex-shrink: 0; }
    #graph-wrapper {
      flex: 1;
      background: var(--bg);
      overflow: hidden;
    }
    #graph-canvas { width: 100%; height: 100%; }
    #config-panel {
      position: fixed;
      top: 0; right: -420px;
      width: 400px; height: 100%;
      background: var(--surface);
      border-left: 1px solid var(--border);
      box-shadow: -2px 0 12px rgba(0,0,0,0.2);
      overflow-y: auto;
      transition: right 0.2s ease;
      z-index: 1000;
      padding: 20px;
      border-radius: 8px 0 0 8px;
    }
    #config-panel.open { right: 0; }
    #panel-overlay {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 999;
    }
    #config-panel.open ~ #panel-overlay { display: block; }
    .panel-title {
      font-size: 14px; font-weight: 600;
      margin-bottom: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
    }
    .panel-close {
      float: right; cursor: pointer;
      color: var(--text-muted); font-size: 18px; line-height: 1;
      background: none; border: none;
    }
    .panel-close:hover { color: var(--text); }
    .config-row { margin: 8px 0; }
    .config-key {
      font-size: 11px; font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.8px;
      margin-bottom: 3px;
    }
    .config-val {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px; color: var(--text);
      white-space: pre-wrap; word-break: break-all;
      background: var(--surface-2); padding: 4px 8px; border-radius: 4px;
    }
    .cluster-member-header {
      font-size: 12px; font-weight: 600; color: var(--accent);
      margin: 10px 0 4px; padding-top: 8px;
      border-top: 1px solid var(--border-subtle);
    }
    /* Memo feature */
    #memo-modal-overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.4); z-index: 1999;
    }
    #memo-modal-overlay.open { display: block; }
    #memo-modal {
      display: none; position: fixed;
      top: 50%; left: 50%; transform: translate(-50%,-50%);
      z-index: 2000; width: 300px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 16px 18px 14px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    #memo-modal.open { display: block; }
    .memo-modal-title {
      font-size: 11px; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 10px;
    }
    #memo-textarea {
      width: 100%; min-height: 80px; padding: 8px 10px; display: block;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--surface-2); color: var(--text);
      font-size: 13px; font-family: system-ui,-apple-system,sans-serif;
      resize: vertical; outline: none;
    }
    #memo-textarea:focus { border-color: var(--accent); }
    .memo-modal-actions {
      display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end;
    }
    #connect-mode-hint {
      display: none; position: fixed; top: 65px; left: 50%;
      transform: translateX(-50%); z-index: 1500; pointer-events: none;
      background: #ca8a04; color: #fff; padding: 6px 18px;
      border-radius: 6px; font-size: 12px; font-weight: 500;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="header-title">{{ title }}</div>
      <div class="header-meta">{{ node_count }} nodes &middot; {{ edge_count }} connections</div>
      <div class="header-hints">
        <span class="hint-item">&#128203; 空白をダブルクリック &rarr; メモ追加</span>
        <span class="hint-sep">&middot;</span>
        <span class="hint-item">&#128308; 赤いクラスタをダブルクリック &rarr; 展開</span>
        <span class="hint-sep">&middot;</span>
        <span class="hint-item">&#128203; メモをダブルクリック &rarr; 編集</span>
      </div>
    </div>
    <div class="header-right">
      <div class="search-wrap">
        <input type="text" id="search-input" class="search-input" placeholder="Search node…" autocomplete="off" spellcheck="false" />
        <button class="search-clear" id="search-clear-btn" aria-label="Clear">&times;</button>
      </div>
      <button class="ctrl-btn" id="add-memo-btn">+ Memo</button>
      <button class="ctrl-btn" id="fit-btn">Fit to Screen</button>
      <button class="ctrl-btn" id="fullscreen-btn">Fullscreen</button>
      <button class="ctrl-btn" id="theme-btn">Light Mode</button>
    </div>
  </header>
  <div id="graph-wrapper">
    <div id="graph-canvas"></div>
  </div>
  <div id="config-panel">
    <div class="panel-title">
      <button class="panel-close" id="panel-close-btn">&times;</button>
      <span id="panel-title-text"></span>
    </div>
    <div id="panel-body"></div>
  </div>
  <div id="panel-overlay"></div>
  <div id="memo-modal-overlay"></div>
  <div id="memo-modal">
    <div class="memo-modal-title" id="memo-modal-title">New Memo</div>
    <textarea id="memo-textarea" placeholder="Enter memo text…" rows="4"></textarea>
    <div class="memo-modal-actions">
      <button class="ctrl-btn" id="memo-delete-btn" style="display:none;color:#f87171;">Delete</button>
      <button class="ctrl-btn" id="memo-cancel-btn">Cancel</button>
      <button class="ctrl-btn" id="memo-save-btn" style="background:var(--accent);color:#fff;border-color:var(--accent);">Save</button>
    </div>
  </div>
  <div id="connect-mode-hint">Click a node to connect &mdash; Esc to cancel</div>
  <script>{{ vis_js | safe }}</script>
  <script id="yxray-data" type="application/json">{{ graph_data_json | safe }}</script>
  <script>
{{ single_graph_js | safe }}
  </script>
</body>
</html>
"""


class SingleGraphRenderer:
    """Render a single WorkflowDoc as a standalone vis-network HTML file.

    Returns a full HTML document (not a fragment).
    vis-network UMD is inlined — zero CDN references.
    """

    def render(self, doc: WorkflowDoc) -> str:
        """WorkflowDoc → standalone HTML string."""
        nodes_list, edges_list, config_map, containers_list = self._build_graph_data(doc)
        vis_js = load_vis_js()
        single_graph_js = _load_single_graph_js()
        title = pathlib.Path(doc.filepath).name

        graph_data_json = json.dumps(
            {
                "nodes": nodes_list,
                "edges": edges_list,
                "config_map": config_map,
                "containers": containers_list,
            },
            ensure_ascii=False,
        )

        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_HTML_TEMPLATE)
        data_node_count = sum(1 for n in doc.nodes if "ToolContainer" not in n.tool_type)
        return template.render(
            title=title,
            node_count=data_node_count,
            edge_count=len(doc.connections),
            graph_data_json=graph_data_json,
            vis_js=vis_js,
            single_graph_js=single_graph_js,
        )

    def _build_graph_data(
        self, doc: WorkflowDoc
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
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
                "config": self._clean_config(node),
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
                    1: "#dbeafe", 2: "#dcfce7", 3: "#fef9c3",
                    4: "#ffedd5", 5: "#fce7f3", 6: "#ede9fe",
                    7: "#d1fae5", 8: "#e0f2fe", 9: "#fee2e2",
                }
                return _STYLE_COLORS.get(style_int)
            except ValueError:
                pass

        # Tint: Qt ARGB32 packed integer
        tint_entry = config.get("Tint")
        if tint_entry:
            raw = tint_entry.get("#text", "") if isinstance(tint_entry, dict) else str(tint_entry)
            result = _hex_or_int_to_rgb(raw)
            if result:
                return result

        # FillColor: top-level hex string (some versions)
        fill_entry = config.get("FillColor") or config.get("fillColor")
        if fill_entry:
            raw = fill_entry.get("#text", "") if isinstance(fill_entry, dict) else str(fill_entry)
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
        raw = file_entry.get("#text", "") if isinstance(file_entry, dict) else str(file_entry)
        return raw.strip() or None

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
