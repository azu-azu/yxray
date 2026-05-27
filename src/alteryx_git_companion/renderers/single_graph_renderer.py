# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow.

SingleGraphRenderer.render(doc) produces a full standalone HTML document
(not a fragment) containing an interactive vis-network graph.

vis-network UMD is inlined via load_vis_js() — zero CDN references.
Physics is disabled; positions are computed via hierarchical_positions().
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import networkx as nx
from jinja2 import Environment

from alteryx_git_companion.models.workflow import AlteryxNode, WorkflowDoc
from alteryx_git_companion.renderers._graph_builder import (
    hierarchical_positions,
    load_vis_js,
)

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
      --edge-color: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      flex-shrink: 0;
    }
    .header-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
    }
    .header-meta {
      font-size: 12px;
      color: var(--text-muted);
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }
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
    main {
      flex: 1;
      display: flex;
      min-height: 0;
    }
    #graph-container {
      flex: 1;
      background: var(--bg);
    }
    /* Slide-in config panel */
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
      float: right;
      cursor: pointer;
      color: var(--text-muted);
      font-size: 18px;
      line-height: 1;
      background: none;
      border: none;
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
      font-size: 12px;
      color: var(--text);
      white-space: pre-wrap;
      word-break: break-all;
      background: var(--surface-2);
      padding: 4px 8px;
      border-radius: 4px;
    }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="header-title">{{ title }}</div>
      <div class="header-meta">{{ node_count }} nodes &middot; {{ edge_count }} connections</div>
    </div>
    <div class="header-right">
      <button class="ctrl-btn" id="fit-btn">Fit to Screen</button>
      <button class="ctrl-btn" id="fullscreen-btn">Fullscreen</button>
      <button class="ctrl-btn" id="theme-btn">Light Mode</button>
    </div>
  </header>
  <main>
    <div id="graph-container"></div>
  </main>
  <div id="config-panel">
    <div class="panel-title">
      <button class="panel-close" id="panel-close-btn">&times;</button>
      <span id="panel-title-text"></span>
    </div>
    <div id="panel-body"></div>
  </div>
  <div id="panel-overlay"></div>
  <script>
(function() {
{{ vis_js | safe }}

var NODES_DATA = {{ nodes_json | safe }};
var EDGES_DATA = {{ edges_json | safe }};
var CONFIG_MAP = {{ config_map_json | safe }};

// ── vis-network setup ─────────────────────────────────────────────────────
var nodesDataset = new vis.DataSet(NODES_DATA);
var edgesDataset = new vis.DataSet(EDGES_DATA);

var isDark = true;

function nodeColors() {
  return isDark
    ? {background: '#1d4ed8', border: '#3b82f6', fontColor: '#e2e8f0',
       hoverBg: '#2563eb', selBg: '#1e40af'}
    : {background: '#93c5fd', border: '#1d4ed8', fontColor: '#1e293b',
       hoverBg: '#bfdbfe', selBg: '#60a5fa'};
}

function applyColors() {
  var c = nodeColors();
  nodesDataset.update(NODES_DATA.map(function(n) {
    return {
      id: n.id,
      color: {
        background: c.background,
        border: c.border,
        highlight: {background: c.selBg, border: c.border},
        hover: {background: c.hoverBg, border: c.border}
      },
      font: {color: c.fontColor}
    };
  }));
}

var options = {
  physics: {enabled: false},
  nodes: {
    shape: 'box',
    borderWidth: 1,
    borderWidthSelected: 2,
    margin: {top: 8, right: 12, bottom: 8, left: 12},
    font: {size: 13, face: 'system-ui,-apple-system,sans-serif'},
    shapeProperties: {borderRadius: 6}
  },
  edges: {
    arrows: {to: {enabled: true, scaleFactor: 0.7, type: 'arrow'}},
    smooth: {enabled: true, type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.4},
    color: {color: '#475569', highlight: '#94a3b8', hover: '#94a3b8'},
    width: 1.5, hoverWidth: 2.5, selectionWidth: 2.5
  },
  interaction: {zoomView: true, dragView: true, hover: true, tooltipDelay: 150}
};

var container = document.getElementById('graph-container');
var network = new vis.Network(container, {nodes: nodesDataset, edges: edgesDataset}, options);
applyColors();
network.fit();

// ── Config panel ──────────────────────────────────────────────────────────
function openPanel(nodeId) {
  var entry = CONFIG_MAP[nodeId];
  if (!entry) return;
  document.getElementById('panel-title-text').textContent = entry.label + ' (ID: ' + nodeId + ')';
  var body = document.getElementById('panel-body');
  body.innerHTML = '';
  var keys = Object.keys(entry.config);
  if (keys.length === 0) {
    var empty = document.createElement('div');
    empty.style.color = 'var(--text-muted)';
    empty.style.fontSize = '13px';
    empty.textContent = 'No configuration data.';
    body.appendChild(empty);
  } else {
    keys.forEach(function(k) {
      var row = document.createElement('div');
      row.className = 'config-row';
      var keyEl = document.createElement('div');
      keyEl.className = 'config-key';
      keyEl.textContent = k;
      var valEl = document.createElement('div');
      valEl.className = 'config-val';
      var v = entry.config[k];
      valEl.textContent = (typeof v === 'object') ? JSON.stringify(v, null, 2) : String(v);
      row.appendChild(keyEl);
      row.appendChild(valEl);
      body.appendChild(row);
    });
  }
  document.getElementById('config-panel').classList.add('open');
}

function closePanel() {
  document.getElementById('config-panel').classList.remove('open');
}

network.on('click', function(params) {
  if (params.nodes.length === 0) { closePanel(); return; }
  openPanel(params.nodes[0]);
});

document.getElementById('panel-close-btn').addEventListener('click', closePanel);
document.getElementById('panel-overlay').addEventListener('click', closePanel);
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closePanel(); });

// ── Controls ──────────────────────────────────────────────────────────────
document.getElementById('fit-btn').addEventListener('click', function() {
  network.fit({animation: true});
});

document.getElementById('fullscreen-btn').addEventListener('click', function() {
  var el = document.documentElement;
  if (!document.fullscreenElement) {
    el.requestFullscreen().catch(function() {});
    this.textContent = 'Exit Fullscreen';
  } else {
    document.exitFullscreen();
    this.textContent = 'Fullscreen';
  }
});
document.addEventListener('fullscreenchange', function() {
  if (!document.fullscreenElement) {
    var btn = document.getElementById('fullscreen-btn');
    if (btn) btn.textContent = 'Fullscreen';
    setTimeout(function() { network.fit({animation: false}); }, 50);
  }
});

// ── Theme toggle ──────────────────────────────────────────────────────────
var savedTheme = localStorage.getItem('yxray-theme') || 'dark';
function applyTheme(theme) {
  isDark = (theme === 'dark');
  if (isDark) {
    document.documentElement.classList.remove('light');
  } else {
    document.documentElement.classList.add('light');
  }
  document.getElementById('theme-btn').textContent = isDark ? 'Light Mode' : 'Dark Mode';
  var edgeColor = isDark ? '#475569' : '#94a3b8';
  edgesDataset.update(EDGES_DATA.map(function(e) {
    return {id: e.id, color: {color: edgeColor, highlight: edgeColor, hover: edgeColor}};
  }));
  applyColors();
}
document.getElementById('theme-btn').addEventListener('click', function() {
  var next = isDark ? 'light' : 'dark';
  localStorage.setItem('yxray-theme', next);
  applyTheme(next);
});
applyTheme(savedTheme);

})();
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
        nodes_json, edges_json, config_map = self._build_graph_data(doc)
        vis_js = load_vis_js()
        title = pathlib.Path(doc.filepath).name

        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_HTML_TEMPLATE)
        return template.render(
            title=title,
            node_count=len(doc.nodes),
            edge_count=len(doc.connections),
            nodes_json=json.dumps(nodes_json),
            edges_json=json.dumps(edges_json),
            config_map_json=json.dumps(config_map),
            vis_js=vis_js,
        )

    def _build_graph_data(
        self, doc: WorkflowDoc
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        # Build NetworkX DiGraph for hierarchical layout
        G: nx.DiGraph[int] = nx.DiGraph()
        for node in doc.nodes:
            G.add_node(int(node.tool_id))
        for conn in doc.connections:
            G.add_edge(int(conn.src_tool), int(conn.dst_tool))

        positions = hierarchical_positions(G) if G.nodes else {}

        node_map = {int(n.tool_id): n for n in doc.nodes}

        nodes_json: list[dict[str, Any]] = []
        positioned: set[int] = set(positions)

        for node_id, (px, py) in positions.items():
            node = node_map[node_id]
            nodes_json.append(self._vis_node(node_id, node, px, py))

        # Isolated nodes not included in positions
        for node in doc.nodes:
            nid = int(node.tool_id)
            if nid not in positioned:
                nodes_json.append(self._vis_node(nid, node, 0.0, 0.0))

        edges_json: list[dict[str, Any]] = [
            {
                "id": f"{int(c.src_tool)}-{int(c.dst_tool)}",
                "from": int(c.src_tool),
                "to": int(c.dst_tool),
            }
            for c in doc.connections
        ]

        # Config map: node_id (str) → {label, config} for panel display
        config_map: dict[str, Any] = {}
        for node in doc.nodes:
            nid = int(node.tool_id)
            short_type = node.tool_type.split(".")[-1]
            config_map[str(nid)] = {
                "label": f"{short_type} (ID: {nid})",
                "config": self._clean_config(node),
            }

        return nodes_json, edges_json, config_map

    def _vis_node(
        self, node_id: int, node: AlteryxNode, x: float, y: float
    ) -> dict[str, Any]:
        short_type = node.tool_type.split(".")[-1]
        return {
            "id": node_id,
            "label": f"{short_type}\n({node_id})",
            "title": node.tool_type,
            "x": x,
            "y": y,
            "fixed": False,
        }

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
