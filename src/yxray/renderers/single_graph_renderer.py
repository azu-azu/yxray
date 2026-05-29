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

from jinja2 import Environment

from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.renderers._graph_builder import load_vis_js

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
    #graph-wrapper {
      width: 100%;
      height: calc(100vh - 57px);
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
  <script>
var NODES_DATA = {{ nodes_json | safe }};
var EDGES_DATA = {{ edges_json | safe }};
var CONFIG_MAP = {{ config_map_json | safe }};
var CONTAINERS_DATA = {{ containers_json | safe }};

// ── vis-network setup ─────────────────────────────────────────────────────
var network = null;
var nodesDataset = null;
var edgesDataset = null;

// ── Clustering constants ──────────────────────────────────────────────────
var MIN_CLUSTER_SIZE = 2;  // minimum nodes to form a type-based cluster
var BOX_PAD_X        = 72; // horizontal padding from node center (expanded cluster box)
var BOX_PAD_Y        = 36; // vertical padding from node center
var BOX_RADIUS       = 14; // corner radius of the rounded rectangle

// ── Cluster color palette ─────────────────────────────────────────────────
// type = same-type BFS cluster (purple); container = ToolContainer group (red).
var CLUSTER_STYLE = {
  type: {
    normal: {background:'#4c1d95', border:'#7c3aed',
             highlight:{background:'#5b21b6', border:'#7c3aed'},
             hover:    {background:'#5b21b6', border:'#7c3aed'}},
    dim:    {background:'#2e1065', border:'#4c1d95'},
    matchBg: '#5b21b6',
    stroke: '#7c3aed', fill: 'rgba(109,40,217,0.07)', label: '#a78bfa',
  },
  container: {
    normal: {background:'#7f1d1d', border:'#ef4444',
             highlight:{background:'#991b1b', border:'#ef4444'},
             hover:    {background:'#991b1b', border:'#ef4444'}},
    dim:    {background:'#450a0a', border:'#7f1d1d'},
    matchBg: '#991b1b',
    stroke: '#ef4444', fill: 'rgba(239,68,68,0.07)', label: '#fca5a5',
  },
};

// ── Cluster state ─────────────────────────────────────────────────────────
var clusterMap = {};       // { 'cluster:N' | 'container:N': { memberIds, toolType, bridgeEdgeIds, isContainer } }
var expandedGroups = {};   // nodeId -> groupKey  (nodes that were expanded from a cluster)
var groupMembers = {};     // groupKey -> { memberIds, toolType, isContainer, containerNodeId }
var clusterCounter = 0;
var clusteredContainerIdx = {}; // CONTAINERS_DATA index -> true, for containers that formed a cluster node

// ── Memo state ────────────────────────────────────────────────────────────
var memoCounter = 0;
var memoData = {};   // 'memo:N' -> {text, x, y}
var memoEdges = {};  // edgeId  -> {from, to}
var _memoEditTarget = null;  // memoId being edited, or null = new memo
var _memoPendingPos = null;  // {x,y} for new memo placement
var _connectMode = false;    // true while waiting for user to click a target node
var _connectSourceId = null; // memo ID initiating the connection
var MEMO_STORAGE_KEY = 'yxray-memos-' + (document.title || 'default');
var _memoHandles = {};   // memoId -> {x,y} bottom-right corner in canvas coords (updated each afterDrawing)
var _resizeState = null; // {memoId, startDomX, startDomY, startW, startH} while drag-resizing

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
    smooth: {enabled: true, type: 'dynamic'},
    color: {color: '#475569', highlight: '#94a3b8', hover: '#94a3b8'},
    width: 1.5, hoverWidth: 2.5, selectionWidth: 2.5
  },
  interaction: {zoomView: true, dragView: true, hover: true, tooltipDelay: 150}
};

// ── Centroid helper ───────────────────────────────────────────────────────
// Returns the average {x, y} of a list of node IDs, looking up positions
// from NODES_DATA. Used to place cluster nodes near their members.
function centroid(nodeIds) {
  var sx = 0, sy = 0, n = 0;
  var lookup = {};
  NODES_DATA.forEach(function(nd) { lookup[nd.id] = nd; });
  nodeIds.forEach(function(id) {
    var nd = lookup[id];
    if (nd && nd.x !== undefined && nd.y !== undefined) {
      sx += nd.x; sy += nd.y; n++;
    } else if (nodesDataset) {
      // Cluster nodes (string IDs like 'cluster:1') won't be in NODES_DATA,
      // but their position is stored in the DataSet after buildClusters() runs.
      var dsNode = nodesDataset.get(id);
      if (dsNode && dsNode.x !== undefined && dsNode.y !== undefined) {
        sx += dsNode.x; sy += dsNode.y; n++;
      }
    }
  });
  return n > 0 ? {x: sx / n, y: sy / n} : {x: 0, y: 0};
}

// ── Clustering ─────────────────────────────────────────────────────────────
//
// Two clustering modes run in sequence before vis.Network is created:
//
//   1. buildClusters(skipSet)   — BFS same-type clustering (type-based).
//      skipSet contains container member IDs so they are not type-clustered.
//
//   2. buildContainerClusters() — groups nodes by ToolContainerID.
//      Reads the current DataSet (after type clustering) and remaps edges.
//      Cluster nodes are teal/green to distinguish them from type clusters (purple).
//
// Both share clusterMap, expandedGroups, groupMembers, clusterCounter.

function buildClusters(skipSet) {
  skipSet = skipSet || {};

  // ── Phase 1: BFS over undirected adjacency to find same-type components ──
  // Use undirected adjacency so that fan-in patterns (multiple same-type nodes
  // flowing into a single node of the same type) are treated as connected.
  var adjMap = {};  // nodeId -> [adjacent nodeIds, both directions]
  NODES_DATA.forEach(function(n) { adjMap[n.id] = []; });
  EDGES_DATA.forEach(function(e) {
    if (!adjMap[e.from]) adjMap[e.from] = [];
    if (!adjMap[e.to])   adjMap[e.to]   = [];
    adjMap[e.from].push(e.to);
    adjMap[e.to].push(e.from);
  });

  // tool type suffix from node.title (= full plugin path, e.g. AlteryxBasePluginsGui.Filter.Filter)
  var nodeTypeLookup = {};
  NODES_DATA.forEach(function(n) {
    nodeTypeLookup[n.id] = (n.title || '').split('.').pop();
  });

  var visited = {};
  var chains = [];  // variable name kept for compatibility with Phase 2+

  NODES_DATA.forEach(function(n) {
    if (visited[n.id]) return;
    if (skipSet[n.id]) { visited[n.id] = true; return; }  // container member: skip
    var toolType = nodeTypeLookup[n.id];

    // BFS: collect all directly-connected nodes of the same type
    var component = [];
    var queue = [n.id];
    visited[n.id] = true;

    while (queue.length > 0) {
      var curr = queue.shift();
      component.push(curr);
      (adjMap[curr] || []).forEach(function(neighbor) {
        if (!visited[neighbor] && !skipSet[neighbor] && nodeTypeLookup[neighbor] === toolType) {
          visited[neighbor] = true;
          queue.push(neighbor);
        }
      });
    }

    if (component.length >= MIN_CLUSTER_SIZE) {
      chains.push({chain: component, toolType: toolType});
    }
  });

  if (chains.length === 0) return;

  // ── Phase 2: assign cluster IDs and build memberToCluster map ────────────
  chains.forEach(function(c) {
    c.cid = 'cluster:' + (++clusterCounter);
  });

  var memberToCluster = {};
  chains.forEach(function(c) {
    c.chain.forEach(function(nid) { memberToCluster[nid] = c.cid; });
  });

  // ── Phase 3: remove all member nodes, add cluster nodes ──────────────────
  var allMembers = [];
  chains.forEach(function(c) { allMembers = allMembers.concat(c.chain); });
  nodesDataset.remove(allMembers);

  chains.forEach(function(c) {
    var cPos = centroid(c.chain);
    nodesDataset.add({
      id: c.cid,
      label: c.toolType + ' ×' + c.chain.length,
      title: c.toolType + ' cluster — Double-click to expand',
      shape: 'box',
      borderDashes: [5, 3],
      x: cPos.x, y: cPos.y,
      color: {
        background: '#4c1d95', border: '#7c3aed',
        highlight: {background: '#5b21b6', border: '#7c3aed'},
        hover: {background: '#5b21b6', border: '#7c3aed'}
      },
      font: {color: '#f1f5f9', size: 13}
    });
  });

  // ── Phase 4: remap all edges in a single pass ─────────────────────────────
  // Remove all original edges first, then re-add with remapped endpoints.
  // Any edge where both src and dst map to the same cluster is an intra-cluster
  // edge and is simply dropped. Cross-cluster or cluster-to-real edges become
  // bridge edges.
  edgesDataset.remove(EDGES_DATA.map(function(e) { return e.id; }));

  var seenEdgeKey = {};
  var clusterBridges = {};  // cid → [bridge edge ids]

  EDGES_DATA.forEach(function(e) {
    var src = memberToCluster[e.from] !== undefined ? memberToCluster[e.from] : e.from;
    var dst = memberToCluster[e.to]   !== undefined ? memberToCluster[e.to]   : e.to;
    if (src === dst) return;  // intra-cluster: skip

    var key = String(src) + '\x00' + String(dst);
    if (seenEdgeKey[key]) return;  // dedup (parallel chains can produce duplicate keys)
    seenEdgeKey[key] = true;

    // Preserve original numeric edge ID only when both endpoints are real nodes
    var newEid = (src === e.from && dst === e.to) ? e.id : 'br:' + (++clusterCounter);
    edgesDataset.add({id: newEid, from: src, to: dst});

    // Register bridge edge in every involved cluster
    if (typeof src === 'string' && src.indexOf('cluster:') === 0) {
      if (!clusterBridges[src]) clusterBridges[src] = [];
      clusterBridges[src].push(newEid);
    }
    if (typeof dst === 'string' && dst.indexOf('cluster:') === 0) {
      if (!clusterBridges[dst]) clusterBridges[dst] = [];
      clusterBridges[dst].push(newEid);
    }
  });

  // ── Phase 5: store cluster metadata ──────────────────────────────────────
  chains.forEach(function(c) {
    clusterMap[c.cid] = {
      memberIds: c.chain,
      toolType: c.toolType,
      bridgeEdgeIds: clusterBridges[c.cid] ? clusterBridges[c.cid].slice() : [],
    };
  });
}

// ── Container membership detection ────────────────────────────────────────
// Determines which data nodes fall inside each ToolContainer by comparing
// node canvas coordinates against container bounding rectangles from CONTAINERS_DATA.
// Nodes inside nested containers are assigned to the smallest enclosing box.
// Returns { nodeId: containerDataIndex, ... }.
function computeContainerMembership() {
  var result = {};
  if (CONTAINERS_DATA.length === 0) return result;
  var PAD = 8;  // tolerance for nodes sitting on the boundary
  NODES_DATA.forEach(function(n) {
    var bestIdx = -1, bestArea = Infinity;
    CONTAINERS_DATA.forEach(function(c, idx) {
      if (n.x >= c.x - PAD && n.x <= c.x + c.w + PAD &&
          n.y >= c.y - PAD && n.y <= c.y + c.h + PAD) {
        var area = c.w * c.h;
        if (area < bestArea) { bestArea = area; bestIdx = idx; }
      }
    });
    if (bestIdx >= 0) result[n.id] = bestIdx;
  });
  return result;
}

// ── Container clustering ───────────────────────────────────────────────────
// membership: { nodeId: containerDataIndex } from computeContainerMembership().
// Groups nodes by container, collapses each group into a teal cluster node.
// Runs AFTER buildClusters() so type-clustered members are already removed.
function buildContainerClusters(membership) {
  if (Object.keys(membership).length === 0) return;

  // Group surviving DataSet node IDs by container index.
  // After buildClusters() some member IDs may have been collapsed into a type
  // cluster; we only add IDs that are still in the DataSet.
  var groups = {};  // containerIdx -> [nodeIds or cluster IDs]
  Object.keys(membership).forEach(function(nid) {
    var id = parseInt(nid);
    var rep = resolveNode(id);   // real node or cluster ID representing it
    if (rep === null) return;    // removed and not in any cluster (shouldn't happen)
    var idx = membership[id];
    if (!groups[idx]) groups[idx] = [];
    // Avoid duplicates (multiple members may resolve to the same cluster)
    if (groups[idx].indexOf(rep) === -1) groups[idx].push(rep);
  });

  var clusterDefs = [];
  var memberToCluster = {};

  Object.keys(groups).forEach(function(idx) {
    var memberIds = groups[parseInt(idx)];
    if (memberIds.length < MIN_CLUSTER_SIZE) return;
    var c = CONTAINERS_DATA[parseInt(idx)];
    var clusterId = 'container:' + (++clusterCounter);
    var caption = c.label || ('Container ' + idx);
    clusteredContainerIdx[parseInt(idx)] = true;  // mark this container as clustered
    var label = caption + ' \xd7' + memberIds.length;
    memberIds.forEach(function(mid) { memberToCluster[mid] = clusterId; });
    clusterDefs.push({ cid: clusterId, memberIds: memberIds, caption: caption, label: label });
  });

  if (clusterDefs.length === 0) return;

  // Remove member nodes/clusters from DataSet
  var allMemberIds = [];
  clusterDefs.forEach(function(c) { allMemberIds = allMemberIds.concat(c.memberIds); });
  nodesDataset.remove(allMemberIds);

  // Add teal container cluster nodes
  clusterDefs.forEach(function(c) {
    var pos = centroid(c.memberIds);
    nodesDataset.add({
      id: c.cid, label: c.label,
      title: c.caption + ' — Double-click to expand',
      shape: 'box', borderDashes: [5, 3],
      x: pos.x, y: pos.y,
      color: CLUSTER_STYLE.container.normal,
      font: {color: '#f1f5f9', size: 13}
    });
  });

  // Remap edges
  var currentEdges = edgesDataset.get();
  var edgesToRemove = [], edgesToAdd = [], seenKey = {}, clusterBridges = {};

  currentEdges.forEach(function(e) {
    var src = memberToCluster[e.from] !== undefined ? memberToCluster[e.from] : e.from;
    var dst = memberToCluster[e.to]   !== undefined ? memberToCluster[e.to]   : e.to;
    if (src !== e.from || dst !== e.to) {
      edgesToRemove.push(e.id);
      if (src === dst) return;
      var key = String(src) + '\x00' + String(dst);
      if (seenKey[key]) return;
      seenKey[key] = true;
      var eid = 'br:' + (++clusterCounter);
      edgesToAdd.push({id: eid, from: src, to: dst});
      [src, dst].forEach(function(ep) {
        if (typeof ep === 'string' && ep.indexOf('container:') === 0) {
          if (!clusterBridges[ep]) clusterBridges[ep] = [];
          clusterBridges[ep].push(eid);
        }
      });
    }
  });

  edgesDataset.remove(edgesToRemove);
  edgesDataset.add(edgesToAdd);

  // Store metadata
  clusterDefs.forEach(function(c) {
    clusterMap[c.cid] = {
      memberIds: c.memberIds, toolType: c.caption,
      bridgeEdgeIds: clusterBridges[c.cid] || [],
      isContainer: true,
    };
  });
}

// Returns the node ID (or cluster ID) currently representing nodeId in the
// DataSet. Returns null if nodeId is not reachable (removed and unclustered).
function resolveNode(nodeId) {
  if (nodesDataset.get(nodeId) !== null) return nodeId;
  for (var cid in clusterMap) {
    if (clusterMap[cid].memberIds.indexOf(nodeId) !== -1) return cid;
  }
  return null;
}

// Re-collapse a previously expanded cluster. groupKey is the original cluster ID
// (e.g. 'cluster:1'). Any member node's double-click triggers this.
function recollapseGroup(groupKey) {
  var group = groupMembers[groupKey];
  if (!group) return;

  var memberSet = {};
  group.memberIds.forEach(function(mid) { memberSet[mid] = true; });

  // Remove all DataSet edges that touch any member node
  var edgesToRemove = edgesDataset.get().filter(function(e) {
    return memberSet[e.from] || memberSet[e.to];
  }).map(function(e) { return e.id; });
  edgesDataset.remove(edgesToRemove);

  // Remove member nodes
  nodesDataset.remove(group.memberIds);

  // Re-add cluster node with appropriate colors (teal for container, purple for type)
  var isContainer = group.isContainer || false;
  var cStyle = isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
  var clusterTitle = isContainer
    ? group.toolType + ' \u2014 Double-click to expand'
    : group.toolType + ' cluster \u2014 Double-click to expand';
  var cPos = centroid(group.memberIds);
  nodesDataset.add({
    id: groupKey,
    label: group.toolType + ' \xd7' + group.memberIds.length,
    title: clusterTitle,
    shape: 'box',
    borderDashes: [5, 3],
    x: cPos.x, y: cPos.y,
    color: cStyle.normal,
    font: {color: '#f1f5f9', size: 13}
  });

  // Re-derive bridge edges from EDGES_DATA (same logic as expandCluster edge step)
  var presentKeys = {};
  edgesDataset.get().forEach(function(e) {
    presentKeys[String(e.from) + '\x00' + String(e.to)] = true;
  });

  var bridgeEdgeIds = [];
  EDGES_DATA.forEach(function(e) {
    var srcIn = memberSet[e.from];
    var dstIn = memberSet[e.to];
    if (!srcIn && !dstIn) return;   // unrelated
    if (srcIn && dstIn) return;     // intra-cluster
    var src = srcIn ? groupKey : resolveNode(e.from);
    var dst = dstIn ? groupKey : resolveNode(e.to);
    if (!src || !dst) return;
    var key = String(src) + '\x00' + String(dst);
    if (presentKeys[key]) return;
    presentKeys[key] = true;
    var newEid = 'br:' + (++clusterCounter);
    edgesDataset.add({id: newEid, from: src, to: dst});
    bridgeEdgeIds.push(newEid);
    if (typeof dst === 'string' && dst.indexOf('cluster:') === 0 && clusterMap[dst]) {
      clusterMap[dst].bridgeEdgeIds.push(newEid);
    }
    if (typeof src === 'string' && src.indexOf('cluster:') === 0 && clusterMap[src]) {
      clusterMap[src].bridgeEdgeIds.push(newEid);
    }
  });

  // Restore cluster state
  clusterMap[groupKey] = {
    memberIds: group.memberIds,
    toolType: group.toolType,
    bridgeEdgeIds: bridgeEdgeIds,
    isContainer: group.isContainer || false,
    containerNodeId: group.containerNodeId,
  };

  // Clean up expanded state
  group.memberIds.forEach(function(mid) { delete expandedGroups[mid]; });
  delete groupMembers[groupKey];

  var cPos = centroid(group.memberIds);
  network.moveTo({position: cPos, animation: {duration: 300, easingFunction: 'easeInOutQuad'}});
}

function expandCluster(cid) {
  var c = clusterMap[cid];
  if (!c) return;

  // Remove cluster node + its bridge edges
  nodesDataset.remove(cid);
  edgesDataset.remove(c.bridgeEdgeIds);

  // Restore member nodes with current theme colors
  var col = nodeColors();
  c.memberIds.forEach(function(mid) {
    var orig = NODES_DATA.find(function(n) { return n.id === mid; });
    if (!orig) return;
    nodesDataset.add({
      id: orig.id, label: orig.label, title: orig.title, shape: 'box',
      x: orig.x, y: orig.y,
      color: {background: col.bg, border: col.bd,
              highlight: {background: col.sel, border: col.bd},
              hover: {background: col.hover, border: col.bd}},
      font: {color: col.font}
    });
  });

  // Record expanded group so the user can double-click any member to re-collapse
  var expandedMemberIds = c.memberIds.slice();
  var expandedToolType = c.toolType;
  var expandedIsContainer = c.isContainer || false;
  var expandedContainerNodeId = c.containerNodeId;
  delete clusterMap[cid];
  groupMembers[cid] = {
    memberIds: expandedMemberIds,
    toolType: expandedToolType,
    isContainer: expandedIsContainer,
    containerNodeId: expandedContainerNodeId,
  };
  expandedMemberIds.forEach(function(mid) { expandedGroups[mid] = cid; });

  // Re-derive edges connected to the just-expanded members.
  // We look at every original edge touching a member node, remap its endpoints
  // to what currently exists in the DataSet (real node or cluster), and add
  // the edge if it isn't already present.
  var memberSet = {};
  c.memberIds.forEach(function(mid) { memberSet[mid] = true; });

  // Build set of already-present edge keys to avoid duplicates
  var presentKeys = {};
  edgesDataset.get().forEach(function(e) {
    presentKeys[String(e.from) + '\x00' + String(e.to)] = true;
  });

  EDGES_DATA.forEach(function(e) {
    if (!memberSet[e.from] && !memberSet[e.to]) return;  // unrelated edge
    var src = resolveNode(e.from);
    var dst = resolveNode(e.to);
    if (!src || !dst || src === dst) return;
    var key = String(src) + '\x00' + String(dst);
    if (presentKeys[key]) return;
    presentKeys[key] = true;

    var newEid = (src === e.from && dst === e.to) ? e.id : 'br:' + (++clusterCounter);
    edgesDataset.add({id: newEid, from: src, to: dst});

    // Register the new bridge edge in any cluster it touches, so a subsequent
    // expandCluster() call can clean it up correctly.
    if (typeof dst === 'string' && dst.indexOf('cluster:') === 0 && clusterMap[dst]) {
      clusterMap[dst].bridgeEdgeIds.push(newEid);
    }
    if (typeof src === 'string' && src.indexOf('cluster:') === 0 && clusterMap[src]) {
      clusterMap[src].bridgeEdgeIds.push(newEid);
    }
  });

  var cPos = centroid(expandedMemberIds);
  network.moveTo({position: cPos, animation: {duration: 300, easingFunction: 'easeInOutQuad'}});
}

// ── Memo helpers ──────────────────────────────────────────────────────────
function _memoNodeDef(id, text, x, y, w, h) {
  var def = {
    id: id,
    label: text || '(memo)',
    title: 'Memo — double-click to edit',
    shape: 'box',
    x: x, y: y,
    color: {
      background: '#fef9c3', border: '#ca8a04',
      highlight: {background: '#fef08a', border: '#a16207'},
      hover:     {background: '#fef08a', border: '#a16207'}
    },
    font: {color: '#1c1917', size: 13},
    borderWidth: 2,
    shapeProperties: {borderRadius: 4}
  };
  if (w && h) {
    def.widthConstraint  = {minimum: w, maximum: w};
    def.heightConstraint = {minimum: h, maximum: h};
  }
  return def;
}

function saveMemos() {
  if (!network) return;
  Object.keys(memoData).forEach(function(id) {
    var pos = network.getPositions([id])[id];
    if (pos) { memoData[id].x = pos.x; memoData[id].y = pos.y; }
  });
  var edgeArr = Object.keys(memoEdges).map(function(eid) { return memoEdges[eid]; });
  try {
    localStorage.setItem(MEMO_STORAGE_KEY, JSON.stringify({nodes: memoData, edges: edgeArr}));
  } catch(e) {}
}

function loadMemos() {
  try {
    var raw = localStorage.getItem(MEMO_STORAGE_KEY);
    if (!raw) return;
    var saved = JSON.parse(raw);
    if (saved.nodes) {
      Object.keys(saved.nodes).forEach(function(id) {
        var m = saved.nodes[id];
        var numMatch = id.match(/^memo:(\d+)$/);
        if (numMatch) { var n = parseInt(numMatch[1]); if (n > memoCounter) memoCounter = n; }
        memoData[id] = m;
        nodesDataset.add(_memoNodeDef(id, m.text, m.x, m.y, m.w, m.h));
      });
    }
    if (saved.edges) {
      saved.edges.forEach(function(e) {
        var eid = 'memo-edge:' + (++memoCounter);
        edgesDataset.add({id: eid, from: e.from, to: e.to,
          color: {color: '#ca8a04', highlight: '#a16207', hover: '#a16207'}, width: 1.5});
        memoEdges[eid] = {from: e.from, to: e.to};
      });
    }
  } catch(e) {}
}

function openMemoModal(targetId, x, y) {
  _memoEditTarget = targetId;
  _memoPendingPos = (x !== undefined && y !== undefined) ? {x: x, y: y} : null;
  var isNew = (targetId === null);
  document.getElementById('memo-modal-title').textContent = isNew ? 'New Memo' : 'Edit Memo';
  document.getElementById('memo-textarea').value = isNew ? '' : (memoData[targetId] ? memoData[targetId].text : '');
  document.getElementById('memo-delete-btn').style.display = isNew ? 'none' : '';
  document.getElementById('memo-modal').classList.add('open');
  document.getElementById('memo-modal-overlay').classList.add('open');
  setTimeout(function() { document.getElementById('memo-textarea').focus(); }, 50);
}

function closeMemoModal() {
  document.getElementById('memo-modal').classList.remove('open');
  document.getElementById('memo-modal-overlay').classList.remove('open');
  _memoEditTarget = null;
  _memoPendingPos = null;
}

function saveMemoFromModal() {
  var text = document.getElementById('memo-textarea').value.trim() || '(memo)';
  if (_memoEditTarget === null) {
    var id = 'memo:' + (++memoCounter);
    var pos = _memoPendingPos || {x: 0, y: 0};
    memoData[id] = {text: text, x: pos.x, y: pos.y};
    nodesDataset.add(_memoNodeDef(id, text, pos.x, pos.y));
  } else {
    if (memoData[_memoEditTarget]) memoData[_memoEditTarget].text = text;
    nodesDataset.update({id: _memoEditTarget, label: text});
  }
  saveMemos();
  closeMemoModal();
}

function deleteMemoNode(memoId) {
  var toRemove = Object.keys(memoEdges).filter(function(eid) {
    return memoEdges[eid].from === memoId || memoEdges[eid].to === memoId;
  });
  edgesDataset.remove(toRemove);
  toRemove.forEach(function(eid) { delete memoEdges[eid]; });
  nodesDataset.remove(memoId);
  delete memoData[memoId];
  saveMemos();
}

function enterConnectMode(fromId) {
  _connectMode = true;
  _connectSourceId = fromId;
  document.getElementById('graph-canvas').style.cursor = 'crosshair';
  document.getElementById('connect-mode-hint').style.display = 'block';
}

function exitConnectMode() {
  _connectMode = false;
  _connectSourceId = null;
  var cv = document.getElementById('graph-canvas');
  if (cv && !cv._memoResizeCursor) cv.style.cursor = '';
  document.getElementById('connect-mode-hint').style.display = 'none';
}

// ── Network init ──────────────────────────────────────────────────────────
var _clusterClickTimer = null;

function initNetwork() {
  if (network) return;
  var canvas = document.getElementById('graph-canvas');
  nodesDataset = new vis.DataSet(NODES_DATA);
  edgesDataset = new vis.DataSet(EDGES_DATA);

  // Compute container membership by geometry before any clustering.
  // This gives type clustering a skipSet so container members stay intact.
  var containerMembership = computeContainerMembership();
  var containerMemberSet = {};
  Object.keys(containerMembership).forEach(function(nid) {
    containerMemberSet[parseInt(nid)] = true;
  });

  buildClusters(containerMemberSet);           // type-based BFS (skips container members)
  buildContainerClusters(containerMembership); // geometry-based container collapse

  network = new vis.Network(canvas, {nodes: nodesDataset, edges: edgesDataset}, options);
  network.fit();
  loadMemos();

  // Draw ToolContainer boundaries behind all nodes/edges.
  // Bounds are computed dynamically from the CURRENT vis-network positions of
  // each container's members, so the border:
  //  - shrinks to wrap a single cluster node when collapsed
  //  - expands to wrap all members when expanded
  //  - covers the full nested set for parent containers (all nodes whose
  //    initial canvas position fell inside the container's XML bounds)
  var CONT_PAD_X = 60, CONT_PAD_Y = 36, CONT_R = 10, CONT_HIT = 8;
  network.on('beforeDrawing', function(ctx) {
    if (CONTAINERS_DATA.length === 0) return;
    ctx.save();

    CONTAINERS_DATA.forEach(function(c, idx) {
      // 1. Find original node IDs whose initial position falls inside this container.
      //    Using initial positions (NODES_DATA) so membership is stable.
      var memberIds = [];
      NODES_DATA.forEach(function(nd) {
        if (nd.x >= c.x - CONT_HIT && nd.x <= c.x + c.w + CONT_HIT &&
            nd.y >= c.y - CONT_HIT && nd.y <= c.y + c.h + CONT_HIT) {
          memberIds.push(nd.id);
        }
      });
      if (memberIds.length === 0) return;

      // 2. Resolve each member to its current DataSet representative
      //    (handles type-clustered and container-clustered states).
      var reps = [];
      memberIds.forEach(function(nid) {
        var rep = resolveNode(nid);
        if (rep !== null && reps.indexOf(rep) === -1) reps.push(rep);
      });
      if (reps.length === 0) return;

      // 3. Get current vis-network positions and compute bounding box.
      var positions = network.getPositions(reps);
      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      var hasAny = false;
      reps.forEach(function(id) {
        var pos = positions[id];
        if (!pos) return;
        hasAny = true;
        minX = Math.min(minX, pos.x);
        minY = Math.min(minY, pos.y);
        maxX = Math.max(maxX, pos.x);
        maxY = Math.max(maxY, pos.y);
      });
      if (!hasAny) return;

      var x = minX - CONT_PAD_X, y = minY - CONT_PAD_Y;
      var w = maxX - minX + CONT_PAD_X * 2;
      var h = maxY - minY + CONT_PAD_Y * 2;
      var r = CONT_R;

      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.arcTo(x + w, y,     x + w, y + r,     r);
      ctx.lineTo(x + w, y + h - r);
      ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
      ctx.lineTo(x + r, y + h);
      ctx.arcTo(x,     y + h, x,     y + h - r, r);
      ctx.lineTo(x,     y + r);
      ctx.arcTo(x,     y,     x + r, y,          r);
      ctx.closePath();
      ctx.fillStyle = 'rgba(244,114,182,0.06)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(244,114,182,0.65)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([8, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (c.label) {
        if (clusteredContainerIdx[idx]) {
          // Clustered child container: small label above the border
          ctx.font = 'bold 11px system-ui,-apple-system,sans-serif';
          ctx.fillStyle = 'rgba(249,168,212,0.7)';
          ctx.fillText(c.label, x + 8, y - 4);
        } else {
          // Non-clustered parent container: large label with 【】above the border
          ctx.font = 'bold 18px system-ui,-apple-system,sans-serif';
          ctx.fillStyle = 'rgba(249,168,212,0.95)';
          ctx.fillText('【' + c.label + '】', x + 10, y - 6);
        }
      }
    });
    ctx.restore();
  });

  network.on('click', function(params) {
    // Connect mode: user clicks a target node to wire a memo edge
    if (_connectMode) {
      if (params.nodes.length > 0) {
        var targetId = params.nodes[0];
        if (targetId !== _connectSourceId) {
          var eid = 'memo-edge:' + (++memoCounter);
          edgesDataset.add({id: eid, from: _connectSourceId, to: targetId,
            color: {color: '#ca8a04', highlight: '#a16207', hover: '#a16207'}, width: 1.5});
          memoEdges[eid] = {from: _connectSourceId, to: targetId};
          saveMemos();
        }
      }
      exitConnectMode();
      return;
    }
    if (params.nodes.length === 0) { closePanel(); return; }
    var nodeId = params.nodes[0];
    // Delay panel open for any node that is double-clickable (cluster or
    // expanded member) so the overlay does not block the second tap.
    if (clusterMap[nodeId] || expandedGroups[nodeId]) {
      clearTimeout(_clusterClickTimer);
      _clusterClickTimer = setTimeout(function() {
        _clusterClickTimer = null;
        openPanel(nodeId);
      }, 280);
    } else {
      openPanel(nodeId);
    }
  });
  network.on('doubleClick', function(params) {
    clearTimeout(_clusterClickTimer);
    _clusterClickTimer = null;
    // Empty canvas double-click → create memo at that canvas position
    if (params.nodes.length === 0) {
      var cp = params.pointer.canvas;
      openMemoModal(null, cp.x, cp.y);
      return;
    }
    var nodeId = params.nodes[0];
    // Memo node double-click → edit
    if (typeof nodeId === 'string' && nodeId.indexOf('memo:') === 0) {
      openMemoModal(nodeId);
      return;
    }
    if (clusterMap[nodeId]) {
      expandCluster(nodeId);
    } else if (expandedGroups[nodeId]) {
      recollapseGroup(expandedGroups[nodeId]);
    }
  });
  // Persist memo positions after drag
  network.on('dragEnd', function(params) {
    if (params.nodes.length === 0) return;
    var hasMemo = params.nodes.some(function(id) {
      return typeof id === 'string' && id.indexOf('memo:') === 0;
    });
    if (hasMemo) saveMemos();
  });

  // Draw a rounded-rect border around each expanded cluster's member nodes.
  // Runs on every canvas redraw so it automatically follows zoom / pan / drag.
  network.on('afterDrawing', function(ctx) {
    var groupKeys = Object.keys(groupMembers);
    if (groupKeys.length === 0) return;

    ctx.save();
    groupKeys.forEach(function(groupKey) {
      var group = groupMembers[groupKey];
      var positions = network.getPositions(group.memberIds);

      var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      var hasNode = false;
      group.memberIds.forEach(function(mid) {
        var pos = positions[mid];
        if (!pos) return;
        hasNode = true;
        minX = Math.min(minX, pos.x);
        minY = Math.min(minY, pos.y);
        maxX = Math.max(maxX, pos.x);
        maxY = Math.max(maxY, pos.y);
      });
      if (!hasNode) return;

      var x = minX - BOX_PAD_X, y = minY - BOX_PAD_Y;
      var w = maxX - minX + BOX_PAD_X * 2;
      var h = maxY - minY + BOX_PAD_Y * 2;
      var r = BOX_RADIUS;

      var bs = group.isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
      var strokeColor = bs.stroke;
      var fillColor   = bs.fill;
      var labelColor  = bs.label;

      // Rounded rectangle path
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.arcTo(x + w, y,     x + w, y + r,     r);
      ctx.lineTo(x + w, y + h - r);
      ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
      ctx.lineTo(x + r, y + h);
      ctx.arcTo(x,     y + h, x,     y + h - r, r);
      ctx.lineTo(x,     y + r);
      ctx.arcTo(x,     y,     x + r, y,          r);
      ctx.closePath();

      ctx.fillStyle = fillColor;
      ctx.fill();

      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([7, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Group label in the top-left corner of the box
      ctx.fillStyle = labelColor;
      ctx.font = 'bold 11px system-ui,-apple-system,sans-serif';
      ctx.fillText(group.toolType, x + 8, y - 5);
    });
    ctx.restore();
  });

  // Draw resize handles (small orange squares at bottom-right corner) for all memo nodes.
  // Also refreshes _memoHandles used for hit-testing in the mousedown listener.
  network.on('afterDrawing', function(ctx) {
    _memoHandles = {};
    Object.keys(memoData).forEach(function(memoId) {
      if (!nodesDataset.get(memoId)) return;
      var bb = network.getBoundingBox(memoId);
      if (!bb) return;
      _memoHandles[memoId] = {x: bb.right, y: bb.bottom};
      ctx.save();
      ctx.fillStyle = '#ca8a04';
      ctx.strokeStyle = '#92400e';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.rect(bb.right - 5, bb.bottom - 5, 8, 8);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    });
  });

  // ── Memo resize drag (capture-phase so we intercept before vis-network) ──
  var HANDLE_HIT_PX = 10;  // hit radius in DOM pixels
  canvas.addEventListener('mousedown', function(e) {
    if (Object.keys(_memoHandles).length === 0) return;
    var rect = canvas.getBoundingClientRect();
    var domX = e.clientX - rect.left;
    var domY = e.clientY - rect.top;
    var scale = network.getScale();
    var canvasPos = network.DOMtoCanvas({x: domX, y: domY});
    var hitR = HANDLE_HIT_PX / scale;
    var found = null;
    Object.keys(_memoHandles).forEach(function(memoId) {
      var h = _memoHandles[memoId];
      if (Math.abs(canvasPos.x - h.x) <= hitR && Math.abs(canvasPos.y - h.y) <= hitR) found = memoId;
    });
    if (!found) return;
    e.preventDefault();
    e.stopPropagation();
    var bb = network.getBoundingBox(found);
    _resizeState = {
      memoId: found,
      startDomX: domX, startDomY: domY,
      startW: bb.right - bb.left,
      startH: bb.bottom - bb.top
    };
  }, true);  // capture phase

  // Cursor feedback when hovering over a resize handle
  canvas.addEventListener('mousemove', function(e) {
    if (_resizeState || _connectMode) return;
    if (Object.keys(_memoHandles).length === 0) { return; }
    var rect = canvas.getBoundingClientRect();
    var domX = e.clientX - rect.left;
    var domY = e.clientY - rect.top;
    var scale = network.getScale();
    var canvasPos = network.DOMtoCanvas({x: domX, y: domY});
    var hitR = HANDLE_HIT_PX / scale;
    var onHandle = Object.keys(_memoHandles).some(function(id) {
      var h = _memoHandles[id];
      return Math.abs(canvasPos.x - h.x) <= hitR && Math.abs(canvasPos.y - h.y) <= hitR;
    });
    if (!canvas._memoResizeCursor && onHandle) {
      canvas._memoResizeCursor = true;
      canvas.style.cursor = 'se-resize';
    } else if (canvas._memoResizeCursor && !onHandle) {
      canvas._memoResizeCursor = false;
      canvas.style.cursor = '';
    }
  });

  document.addEventListener('mousemove', function(e) {
    if (!_resizeState) return;
    var rect = canvas.getBoundingClientRect();
    var dx = (e.clientX - rect.left) - _resizeState.startDomX;
    var dy = (e.clientY - rect.top)  - _resizeState.startDomY;
    var scale = network.getScale();
    var newW = Math.max(60, _resizeState.startW + dx / scale);
    var newH = Math.max(28, _resizeState.startH + dy / scale);
    nodesDataset.update({
      id: _resizeState.memoId,
      widthConstraint:  {minimum: newW, maximum: newW},
      heightConstraint: {minimum: newH, maximum: newH}
    });
  });

  document.addEventListener('mouseup', function() {
    if (!_resizeState) return;
    var rs = _resizeState;
    _resizeState = null;
    canvas.style.cursor = '';
    canvas._memoResizeCursor = false;
    var bb = network.getBoundingBox(rs.memoId);
    if (memoData[rs.memoId] && bb) {
      memoData[rs.memoId].w = bb.right - bb.left;
      memoData[rs.memoId].h = bb.bottom - bb.top;
      saveMemos();
    }
  });
}

try {
  initNetwork();
  requestAnimationFrame(function() {
    if (network) { network.redraw(); network.fit({animation: false}); }
  });
} catch(err) {
  var errDiv = document.createElement('div');
  errDiv.style.cssText = 'position:fixed;top:10px;left:10px;right:10px;background:#dc2626;color:#fff;padding:16px;z-index:9999;font-family:monospace;white-space:pre-wrap;border-radius:8px;font-size:13px';
  errDiv.textContent = 'JS ERROR: ' + err.message + ' | ' + (err.stack || '');
  document.body.appendChild(errDiv);
}

window.addEventListener('resize', function() {
  if (network) { network.redraw(); network.fit({animation: false}); }
});

// ── Config panel ──────────────────────────────────────────────────────────
function renderConfigRows(entry, container) {
  var keys = Object.keys(entry.config);
  if (keys.length === 0) {
    var empty = document.createElement('div');
    empty.style.cssText = 'color:var(--text-muted);font-size:13px;';
    empty.textContent = 'No configuration data.';
    container.appendChild(empty);
    return;
  }
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
    container.appendChild(row);
  });
}

function openPanel(nodeId) {
  var body = document.getElementById('panel-body');
  body.innerHTML = '';

  // Memo node — show editable memo panel
  if (typeof nodeId === 'string' && nodeId.indexOf('memo:') === 0) {
    var m = memoData[nodeId];
    document.getElementById('panel-title-text').textContent = 'Memo';
    var textDiv = document.createElement('div');
    textDiv.className = 'config-val';
    textDiv.style.cssText = 'white-space:pre-wrap;min-height:40px;margin-bottom:12px;';
    textDiv.textContent = m ? m.text : '';
    body.appendChild(textDiv);
    var hint = document.createElement('div');
    hint.style.cssText = 'font-size:11px;color:var(--text-muted);margin-bottom:10px;';
    hint.textContent = 'Double-click the node to edit.';
    body.appendChild(hint);
    var acts = document.createElement('div');
    acts.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;';
    var editBtn = document.createElement('button');
    editBtn.className = 'ctrl-btn';
    editBtn.textContent = 'Edit';
    editBtn.onclick = function() { closePanel(); openMemoModal(nodeId); };
    var connectBtn = document.createElement('button');
    connectBtn.className = 'ctrl-btn';
    connectBtn.textContent = 'Connect to…';
    connectBtn.onclick = function() { closePanel(); enterConnectMode(nodeId); };
    var delBtn = document.createElement('button');
    delBtn.className = 'ctrl-btn';
    delBtn.style.color = '#f87171';
    delBtn.textContent = 'Delete';
    delBtn.onclick = function() { closePanel(); deleteMemoNode(nodeId); };
    acts.appendChild(editBtn);
    acts.appendChild(connectBtn);
    acts.appendChild(delBtn);
    body.appendChild(acts);
    document.getElementById('config-panel').classList.add('open');
    return;
  }

  // Cluster node — show member list
  if (clusterMap[nodeId]) {
    var c = clusterMap[nodeId];
    document.getElementById('panel-title-text').textContent =
      c.toolType + ' ×' + c.memberIds.length + ' nodes';
    var hint = document.createElement('div');
    hint.style.cssText = 'font-size:12px;color:var(--text-muted);margin-bottom:12px;';
    hint.textContent = 'Double-click the node to expand.';
    body.appendChild(hint);
    c.memberIds.forEach(function(mid) {
      var entry = CONFIG_MAP[String(mid)];
      if (!entry) return;
      var hdr = document.createElement('div');
      hdr.className = 'cluster-member-header';
      hdr.textContent = entry.label;
      body.appendChild(hdr);
      renderConfigRows(entry, body);
    });
    document.getElementById('config-panel').classList.add('open');
    return;
  }

  var entry = CONFIG_MAP[String(nodeId)];
  if (!entry) return;
  document.getElementById('panel-title-text').textContent = entry.label + ' (ID: ' + nodeId + ')';
  renderConfigRows(entry, body);
  document.getElementById('config-panel').classList.add('open');
}

function closePanel() {
  document.getElementById('config-panel').classList.remove('open');
}

document.getElementById('panel-close-btn').addEventListener('click', closePanel);
document.getElementById('panel-overlay').addEventListener('click', closePanel);
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    if (_connectMode) { exitConnectMode(); return; }
    closeMemoModal();
    closePanel();
    return;
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && !e.target.matches('input,textarea')) {
    var sel = network ? network.getSelectedNodes() : [];
    sel.forEach(function(id) {
      if (typeof id === 'string' && id.indexOf('memo:') === 0) deleteMemoNode(id);
    });
  }
});

// ── Memo modal events ─────────────────────────────────────────────────────
document.getElementById('memo-save-btn').addEventListener('click', saveMemoFromModal);
document.getElementById('memo-cancel-btn').addEventListener('click', closeMemoModal);
document.getElementById('memo-modal-overlay').addEventListener('click', closeMemoModal);
document.getElementById('memo-delete-btn').addEventListener('click', function() {
  if (_memoEditTarget) deleteMemoNode(_memoEditTarget);
  closeMemoModal();
});
document.getElementById('memo-textarea').addEventListener('keydown', function(e) {
  if (e.key === 'Escape') { e.stopPropagation(); closeMemoModal(); }
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveMemoFromModal(); }
});

document.getElementById('add-memo-btn').addEventListener('click', function() {
  var center = network ? network.getViewPosition() : {x: 0, y: 0};
  openMemoModal(null, center.x, center.y);
});

// ── Controls ──────────────────────────────────────────────────────────────
document.getElementById('fit-btn').addEventListener('click', function() {
  if (network) network.fit({animation: true});
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
    setTimeout(function() { if (network) network.fit({animation: false}); }, 50);
  }
});

// ── Search ────────────────────────────────────────────────────────────────
var searchActive = false;

function nodeColors() {
  var s = getComputedStyle(document.documentElement);
  return {
    bg:    s.getPropertyValue('--node-bg').trim(),
    bd:    s.getPropertyValue('--node-border').trim(),
    font:  s.getPropertyValue('--node-font').trim(),
    hover: s.getPropertyValue('--node-hover').trim(),
    sel:   s.getPropertyValue('--node-select').trim(),
  };
}

function doSearch(query) {
  query = query.trim().toLowerCase();
  if (!query) { clearSearch(); return; }
  searchActive = true;
  document.getElementById('search-clear-btn').style.display = 'block';

  var col = nodeColors();
  var allNodes = nodesDataset.get();
  var updates = [];
  var firstMatch = null;

  allNodes.forEach(function(n) {
    // Memo nodes: dim when not matching, restore when matching, never touch colors otherwise
    if (typeof n.id === 'string' && n.id.indexOf('memo:') === 0) {
      var mLabel = (n.label || '').toLowerCase();
      var mMatch = mLabel.indexOf(query) !== -1;
      updates.push({id: n.id, font: {color: mMatch ? '#1c1917' : '#a8a29e'}});
      if (mMatch && firstMatch === null) firstMatch = n.id;
      return;
    }
    var idStr  = String(n.id).toLowerCase();
    var label  = (n.label || '').toLowerCase();
    var matches = idStr === query || label.indexOf(query) !== -1;

    if (matches) {
      if (firstMatch === null) firstMatch = n.id;
      if (clusterMap[n.id]) {
        var cs = clusterMap[n.id].isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
        updates.push({id: n.id, color: {
          background: cs.matchBg, border: '#f59e0b',
          highlight: {background: cs.matchBg, border: '#f59e0b'},
          hover: {background: cs.matchBg, border: '#f59e0b'}
        }, font: {color: '#f1f5f9'}});
      } else {
        updates.push({id: n.id, color: {
          background: col.bg, border: '#f59e0b',
          highlight: {background: col.sel, border: '#f59e0b'},
          hover: {background: col.hover, border: '#f59e0b'}
        }, font: {color: col.font}});
      }
    } else {
      if (clusterMap[n.id]) {
        var cd = (clusterMap[n.id].isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type).dim;
        updates.push({id: n.id, color: {
          background: cd.background, border: cd.border,
          highlight: {background: cd.background, border: cd.border},
          hover: {background: cd.background, border: cd.border}
        }, font: {color: '#6b7280'}});
      } else {
        updates.push({id: n.id, color: {
          background: col.bg, border: col.bd,
          highlight: {background: col.bg, border: col.bd},
          hover: {background: col.bg, border: col.bd}
        }, font: {color: '#64748b'}});
      }
    }
  });

  nodesDataset.update(updates);
  if (firstMatch !== null) {
    network.focus(firstMatch, {scale: 1.2, animation: {duration: 400, easingFunction: 'easeInOutQuad'}});
  }
}

function clearSearch() {
  searchActive = false;
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear-btn').style.display = 'none';
  var col = nodeColors();
  nodesDataset.update(nodesDataset.get().map(function(n) {
    if (clusterMap[n.id]) {
      var cs = clusterMap[n.id].isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
      return {id: n.id, color: cs.normal, font: {color: '#f1f5f9'}};
    }
    if (typeof n.id === 'string' && n.id.indexOf('memo:') === 0) {
      return {id: n.id, font: {color: '#1c1917'}};  // restore memo font
    }
    return {id: n.id, color: {
      background: col.bg, border: col.bd,
      highlight: {background: col.sel, border: col.bd},
      hover: {background: col.hover, border: col.bd}
    }, font: {color: col.font}};
  }));
}

document.getElementById('search-input').addEventListener('input', function() {
  doSearch(this.value);
});
document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { this.blur(); }
  else if (e.key === 'Escape') { clearSearch(); this.blur(); }
});
document.getElementById('search-clear-btn').addEventListener('click', function() {
  clearSearch();
  document.getElementById('search-input').focus();
});
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    var inp = document.getElementById('search-input');
    inp.focus(); inp.select();
  }
});

// ── Theme toggle ──────────────────────────────────────────────────────────
var isDark = true;
function applyTheme(theme) {
  isDark = (theme === 'dark');
  if (isDark) {
    document.documentElement.classList.remove('light');
  } else {
    document.documentElement.classList.add('light');
  }
  document.getElementById('theme-btn').textContent = isDark ? 'Light Mode' : 'Dark Mode';
  if (!nodesDataset || !edgesDataset) return;
  var s = getComputedStyle(document.documentElement);
  var edgeColor = s.getPropertyValue('--edge-color').trim();
  var nodeBg    = s.getPropertyValue('--node-bg').trim();
  var nodeBd    = s.getPropertyValue('--node-border').trim();
  var nodeFont  = s.getPropertyValue('--node-font').trim();
  var nodeHover = s.getPropertyValue('--node-hover').trim();
  var nodeSel   = s.getPropertyValue('--node-select').trim();
  // Iterate only nodes/edges currently in the DataSet.
  // Using NODES_DATA.map() here would re-create clustered-away nodes because
  // DataSet.update() inserts missing IDs as new (label-less) items.
  var nodeUpdates = [];
  nodesDataset.getIds().forEach(function(id) {
    if (clusterMap[id]) return;  // cluster node: fixed color (purple/teal) — skip
    if (typeof id === 'string' && id.indexOf('memo:') === 0) return;  // memo: keep yellow
    nodeUpdates.push({id: id, color: {background: nodeBg, border: nodeBd,
      highlight: {background: nodeSel, border: nodeBd},
      hover: {background: nodeHover, border: nodeBd}}, font: {color: nodeFont}});
  });
  nodesDataset.update(nodeUpdates);
  edgesDataset.update(edgesDataset.getIds().map(function(id) {
    return {id: id, color: {color: edgeColor, highlight: edgeColor, hover: edgeColor}};
  }));
}
document.getElementById('theme-btn').addEventListener('click', function() {
  var next = isDark ? 'light' : 'dark';
  localStorage.setItem('yxray-theme', next);
  applyTheme(next);
});
var savedTheme = localStorage.getItem('yxray-theme') || 'dark';
applyTheme(savedTheme);

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
        nodes_json, edges_json, config_map, containers_json = self._build_graph_data(doc)
        vis_js = load_vis_js()
        title = pathlib.Path(doc.filepath).name

        env = Environment(autoescape=True)  # noqa: S701
        env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}
        template = env.from_string(_HTML_TEMPLATE)
        data_node_count = sum(1 for n in doc.nodes if "ToolContainer" not in n.tool_type)
        return template.render(
            title=title,
            node_count=data_node_count,
            edge_count=len(doc.connections),
            nodes_json=json.dumps(nodes_json),
            edges_json=json.dumps(edges_json),
            config_map_json=json.dumps(config_map),
            containers_json=json.dumps(containers_json),
            vis_js=vis_js,
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
            }
            for node in doc.nodes
            if "ToolContainer" in node.tool_type and node.width > 0 and node.height > 0
        ]

        return nodes_json, edges_json, config_map, containers_json

    def _container_label(self, node: AlteryxNode) -> str:
        caption_entry = node.config.get("Caption", {})
        if isinstance(caption_entry, dict):
            text = caption_entry.get("#text", "")
        else:
            text = str(caption_entry) if caption_entry else ""
        return text or f"Container ({int(node.tool_id)})"

    def _vis_node(self, node_id: int, node: AlteryxNode) -> dict[str, Any]:
        short_type = node.tool_type.split(".")[-1]
        return {
            "id": node_id,
            "label": f"{short_type}\n({node_id})",
            "title": node.tool_type,
            "containerId": node.container_id,
            "x": node.x,
            "y": node.y,
        }

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
