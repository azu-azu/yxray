# ruff: noqa: E501
"""Standalone HTML report renderer for a single Alteryx workflow.

SingleGraphRenderer.render(doc) produces a full standalone HTML document
(not a fragment) containing an interactive vis-network graph.

vis-network UMD is inlined via load_vis_js() — zero CDN references.
Physics is disabled; layout is handled by vis-network hierarchical engine.
Clustering collapses same-type linear chains (length >= 3) into single nodes.
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
  </style>
</head>
<body>
  <header>
    <div>
      <div class="header-title">{{ title }}</div>
      <div class="header-meta">{{ node_count }} nodes &middot; {{ edge_count }} connections</div>
    </div>
    <div class="header-right">
      <div class="search-wrap">
        <input type="text" id="search-input" class="search-input" placeholder="Search node…" autocomplete="off" spellcheck="false" />
        <button class="search-clear" id="search-clear-btn" aria-label="Clear">&times;</button>
      </div>
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
  <script>{{ vis_js | safe }}</script>
  <script>
var NODES_DATA = {{ nodes_json | safe }};
var EDGES_DATA = {{ edges_json | safe }};
var CONFIG_MAP = {{ config_map_json | safe }};

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
// type = same-type BFS cluster (purple); container = ToolContainer group (teal).
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
    normal: {background:'#065f46', border:'#059669',
             highlight:{background:'#047857', border:'#059669'},
             hover:    {background:'#047857', border:'#059669'}},
    dim:    {background:'#022c22', border:'#065f46'},
    matchBg: '#047857',
    stroke: '#059669', fill: 'rgba(5,150,105,0.07)', label: '#34d399',
  },
};

// ── Cluster state ─────────────────────────────────────────────────────────
var clusterMap = {};       // { 'cluster:N' | 'container:N': { memberIds, toolType, bridgeEdgeIds, isContainer } }
var expandedGroups = {};   // nodeId -> groupKey  (nodes that were expanded from a cluster)
var groupMembers = {};     // groupKey -> { memberIds, toolType, isContainer, containerNodeId }
var clusterCounter = 0;

var options = {
  layout: {
    hierarchical: {
      enabled: true,
      direction: 'LR',
      sortMethod: 'directed',
      nodeSpacing: 120,
      levelSeparation: 220,
      treeSpacing: 150,
    }
  },
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
    nodesDataset.add({
      id: c.cid,
      label: c.toolType + ' ×' + c.chain.length,
      title: c.toolType + ' cluster — Double-click to expand',
      shape: 'box',
      borderDashes: [5, 3],
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

// ── Container clustering ───────────────────────────────────────────────────
// Groups nodes by their containerId (parsed from ToolContainerID in the yxmd).
// Runs AFTER buildClusters() so it operates on the already-modified DataSet.
// Container clusters use teal/green color (#065f46) to distinguish from
// type-based clusters (purple #4c1d95).

function buildContainerClusters() {
  // Step 1: collect containerLabels and direct-member groups from raw NODES_DATA.
  var containerLabels = {};  // containerNodeId -> caption string
  var containerGroups = {};  // containerNodeId -> [direct member nodeIds (data + nested containers)]

  NODES_DATA.forEach(function(n) {
    if (n.containerLabel !== undefined) {
      containerLabels[n.id] = n.containerLabel;
    }
    if (n.containerId !== null && n.containerId !== undefined) {
      if (!containerGroups[n.containerId]) containerGroups[n.containerId] = [];
      containerGroups[n.containerId].push(n.id);
    }
  });

  if (Object.keys(containerGroups).length === 0) return;

  // Step 2: identify root containers — those whose own node has no containerId.
  // Nested container nodes (containerId set) are collected under their parent and
  // are NOT turned into separate clusters; only root containers become clusters.
  var nestedContainerNodeIds = {};
  NODES_DATA.forEach(function(n) {
    if (n.containerLabel !== undefined &&
        n.containerId !== null && n.containerId !== undefined) {
      nestedContainerNodeIds[n.id] = true;
    }
  });

  var rootContainerIds = Object.keys(containerGroups).map(Number).filter(function(cid) {
    return !nestedContainerNodeIds[cid];
  });

  if (rootContainerIds.length === 0) return;

  // Recursively collect all non-container descendant node IDs under a container.
  function collectLeafMembers(containerId) {
    var result = [];
    (containerGroups[containerId] || []).forEach(function(mid) {
      if (containerLabels[mid] !== undefined) {
        // mid is a nested ToolContainer node — recurse into it
        result = result.concat(collectLeafMembers(mid));
      } else {
        result.push(mid);
      }
    });
    return result;
  }

  // Step 3: build cluster defs (root containers only) and memberToCluster map
  var clusterDefs = [];
  var memberToCluster = {};   // data nodeId -> root clusterId
  var allContainerNodeIds = {};  // every ToolContainer node — no data role, edges dropped
  Object.keys(containerLabels).forEach(function(k) { allContainerNodeIds[parseInt(k)] = true; });

  rootContainerIds.forEach(function(containerId) {
    var memberIds = collectLeafMembers(containerId);
    if (memberIds.length === 0) return;
    var clusterId = 'container:' + containerId;
    var caption = containerLabels[containerId] || ('Container ' + containerId);
    var label = caption + ' \xd7' + memberIds.length;
    memberIds.forEach(function(mid) { memberToCluster[mid] = clusterId; });
    clusterDefs.push({ cid: clusterId, memberIds: memberIds, containerNodeId: containerId, label: label, caption: caption });
  });

  if (clusterDefs.length === 0) return;

  // Step 4: remove all data members and ALL ToolContainer nodes from DataSet
  var removeSet = {};
  clusterDefs.forEach(function(c) { c.memberIds.forEach(function(id) { removeSet[id] = true; }); });
  Object.keys(allContainerNodeIds).forEach(function(k) {
    var id = parseInt(k);
    if (nodesDataset.get(id) !== null) removeSet[id] = true;
  });
  nodesDataset.remove(Object.keys(removeSet).map(Number));

  // Step 5: add container cluster nodes (teal/green)
  clusterDefs.forEach(function(c) {
    nodesDataset.add({
      id: c.cid,
      label: c.label,
      title: c.caption + ' — Double-click to expand',
      shape: 'box',
      borderDashes: [5, 3],
      color: CLUSTER_STYLE.container.normal,
      font: {color: '#f1f5f9', size: 13}
    });
  });

  // Step 6: remap edges using CURRENT DataSet state (after type clustering).
  // Only edges that touch container members or the container node need changing.
  var currentEdges = edgesDataset.get();
  var edgesToRemove = [];
  var edgesToAdd = [];
  var seenEdgeKey = {};
  var clusterBridges = {};

  currentEdges.forEach(function(e) {
    var srcMapped = memberToCluster[e.from];
    var dstMapped = memberToCluster[e.to];

    // ToolContainer node itself has no data role — drop any edge to/from it
    if (allContainerNodeIds[e.from] || allContainerNodeIds[e.to]) {
      edgesToRemove.push(e.id);
      return;
    }

    var src = srcMapped !== undefined ? srcMapped : e.from;
    var dst = dstMapped !== undefined ? dstMapped : e.to;

    // Only act if at least one endpoint changed
    if (src !== e.from || dst !== e.to) {
      edgesToRemove.push(e.id);
      if (src === dst) return;  // intra-cluster: drop
      var key = String(src) + '\x00' + String(dst);
      if (seenEdgeKey[key]) return;
      seenEdgeKey[key] = true;
      var newEid = 'br:' + (++clusterCounter);
      edgesToAdd.push({id: newEid, from: src, to: dst});
      if (typeof src === 'string' && src.indexOf('container:') === 0) {
        if (!clusterBridges[src]) clusterBridges[src] = [];
        clusterBridges[src].push(newEid);
      }
      if (typeof dst === 'string' && dst.indexOf('container:') === 0) {
        if (!clusterBridges[dst]) clusterBridges[dst] = [];
        clusterBridges[dst].push(newEid);
      }
    }
  });

  edgesDataset.remove(edgesToRemove);
  edgesDataset.add(edgesToAdd);

  // Step 7: store cluster metadata
  clusterDefs.forEach(function(c) {
    clusterMap[c.cid] = {
      memberIds: c.memberIds,
      toolType: c.caption,
      bridgeEdgeIds: clusterBridges[c.cid] ? clusterBridges[c.cid].slice() : [],
      isContainer: true,
      containerNodeId: c.containerNodeId,
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
  nodesDataset.add({
    id: groupKey,
    label: group.toolType + ' \xd7' + group.memberIds.length,
    title: clusterTitle,
    shape: 'box',
    borderDashes: [5, 3],
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

  network.fit({animation: true});
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

  network.fit({animation: true});
}

// ── Network init ──────────────────────────────────────────────────────────
var _clusterClickTimer = null;

function initNetwork() {
  if (network) return;
  var canvas = document.getElementById('graph-canvas');
  nodesDataset = new vis.DataSet(NODES_DATA);
  edgesDataset = new vis.DataSet(EDGES_DATA);

  // Container members get priority — build skipSet so type clustering ignores them
  var containerMemberIds = {};
  NODES_DATA.forEach(function(n) {
    if (n.containerId !== null && n.containerId !== undefined) {
      containerMemberIds[n.id] = true;
    }
  });

  buildClusters(containerMemberIds);  // type-based BFS (skips container members)
  buildContainerClusters();            // container-based (operates on current DataSet)

  network = new vis.Network(canvas, {nodes: nodesDataset, edges: edgesDataset}, options);
  network.fit();
  network.on('click', function(params) {
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
    if (params.nodes.length === 0) return;
    var nodeId = params.nodes[0];
    if (clusterMap[nodeId]) {
      expandCluster(nodeId);
    } else if (expandedGroups[nodeId]) {
      recollapseGroup(expandedGroups[nodeId]);
    }
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
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closePanel(); });

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
        nodes_json: list[dict[str, Any]] = [
            self._vis_node(int(node.tool_id), node) for node in doc.nodes
        ]

        edges_json: list[dict[str, Any]] = [
            {"id": i, "from": int(c.src_tool), "to": int(c.dst_tool)}
            for i, c in enumerate(doc.connections)
        ]

        config_map: dict[str, Any] = {
            str(int(node.tool_id)): {
                "label": f"{node.tool_type.split('.')[-1]} (ID: {int(node.tool_id)})",
                "config": self._clean_config(node),
            }
            for node in doc.nodes
        }

        return nodes_json, edges_json, config_map

    def _vis_node(self, node_id: int, node: AlteryxNode) -> dict[str, Any]:
        short_type = node.tool_type.split(".")[-1]
        result: dict[str, Any] = {
            "id": node_id,
            "label": f"{short_type}\n({node_id})",
            "title": node.tool_type,
            "containerId": node.container_id,
        }
        if "ToolContainer" in node.tool_type:
            caption_entry = node.config.get("Caption", {})
            if isinstance(caption_entry, dict):
                caption = caption_entry.get("#text", "")
            else:
                caption = str(caption_entry) if caption_entry else ""
            result["containerLabel"] = caption or f"Container ({node_id})"
        return result

    def _clean_config(self, node: AlteryxNode) -> dict[str, Any]:
        """Return config dict excluding XML attribute keys (@ prefix)."""
        return {k: v for k, v in node.config.items() if not k.startswith("@")}
