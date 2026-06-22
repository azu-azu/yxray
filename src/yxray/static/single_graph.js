// Data injected by SingleGraphRenderer via #yxray-data script tag
var __d = JSON.parse(document.getElementById('yxray-data').textContent);
var NODES_DATA = __d.nodes;
var EDGES_DATA = __d.edges;
var CONFIG_MAP = __d.config_map;
var CONTAINERS_DATA = __d.containers;
var NODE_LAYER = __d.node_layer;
var NODE_POS = {};
NODES_DATA.forEach(function(n) { NODE_POS[n.id] = {x: n.x, y: n.y}; });

var BROWSE_NODE_IDS = (function() {
  var ids = {};
  NODES_DATA.forEach(function(n) {
    var tip = n.title ? n.title.split('.').pop().toLowerCase() : '';
    if (tip === 'browse' || tip === 'browsev2') ids[n.id] = true;
  });
  return ids;
}());

// ── vis-network setup ─────────────────────────────────────────────────────
var network = null;
var nodesDataset = null;
var edgesDataset = null;

// ── Clustering constants ──────────────────────────────────────────────────
var MIN_CLUSTER_SIZE = 2;  // minimum nodes to form a type-based cluster
var BOX_PAD_X        = 72; // horizontal padding from node center (expanded cluster box)
var BOX_PAD_Y        = 36; // vertical padding from node center
var BOX_RADIUS       = 14; // corner radius of the rounded rectangle

// ── Container drawing constants ───────────────────────────────────────────
var CONT_PAD_X          = 60; // horizontal padding around container boundary box
var CONT_PAD_Y          = 36; // vertical padding around container boundary box
var CONT_R              = 10; // corner radius of container boundary box
var CONTAINER_BOUNDARY_PAD = 8; // tolerance for nodes on/near the container boundary
var HANDLE_HIT_PX          = 10; // resize handle hit radius in DOM pixels

// ── Focus / zoom constants ────────────────────────────────────────────────
var FOCUS_SCALE = 0.9; // unified zoom level for focusNode / search / container focus

// ── Minimap constants ─────────────────────────────────────────────────────
var MINIMAP_GRAPH_PAD = 80;   // padding added around graph bounding box in minimap
var MINIMAP_FIT       = 0.92; // scale factor to leave a small margin inside minimap canvas
var _focusedContainerIdx   = null; // index into CONTAINERS_DATA, or null
var _containerBounds       = [];   // [{x1,y1,x2,y2}] updated each beforeDrawing frame
var _containerDragState    = null; // active container drag, or null
// Returns '#000000' or '#ffffff' — whichever has higher WCAG contrast against hex.
function contrastColor(hex) {
  if (!hex || hex.length < 7) return '#ffffff';
  var r = parseInt(hex.slice(1,3), 16) / 255;
  var g = parseInt(hex.slice(3,5), 16) / 255;
  var b = parseInt(hex.slice(5,7), 16) / 255;
  function lin(c) { return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  var L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return L > 0.179 ? '#000000' : '#ffffff';
}

// ── Cluster color palette ─────────────────────────────────────────────────
// type = same-type BFS cluster (purple); container = ToolContainer group (red).
var CLUSTER_STYLE = {
  type: {
    normal: {background:'#4c1d95', border:'#7c3aed',
             highlight:{background:'#92400e', border:'#f59e0b'},
             hover:    {background:'#5b21b6', border:'#7c3aed'}},
    dim:    {background:'#2e1065', border:'#4c1d95'},
    matchBg: '#5b21b6',
    stroke: '#7c3aed', fill: 'rgba(109,40,217,0.07)', label: '#a78bfa',
  },
  container: {
    normal: {background:'#7f1d1d', border:'#ef4444',
             highlight:{background:'#92400e', border:'#f59e0b'},
             hover:    {background:'#991b1b', border:'#ef4444'}},
    dim:    {background:'#450a0a', border:'#7f1d1d'},
    matchBg: '#991b1b',
    stroke: '#ef4444', fill: 'rgba(239,68,68,0.07)', label: '#fca5a5',
  },
};

// ── Application state ─────────────────────────────────────────────────────
var AppState = {
  // Cluster state
  clusterMap: {},         // { 'cluster:N' | 'container:N': { memberIds, toolType, bridgeEdgeIds, isContainer } }
  expandedGroups: {},     // nodeId -> groupKey (nodes expanded from a cluster)
  groupMembers: {},       // groupKey -> { memberIds, toolType, isContainer, containerNodeId }
  clusterCounter: 0,
  clusteredContainerIdx: {}, // CONTAINERS_DATA index -> true, for containers that formed a cluster node
  // Memo state
  memoCounter: 0,
  memoData: {},           // 'memo:N' -> {text, x, y}
  memoEdges: {},          // edgeId  -> {from, to}
  memoEditTarget: null,   // memoId being edited, or null = new memo
  memoPendingPos: null,   // {x,y} for new memo placement
  connectMode: false,     // true while waiting for user to click a target node
  connectSourceId: null,  // memo ID initiating the connection
  memoHandles: {},        // memoId -> {x,y} bottom-right corner in canvas coords (updated each afterDrawing)
  resizeState: null,      // {memoId, startDomX, startDomY, startW, startH} while drag-resizing
};

function clusterMinLayer(id) {
  if (typeof id !== 'string' || id.indexOf('cluster:') !== 0) {
    return NODE_LAYER[id] !== undefined ? NODE_LAYER[id] : Infinity;
  }
  var meta = AppState.clusterMap[id];
  if (!meta) return Infinity;
  return meta.memberIds.reduce(function(min, memberId) {
    return Math.min(min, clusterMinLayer(memberId));
  }, Infinity);
}

function clusterAnchorPosition(id) {
  if (typeof id !== 'string' || id.indexOf('cluster:') !== 0) {
    return NODE_POS[id] || {x: 0, y: 0};
  }
  var meta = AppState.clusterMap[id];
  if (!meta || meta.memberIds.length === 0) return {x: 0, y: 0};
  var positions = meta.memberIds.map(clusterAnchorPosition);
  return positions.reduce(function(total, position) {
    return {x: total.x + position.x, y: total.y + position.y};
  }, {x: 0, y: 0});
}

function memberPosition(id) {
  var position = clusterAnchorPosition(id);
  if (typeof id !== 'string' || id.indexOf('cluster:') !== 0) return position;
  var count = AppState.clusterMap[id].memberIds.length;
  return {x: position.x / count, y: position.y / count};
}

function compareNumber(a, b) {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

function sortedMemberIds(ids) {
  return ids.slice().sort(function(a, b) {
    var layerOrder = compareNumber(clusterMinLayer(a), clusterMinLayer(b));
    if (layerOrder !== 0) return layerOrder;
    var aPosition = memberPosition(a);
    var bPosition = memberPosition(b);
    var yOrder = compareNumber(aPosition.y, bPosition.y);
    if (yOrder !== 0) return yOrder;
    var xOrder = compareNumber(aPosition.x, bPosition.x);
    if (xOrder !== 0) return xOrder;
    return String(a).localeCompare(String(b), undefined, {numeric: true});
  });
}
var MEMO_STORAGE_KEY           = 'yxray-memos-'           + (document.title || 'default');
var CONTAINER_ORDER_KEY        = 'yxray-container-order-' + (document.title || 'default');

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
// Both share AppState.clusterMap, AppState.expandedGroups, AppState.groupMembers, AppState.clusterCounter.

// Build an undirected adjacency map from a node list and an edge list.
// Returns { nodeId: [neighborId, ...] } for both edge directions.
function buildAdjacencyMap(nodes, edges) {
  var adjMap = {};
  nodes.forEach(function(n) { adjMap[n.id] = []; });
  edges.forEach(function(e) {
    if (!adjMap[e.from]) adjMap[e.from] = [];
    if (!adjMap[e.to])   adjMap[e.to]   = [];
    adjMap[e.from].push(e.to);
    adjMap[e.to].push(e.from);
  });
  return adjMap;
}

function buildClusters(skipSet) {
  skipSet = skipSet || {};

  // ── Phase 1: BFS over undirected adjacency to find same-type components ──
  // Use undirected adjacency so that fan-in patterns (multiple same-type nodes
  // flowing into a single node of the same type) are treated as connected.
  var adjMap = buildAdjacencyMap(NODES_DATA, EDGES_DATA);

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
    c.cid = 'cluster:' + (++AppState.clusterCounter);
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
      title: c.toolType + ' cluster — Click to expand/collapse',
      shape: 'box',
      borderDashes: [5, 3],
      x: cPos.x, y: cPos.y,
      color: {
        background: '#4c1d95', border: '#7c3aed',
        highlight: {background: '#92400e', border: '#f59e0b'},
        hover: {background: '#5b21b6', border: '#7c3aed'}
      },
      font: {color: contrastColor('#4c1d95'), size: 13}
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
    var newEid = (src === e.from && dst === e.to) ? e.id : 'br:' + (++AppState.clusterCounter);
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
    AppState.clusterMap[c.cid] = {
      memberIds: sortedMemberIds(c.chain),
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
// Result is cached after the first call — membership is stable for the lifetime of the page.
var _containerMembershipCache = null;
function computeContainerMembership() {
  if (_containerMembershipCache) return _containerMembershipCache;
  var result = {};
  if (CONTAINERS_DATA.length === 0) { _containerMembershipCache = result; return result; }
  NODES_DATA.forEach(function(n) {
    var bestIdx = -1, bestArea = Infinity;
    CONTAINERS_DATA.forEach(function(c, idx) {
      if (n.x >= c.x - CONTAINER_BOUNDARY_PAD && n.x <= c.x + c.w + CONTAINER_BOUNDARY_PAD &&
          n.y >= c.y - CONTAINER_BOUNDARY_PAD && n.y <= c.y + c.h + CONTAINER_BOUNDARY_PAD) {
        var area = c.w * c.h;
        if (area < bestArea) { bestArea = area; bestIdx = idx; }
      }
    });
    if (bestIdx >= 0) result[n.id] = bestIdx;
  });
  _containerMembershipCache = result;
  return result;
}

// ── Fill color helpers ────────────────────────────────────────────────────
// Used by container cluster nodes to reflect their Alteryx fill color.

function _isNearWhiteOrGray(hex) {
  // Returns true for white-ish or low-saturation bright colors that are
  // hard to distinguish from the canvas background → fallback to default red.
  if (!hex || hex.length < 7) return true;
  var r = parseInt(hex.slice(1,3), 16);
  var g = parseInt(hex.slice(3,5), 16);
  var b = parseInt(hex.slice(5,7), 16);
  if (r > 215 && g > 215 && b > 215) return true;  // near-white
  var mx = Math.max(r,g,b), mn = Math.min(r,g,b);
  return (mx - mn < 25 && mx > 160);  // low-saturation gray
}

function _darkenHex(hex, pct) {
  var f = 1 - pct / 100;
  var r = Math.round(parseInt(hex.slice(1,3), 16) * f);
  var g = Math.round(parseInt(hex.slice(3,5), 16) * f);
  var b = Math.round(parseInt(hex.slice(5,7), 16) * f);
  return '#' + ('00'+r.toString(16)).slice(-2) +
               ('00'+g.toString(16)).slice(-2) +
               ('00'+b.toString(16)).slice(-2);
}

function _containerNodeStyle(fillHex) {
  // Returns {color, fontColor} for a container cluster node.
  // Falls back to default red if fill is null / near-white / near-gray.
  if (!fillHex || _isNearWhiteOrGray(fillHex)) {
    return {color: CLUSTER_STYLE.container.normal, fontColor: contrastColor('#7f1d1d')};
  }
  var dark = _darkenHex(fillHex, 20);
  return {
    color: {
      background: fillHex,  border: dark,
      highlight: {background: '#92400e', border: '#f59e0b'},
      hover:     {background: _darkenHex(fillHex, 8), border: dark}
    },
    fontColor: contrastColor(fillHex)
  };
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
    var memberIds = sortedMemberIds(groups[parseInt(idx)]);
    if (memberIds.length < MIN_CLUSTER_SIZE) return;
    var c = CONTAINERS_DATA[parseInt(idx)];
    var clusterId = 'container:' + (++AppState.clusterCounter);
    var caption = c.label || ('Container ' + idx);
    AppState.clusteredContainerIdx[parseInt(idx)] = true;  // mark this container as clustered
    var label = caption + ' \xd7' + memberIds.length;
    memberIds.forEach(function(mid) { memberToCluster[mid] = clusterId; });
    clusterDefs.push({ cid: clusterId, memberIds: memberIds, caption: caption, label: label, fillColor: c.fillColor || null });
  });

  if (clusterDefs.length === 0) return;

  // Remove member nodes/clusters from DataSet
  var allMemberIds = [];
  clusterDefs.forEach(function(c) { allMemberIds = allMemberIds.concat(c.memberIds); });
  nodesDataset.remove(allMemberIds);

  // Add container cluster nodes (color from Alteryx fill, or red fallback)
  clusterDefs.forEach(function(c) {
    var pos = centroid(c.memberIds);
    var ns = _containerNodeStyle(c.fillColor);
    nodesDataset.add({
      id: c.cid, label: c.label,
      title: c.caption + ' — Click to expand/collapse',
      shape: 'box', borderDashes: [5, 3],
      x: pos.x, y: pos.y,
      color: ns.color,
      font: {color: ns.fontColor, size: 13}
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
      var eid = 'br:' + (++AppState.clusterCounter);
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

  // Store metadata (including fill color for later re-collapse and search restore)
  clusterDefs.forEach(function(c) {
    var ns = _containerNodeStyle(c.fillColor);
    AppState.clusterMap[c.cid] = {
      memberIds: c.memberIds, toolType: c.caption,
      bridgeEdgeIds: clusterBridges[c.cid] || [],
      isContainer: true,
      fillColorHex: c.fillColor || null,
      fontColorHex: ns.fontColor,
    };
  });
}

// Returns the node ID (or cluster ID) currently representing nodeId in the
// DataSet. Returns null if nodeId is not reachable (removed and unclustered).
function resolveNode(nodeId) {
  if (nodesDataset.get(nodeId) !== null) return nodeId;
  for (var cid in AppState.clusterMap) {
    if (AppState.clusterMap[cid].memberIds.indexOf(nodeId) !== -1) return cid;
  }
  return null;
}

// Re-collapse a previously expanded cluster. groupKey is the original cluster ID
// (e.g. 'cluster:1'). Any member node's double-click triggers this.
function recollapseGroup(groupKey) {
  var group = AppState.groupMembers[groupKey];
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

  // Re-add cluster node with appropriate colors
  var isContainer = group.isContainer || false;
  var clusterTitle = isContainer
    ? group.toolType + ' \u2014 Click to expand/collapse'
    : group.toolType + ' cluster \u2014 Click to expand/collapse';
  var cPos = centroid(group.memberIds);
  var ns = isContainer
    ? _containerNodeStyle(group.fillColorHex || null)
    : {color: CLUSTER_STYLE.type.normal, fontColor: contrastColor('#4c1d95')};
  nodesDataset.add({
    id: groupKey,
    label: group.toolType + ' \xd7' + group.memberIds.length,
    title: clusterTitle,
    shape: 'box',
    borderDashes: [5, 3],
    x: cPos.x, y: cPos.y,
    color: ns.color,
    font: {color: ns.fontColor, size: 13}
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
    var newEid = 'br:' + (++AppState.clusterCounter);
    edgesDataset.add({id: newEid, from: src, to: dst});
    bridgeEdgeIds.push(newEid);
    if (typeof dst === 'string' && dst.indexOf('cluster:') === 0 && AppState.clusterMap[dst]) {
      AppState.clusterMap[dst].bridgeEdgeIds.push(newEid);
    }
    if (typeof src === 'string' && src.indexOf('cluster:') === 0 && AppState.clusterMap[src]) {
      AppState.clusterMap[src].bridgeEdgeIds.push(newEid);
    }
  });

  // Restore cluster state
  AppState.clusterMap[groupKey] = {
    memberIds: group.memberIds,
    toolType: group.toolType,
    bridgeEdgeIds: bridgeEdgeIds,
    isContainer: group.isContainer || false,
    containerNodeId: group.containerNodeId,
    fillColorHex: group.fillColorHex || null,
    fontColorHex: group.fontColorHex || (group.isContainer ? contrastColor('#7f1d1d') : contrastColor('#4c1d95')),
  };

  // Clean up expanded state
  group.memberIds.forEach(function(mid) { delete AppState.expandedGroups[mid]; });
  delete AppState.groupMembers[groupKey];

  var cPos = centroid(group.memberIds);
  network.moveTo({position: cPos, animation: {duration: 300, easingFunction: 'easeInOutQuad'}});

  // Re-apply search so the newly restored cluster node is highlighted/dimmed correctly.
  if (searchActive) {
    var q = document.getElementById('search-input').value;
    if (q) doSearch(q, true, true);
  }
}

function expandCluster(cid) {
  var c = AppState.clusterMap[cid];
  if (!c) return;

  // Remove cluster node + its bridge edges
  nodesDataset.remove(cid);
  edgesDataset.remove(c.bridgeEdgeIds);

  // Restore member nodes with current theme colors
  var col = nodeColors();
  c.memberIds.forEach(function(mid) {
    var orig = NODES_DATA.find(function(n) { return n.id === mid; });
    if (!orig) return;
    var nodeColor, fontColor;
    if (BROWSE_NODE_IDS[mid]) {
      var bc = browseNodeColor();
      nodeColor = bc;
      fontColor = contrastColor(bc.background);
    } else {
      nodeColor = {background: col.bg, border: col.bd,
              highlight: {background: '#92400e', border: '#f59e0b'},
              hover: {background: col.hover, border: col.bd}};
      fontColor = contrastColor(col.bg);
    }
    nodesDataset.add({
      id: orig.id, label: orig.label, title: orig.title, shape: 'box',
      x: orig.x, y: orig.y,
      color: nodeColor,
      font: {color: fontColor}
    });
  });

  // Record expanded group so the user can double-click any member to re-collapse
  var expandedMemberIds = c.memberIds.slice();
  var expandedToolType = c.toolType;
  var expandedIsContainer = c.isContainer || false;
  var expandedContainerNodeId = c.containerNodeId;
  var expandedFillColorHex = c.fillColorHex || null;
  var expandedFontColorHex = c.fontColorHex || (c.isContainer ? contrastColor('#7f1d1d') : contrastColor('#4c1d95'));
  delete AppState.clusterMap[cid];
  AppState.groupMembers[cid] = {
    memberIds: expandedMemberIds,
    toolType: expandedToolType,
    isContainer: expandedIsContainer,
    containerNodeId: expandedContainerNodeId,
    fillColorHex: expandedFillColorHex,
    fontColorHex: expandedFontColorHex,
  };
  expandedMemberIds.forEach(function(mid) { AppState.expandedGroups[mid] = cid; });

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

    var newEid = (src === e.from && dst === e.to) ? e.id : 'br:' + (++AppState.clusterCounter);
    edgesDataset.add({id: newEid, from: src, to: dst});

    // Register the new bridge edge in any cluster it touches, so a subsequent
    // expandCluster() call can clean it up correctly.
    if (typeof dst === 'string' && dst.indexOf('cluster:') === 0 && AppState.clusterMap[dst]) {
      AppState.clusterMap[dst].bridgeEdgeIds.push(newEid);
    }
    if (typeof src === 'string' && src.indexOf('cluster:') === 0 && AppState.clusterMap[src]) {
      AppState.clusterMap[src].bridgeEdgeIds.push(newEid);
    }
  });

  // Re-apply search highlights to the newly visible member nodes.
  if (searchActive) {
    var q = document.getElementById('search-input').value;
    if (q) {
      doSearch(q, true, true);
      if (focusFirstVisibleSearchMatch(q, expandedMemberIds)) return;
    }
  }

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
    font: {color: '#000000', size: 13},
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
  Object.keys(AppState.memoData).forEach(function(id) {
    var pos = network.getPositions([id])[id];
    if (pos) { AppState.memoData[id].x = pos.x; AppState.memoData[id].y = pos.y; }
  });
  var edgeArr = Object.keys(AppState.memoEdges).map(function(eid) { return AppState.memoEdges[eid]; });
  try {
    localStorage.setItem(MEMO_STORAGE_KEY, JSON.stringify({nodes: AppState.memoData, edges: edgeArr}));
  } catch(e) {
    console.warn('[yxray] memo save failed:', e);
  }
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
        if (numMatch) { var n = parseInt(numMatch[1]); if (n > AppState.memoCounter) AppState.memoCounter = n; }
        AppState.memoData[id] = m;
        nodesDataset.add(_memoNodeDef(id, m.text, m.x, m.y, m.w, m.h));
      });
    }
    if (saved.edges) {
      saved.edges.forEach(function(e) {
        var eid = 'memo-edge:' + (++AppState.memoCounter);
        edgesDataset.add({id: eid, from: e.from, to: e.to,
          color: {color: '#ca8a04', highlight: '#a16207', hover: '#a16207'}, width: 1.5});
        AppState.memoEdges[eid] = {from: e.from, to: e.to};
      });
    }
  } catch(e) {
    console.warn('[yxray] memo load failed:', e);
  }
}

// ── Container order persistence ───────────────────────────────────────────
function saveContainerOrder() {
  var body = document.getElementById('containers-panel-body');
  if (!body) return;
  var order = Array.from(body.querySelectorAll('.container-row')).map(function(el) {
    return el.getAttribute('data-label');
  });
  try {
    localStorage.setItem(CONTAINER_ORDER_KEY, JSON.stringify(order));
  } catch(e) {
    console.warn('[yxray] container order save failed:', e);
  }
}

function loadContainerOrder() {
  var body = document.getElementById('containers-panel-body');
  if (!body) return;
  try {
    var raw = localStorage.getItem(CONTAINER_ORDER_KEY);
    if (!raw) return;
    var order = JSON.parse(raw);
    if (!Array.isArray(order)) return;
    var rows = Array.from(body.querySelectorAll('.container-row'));
    // Use arrays to handle duplicate labels without losing rows.
    var rowMap = {};
    rows.forEach(function(el) {
      var lbl = el.getAttribute('data-label');
      if (!rowMap[lbl]) rowMap[lbl] = [];
      rowMap[lbl].push(el);
    });
    // Re-append in saved order; duplicate labels consume from the front of each array.
    var placedSet = new Set();
    order.forEach(function(label) {
      if (rowMap[label] && rowMap[label].length > 0) {
        var el = rowMap[label].shift();
        body.appendChild(el);
        placedSet.add(el);
      }
    });
    // Append any rows not covered by saved order (new containers or leftover duplicates).
    rows.forEach(function(el) {
      if (!placedSet.has(el)) body.appendChild(el);
    });
  } catch(e) {
    console.warn('[yxray] container order load failed:', e);
  }
}

// ── Container row drag-to-reorder ─────────────────────────────────────────
(function() {
  var body = document.getElementById('containers-panel-body');
  if (!body) return;
  var dragSrc = null;

  body.addEventListener('dragstart', function(e) {
    var row = e.target.closest('.container-row');
    if (!row) return;
    dragSrc = row;
    row.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });

  function clearDragIndicators() {
    body.querySelectorAll('.drag-over-top, .drag-over-bottom').forEach(function(el) {
      el.classList.remove('drag-over-top', 'drag-over-bottom');
    });
  }

  function isAfterMidpoint(e, el) {
    var rect = el.getBoundingClientRect();
    return e.clientY > rect.top + rect.height / 2;
  }

  body.addEventListener('dragend', function(e) {
    var row = e.target.closest('.container-row');
    if (row) row.classList.remove('dragging');
    clearDragIndicators();
    dragSrc = null;
  });

  body.addEventListener('dragover', function(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    var row = e.target.closest('.container-row');
    clearDragIndicators();
    if (row && row !== dragSrc) {
      row.classList.add(isAfterMidpoint(e, row) ? 'drag-over-bottom' : 'drag-over-top');
    }
  });

  body.addEventListener('drop', function(e) {
    e.preventDefault();
    var target = e.target.closest('.container-row');
    if (!target || !dragSrc || target === dragSrc) return;
    clearDragIndicators();
    if (isAfterMidpoint(e, target)) {
      body.insertBefore(dragSrc, target.nextSibling);  // null → appendChild 相当
    } else {
      body.insertBefore(dragSrc, target);
    }
    saveContainerOrder();
  });
})();

function openMemoModal(targetId, x, y) {
  AppState.memoEditTarget = targetId;
  AppState.memoPendingPos = (x !== undefined && y !== undefined) ? {x: x, y: y} : null;
  var isNew = (targetId === null);
  document.getElementById('memo-modal-title').textContent = isNew ? 'New Memo' : 'Edit Memo';
  document.getElementById('memo-textarea').value = isNew ? '' : (AppState.memoData[targetId] ? AppState.memoData[targetId].text : '');
  document.getElementById('memo-delete-btn').style.display = isNew ? 'none' : '';
  document.getElementById('memo-modal').classList.add('open');
  document.getElementById('memo-modal-overlay').classList.add('open');
  setTimeout(function() { document.getElementById('memo-textarea').focus(); }, 50);
}

function closeMemoModal() {
  document.getElementById('memo-modal').classList.remove('open');
  document.getElementById('memo-modal-overlay').classList.remove('open');
  AppState.memoEditTarget = null;
  AppState.memoPendingPos = null;
}

function saveMemoFromModal() {
  var text = document.getElementById('memo-textarea').value.trim() || '(memo)';
  if (AppState.memoEditTarget === null) {
    var id = 'memo:' + (++AppState.memoCounter);
    var pos = AppState.memoPendingPos || {x: 0, y: 0};
    AppState.memoData[id] = {text: text, x: pos.x, y: pos.y};
    nodesDataset.add(_memoNodeDef(id, text, pos.x, pos.y));
  } else {
    if (AppState.memoData[AppState.memoEditTarget]) AppState.memoData[AppState.memoEditTarget].text = text;
    nodesDataset.update({id: AppState.memoEditTarget, label: text});
  }
  saveMemos();
  closeMemoModal();
}

function deleteMemoNode(memoId) {
  var toRemove = Object.keys(AppState.memoEdges).filter(function(eid) {
    return AppState.memoEdges[eid].from === memoId || AppState.memoEdges[eid].to === memoId;
  });
  edgesDataset.remove(toRemove);
  toRemove.forEach(function(eid) { delete AppState.memoEdges[eid]; });
  nodesDataset.remove(memoId);
  delete AppState.memoData[memoId];
  saveMemos();
}

function enterConnectMode(fromId) {
  AppState.connectMode = true;
  AppState.connectSourceId = fromId;
  document.getElementById('graph-canvas').style.cursor = 'crosshair';
  document.getElementById('connect-mode-hint').style.display = 'block';
}

function exitConnectMode() {
  AppState.connectMode = false;
  AppState.connectSourceId = null;
  var cv = document.getElementById('graph-canvas');
  if (cv && !cv._memoResizeCursor) cv.style.cursor = '';
  document.getElementById('connect-mode-hint').style.display = 'none';
}

// ── Minimap ───────────────────────────────────────────────────────────────
function closeMinimapPanel() {
  document.getElementById('minimap-wrap').style.display = 'none';
  document.getElementById('minimap-reopen').style.display = 'block';
}
function openMinimapPanel() {
  document.getElementById('minimap-wrap').style.display = '';
  document.getElementById('minimap-reopen').style.display = 'none';
}

function drawMinimap() {
  var mc = document.getElementById('minimap-canvas');
  if (!mc || !network || !nodesDataset) return;
  var mCtx = mc.getContext('2d');
  var mW = mc.width;
  var mH = mc.height;

  // Bounding box from original data node positions (stable; falls back to
  // stored x/y for nodes that are currently collapsed inside a cluster).
  var positions = network.getPositions(NODES_DATA.map(function(nd) { return nd.id; }));
  var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  NODES_DATA.forEach(function(nd) {
    var p = positions[nd.id] || {x: nd.x, y: nd.y};
    minX = Math.min(minX, p.x); minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y);
  });
  if (!isFinite(minX)) return;

  minX -= MINIMAP_GRAPH_PAD; minY -= MINIMAP_GRAPH_PAD;
  maxX += MINIMAP_GRAPH_PAD; maxY += MINIMAP_GRAPH_PAD;
  var graphW = maxX - minX;
  var graphH = maxY - minY;
  if (graphW <= 0 || graphH <= 0) return;

  // Fit the graph inside the minimap canvas while preserving aspect ratio.
  var s = Math.min(mW / graphW, mH / graphH) * MINIMAP_FIT;
  var offX = (mW - graphW * s) / 2;
  var offY = (mH - graphH * s) / 2;
  function gx(x) { return (x - minX) * s + offX; }
  function gy(y) { return (y - minY) * s + offY; }

  // Background
  mCtx.clearRect(0, 0, mW, mH);
  mCtx.fillStyle = isDark ? 'rgba(15,23,42,0.94)' : 'rgba(248,250,252,0.94)';
  mCtx.fillRect(0, 0, mW, mH);

  // Edges — use stored x/y for nodes collapsed inside clusters.
  mCtx.strokeStyle = isDark ? 'rgba(71,85,105,0.55)' : 'rgba(148,163,184,0.65)';
  mCtx.lineWidth = 0.5;
  EDGES_DATA.forEach(function(edge) {
    var fp = positions[edge.from] || (function() { var nd = NODES_DATA.find(function(n){return n.id===edge.from;}); return nd ? {x:nd.x,y:nd.y} : null; })();
    var tp = positions[edge.to]   || (function() { var nd = NODES_DATA.find(function(n){return n.id===edge.to;});   return nd ? {x:nd.x,y:nd.y} : null; })();
    if (!fp || !tp) return;
    mCtx.beginPath();
    mCtx.moveTo(gx(fp.x), gy(fp.y));
    mCtx.lineTo(gx(tp.x), gy(tp.y));
    mCtx.stroke();
  });

  // ── Layer 1: Viewport rectangle (drawn first so focus glows render on top) ──
  var scale = network.getScale();
  var vp = network.getViewPosition();
  var mainC = network.canvas.frame.canvas;
  var vW = mainC.clientWidth / scale;
  var vH = mainC.clientHeight / scale;
  var rX = gx(vp.x - vW / 2);
  var rY = gy(vp.y - vH / 2);
  var rW = vW * s;
  var rH = vH * s;
  mCtx.fillStyle = isDark ? 'rgba(148,163,184,0.07)' : 'rgba(15,23,42,0.05)';
  mCtx.fillRect(rX, rY, rW, rH);
  mCtx.strokeStyle = isDark ? 'rgba(148,163,184,0.7)' : 'rgba(71,85,105,0.65)';
  mCtx.lineWidth = 1.2;
  mCtx.strokeRect(rX, rY, rW, rH);

  // ── Layer 2: All nodes — neutral/dim ─────────────────────────────────────
  var focusedId = typeof _focusHighlightId !== 'undefined' ? _focusHighlightId : null;
  var dimColor = isDark ? 'rgba(148,163,184,0.45)' : 'rgba(100,116,139,0.45)';

  nodesDataset.getIds().forEach(function(id) {
    if (typeof id !== 'string') return;
    if (id.indexOf('memo:') === 0) return;
    var p = network.getPosition(id);
    if (!p) return;
    mCtx.beginPath();
    mCtx.arc(gx(p.x), gy(p.y), 3, 0, Math.PI * 2);
    mCtx.fillStyle = dimColor;
    mCtx.fill();
  });
  NODES_DATA.forEach(function(nd) {
    var p = positions[nd.id] || {x: nd.x, y: nd.y};
    mCtx.beginPath();
    mCtx.arc(gx(p.x), gy(p.y), 2.5, 0, Math.PI * 2);
    mCtx.fillStyle = dimColor;
    mCtx.fill();
  });

  // ── Layer 3: Focused indicator (always on top) ───────────────────────────
  if (focusedId !== null) {
    var fp2 = positions[focusedId] || (function() {
      var nd = NODES_DATA.find(function(n) { return n.id === focusedId; });
      return nd ? {x: nd.x, y: nd.y} : null;
    })();
    if (fp2) {
      mCtx.save();
      mCtx.beginPath();
      mCtx.arc(gx(fp2.x), gy(fp2.y), 8, 0, Math.PI * 2);
      mCtx.fillStyle = 'rgba(251,191,36,0.2)';
      mCtx.shadowColor = 'rgba(251,191,36,0.9)';
      mCtx.shadowBlur = 12;
      mCtx.fill();
      mCtx.beginPath();
      mCtx.arc(gx(fp2.x), gy(fp2.y), 5, 0, Math.PI * 2);
      mCtx.fillStyle = '#fbbf24';
      mCtx.shadowBlur = 10;
      mCtx.fill();
      mCtx.shadowBlur = 0;
      mCtx.strokeStyle = 'rgba(255,255,255,0.9)';
      mCtx.lineWidth = 1.5;
      mCtx.stroke();
      mCtx.restore();
    }
  }

  if (_focusedContainerIdx !== null && CONTAINERS_DATA[_focusedContainerIdx]) {
    var cd = CONTAINERS_DATA[_focusedContainerIdx];
    mCtx.save();
    mCtx.strokeStyle = '#f59e0b';
    mCtx.lineWidth = 2;
    mCtx.shadowColor = 'rgba(245,158,11,0.9)';
    mCtx.shadowBlur = 10;
    mCtx.setLineDash([4, 3]);
    mCtx.strokeRect(gx(cd.x), gy(cd.y), cd.w * s, cd.h * s);
    mCtx.restore();
  }
}

// ── Network init ──────────────────────────────────────────────────────────
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
  network.on('beforeDrawing', function(ctx) {
    if (CONTAINERS_DATA.length === 0) return;
    _containerBounds = new Array(CONTAINERS_DATA.length);
    ctx.save();

    CONTAINERS_DATA.forEach(function(c, idx) {
      // 1. Find original node IDs whose initial position falls inside this container.
      //    Using initial positions (NODES_DATA) so membership is stable.
      var memberIds = [];
      NODES_DATA.forEach(function(nd) {
        if (nd.x >= c.x - CONTAINER_BOUNDARY_PAD && nd.x <= c.x + c.w + CONTAINER_BOUNDARY_PAD &&
            nd.y >= c.y - CONTAINER_BOUNDARY_PAD && nd.y <= c.y + c.h + CONTAINER_BOUNDARY_PAD) {
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
      // Cache label hit area for container drag. Label is drawn at (x+10, y-6).
      if (c.label) {
        ctx.font = 'bold 24px system-ui,-apple-system,sans-serif';
        var tw = ctx.measureText(c.label).width;
        _containerBounds[idx] = {x1: x + 4, y1: y - 34, x2: x + 14 + tw, y2: y};
      }

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
      var focused = (idx === _focusedContainerIdx);
      ctx.fillStyle   = focused ? 'rgba(245,158,11,0.12)' : 'rgba(244,114,182,0.06)';
      ctx.fill();
      ctx.strokeStyle = focused ? '#f59e0b'               : 'rgba(244,114,182,0.65)';
      ctx.lineWidth   = focused ? 2.5                     : 1.5;
      ctx.setLineDash([8, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (c.label) {
        ctx.font = 'bold 24px system-ui,-apple-system,sans-serif';
        ctx.fillStyle = focused ? '#f59e0b' : 'rgba(249,168,212,0.95)';
        ctx.fillText(c.label, x + 10, y - 6);
      }
    });
    ctx.restore();
  });

  // ── Container label drag: grab the label text to move all members ──────────
  var _cvs = network.canvas.frame.canvas;

  function _findLabelAt(cp) {
    for (var i = _containerBounds.length - 1; i >= 0; i--) {
      var b = _containerBounds[i];
      if (!b) continue;
      if (cp.x >= b.x1 && cp.x <= b.x2 && cp.y >= b.y1 && cp.y <= b.y2) return i;
    }
    return -1;
  }

  function _onContainerDragMove(e) {
    if (!_containerDragState || (!e.movementX && !e.movementY)) return;
    var scale = network.getScale();
    var dx = e.movementX / scale;
    var dy = e.movementY / scale;
    var cur = _containerDragState.curPositions;
    nodesDataset.update(_containerDragState.reps.map(function(id) {
      var key = String(id);
      cur[key] = {x: cur[key].x + dx, y: cur[key].y + dy};
      return {id: id, x: cur[key].x, y: cur[key].y}; // original typed id
    }));
  }

  function _onContainerDragEnd() {
    _containerDragState = null;
    document.removeEventListener('mousemove', _onContainerDragMove);
    document.removeEventListener('mouseup', _onContainerDragEnd);
    _cvs.style.cursor = '';
  }

  // Attach to the frame div (parent of canvas) so stopPropagation fires
  // BEFORE vis-network's canvas-level handlers in the capture phase.
  var _frame = network.canvas.frame;
  var _canvasRect = null;
  _frame.addEventListener('mousedown', function(e) {
    if (e.button !== 0 || _containerDragState) return;
    _canvasRect = _cvs.getBoundingClientRect();
    var domX = e.clientX - _canvasRect.left;
    var domY = e.clientY - _canvasRect.top;
    var cp = network.DOMtoCanvas({x: domX, y: domY});
    var cidx = _findLabelAt(cp);
    if (cidx < 0) return;
    e.stopPropagation(); // prevents canvas from receiving event
    e.preventDefault();
    var membership = computeContainerMembership();
    // Collect reps preserving original ID types (numeric for regular nodes).
    var repsArr = [], repsKeySet = {};
    Object.keys(membership).forEach(function(k) {
      if (membership[parseInt(k)] === cidx) {
        var rep = resolveNode(parseInt(k));
        if (rep !== null) {
          var key = String(rep);
          if (!repsKeySet[key]) { repsKeySet[key] = true; repsArr.push(rep); }
        }
      }
    });
    var positions = network.getPositions(repsArr);
    var curPositions = {};
    repsArr.forEach(function(id) {
      var p = positions[id];
      curPositions[String(id)] = p ? {x: p.x, y: p.y} : {x: 0, y: 0};
    });
    _containerDragState = {cidx: cidx, reps: repsArr, curPositions: curPositions};
    _cvs.style.cursor = 'grabbing';
    document.addEventListener('mousemove', _onContainerDragMove);
    document.addEventListener('mouseup', _onContainerDragEnd);
  }, true);

  _cvs.addEventListener('mousemove', function(e) {
    if (_containerDragState) return;
    var cp = network.DOMtoCanvas({x: e.offsetX, y: e.offsetY});
    _cvs.style.cursor = _findLabelAt(cp) >= 0 ? 'grab' : '';
  });

  network.on('click', function(params) {
    // Connect mode: user clicks a target node to wire a memo edge
    if (AppState.connectMode) {
      if (params.nodes.length > 0) {
        var targetId = params.nodes[0];
        if (targetId !== AppState.connectSourceId) {
          var eid = 'memo-edge:' + (++AppState.memoCounter);
          edgesDataset.add({id: eid, from: AppState.connectSourceId, to: targetId,
            color: {color: '#ca8a04', highlight: '#a16207', hover: '#a16207'}, width: 1.5});
          AppState.memoEdges[eid] = {from: AppState.connectSourceId, to: targetId};
          saveMemos();
        }
      }
      exitConnectMode();
      return;
    }
    if (params.nodes.length === 0) { closePanel(); return; }
    openPanel(params.nodes[0]);
  });
  network.on('doubleClick', function(params) {
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

  // Single afterDrawing handler: cluster boxes, memo handles, file subtitles.
  // Consolidated from three separate listeners to reduce per-frame overhead.
  network.on('afterDrawing', function(ctx) {
    // 1. Draw rounded-rect border around each expanded cluster's member nodes.
    var groupKeys = Object.keys(AppState.groupMembers);
    if (groupKeys.length > 0) {
      ctx.save();
      groupKeys.forEach(function(groupKey) {
        var group = AppState.groupMembers[groupKey];
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

        ctx.fillStyle = bs.fill;
        ctx.fill();
        ctx.strokeStyle = bs.stroke;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([7, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = bs.label;
        ctx.font = 'bold 11px system-ui,-apple-system,sans-serif';
        ctx.fillText(group.toolType, x + 8, y - 5);
      });
      ctx.restore();
    }

    // 2. Memo resize handles + refresh AppState.memoHandles for hit-testing.
    AppState.memoHandles = {};
    Object.keys(AppState.memoData).forEach(function(memoId) {
      if (!nodesDataset.get(memoId)) return;
      var bb = network.getBoundingBox(memoId);
      if (!bb) return;
      AppState.memoHandles[memoId] = {x: bb.right, y: bb.bottom};
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

    // 3. File path subtitles below input/output nodes (not shown when clustered).
    NODES_DATA.forEach(function(nd) {
      if (!nd.subtitle) return;
      if (!nodesDataset.get(nd.id)) return;
      var bb = network.getBoundingBox(nd.id);
      if (!bb) return;
      var bsIdx = nd.subtitle.lastIndexOf(String.fromCharCode(92));
      var fsIdx = nd.subtitle.lastIndexOf('/');
      var sepIdx = Math.max(bsIdx, fsIdx);
      var text = sepIdx >= 0 ? nd.subtitle.slice(sepIdx + 1) : nd.subtitle;
      if (text.length > 30) text = '…' + text.slice(-27);
      ctx.save();
      ctx.font = '10px system-ui,-apple-system,sans-serif';
      ctx.fillStyle = isDark ? 'rgba(148,163,184,0.85)' : 'rgba(71,85,105,0.85)';
      ctx.textAlign = 'center';
      ctx.fillText(text, (bb.left + bb.right) / 2, bb.bottom + 16);
      ctx.restore();
    });

    // 4. Minimap overlay.
    drawMinimap();
  });

  // ── Memo resize drag (capture-phase so we intercept before vis-network) ──
  canvas.addEventListener('mousedown', function(e) {
    if (Object.keys(AppState.memoHandles).length === 0) return;
    var rect = canvas.getBoundingClientRect();
    var domX = e.clientX - rect.left;
    var domY = e.clientY - rect.top;
    var scale = network.getScale();
    var canvasPos = network.DOMtoCanvas({x: domX, y: domY});
    var hitR = HANDLE_HIT_PX / scale;
    var found = null;
    Object.keys(AppState.memoHandles).forEach(function(memoId) {
      var h = AppState.memoHandles[memoId];
      if (Math.abs(canvasPos.x - h.x) <= hitR && Math.abs(canvasPos.y - h.y) <= hitR) found = memoId;
    });
    if (!found) return;
    e.preventDefault();
    e.stopPropagation();
    var bb = network.getBoundingBox(found);
    AppState.resizeState = {
      memoId: found,
      startDomX: domX, startDomY: domY,
      startW: bb.right - bb.left,
      startH: bb.bottom - bb.top
    };
  }, true);  // capture phase

  // Cursor feedback when hovering over a resize handle
  canvas.addEventListener('mousemove', function(e) {
    if (AppState.resizeState || AppState.connectMode) return;
    if (Object.keys(AppState.memoHandles).length === 0) { return; }
    var rect = canvas.getBoundingClientRect();
    var domX = e.clientX - rect.left;
    var domY = e.clientY - rect.top;
    var scale = network.getScale();
    var canvasPos = network.DOMtoCanvas({x: domX, y: domY});
    var hitR = HANDLE_HIT_PX / scale;
    var onHandle = Object.keys(AppState.memoHandles).some(function(id) {
      var h = AppState.memoHandles[id];
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
    if (!AppState.resizeState) return;
    var rect = canvas.getBoundingClientRect();
    var dx = (e.clientX - rect.left) - AppState.resizeState.startDomX;
    var dy = (e.clientY - rect.top)  - AppState.resizeState.startDomY;
    var scale = network.getScale();
    var newW = Math.max(60, AppState.resizeState.startW + dx / scale);
    var newH = Math.max(28, AppState.resizeState.startH + dy / scale);
    nodesDataset.update({
      id: AppState.resizeState.memoId,
      widthConstraint:  {minimum: newW, maximum: newW},
      heightConstraint: {minimum: newH, maximum: newH}
    });
  });

  document.addEventListener('mouseup', function() {
    if (!AppState.resizeState) return;
    var rs = AppState.resizeState;
    AppState.resizeState = null;
    canvas.style.cursor = '';
    canvas._memoResizeCursor = false;
    var bb = network.getBoundingBox(rs.memoId);
    if (AppState.memoData[rs.memoId] && bb) {
      AppState.memoData[rs.memoId].w = bb.right - bb.left;
      AppState.memoData[rs.memoId].h = bb.bottom - bb.top;
      saveMemos();
    }
  });
}

try {
  initNetwork();
  loadContainerOrder();
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
// Shared render helper: builds Expand/Collapse button + member list for a cluster.
// Called from openPanel() and from within the buttons themselves so the panel
// stays open and its content flips between "Expand" and "Collapse" states.
function _refreshClusterPanel(groupKey) {
  _panelNodeId = groupKey;
  var body = document.getElementById('panel-body');
  body.innerHTML = '';
  if (AppState.clusterMap[groupKey]) {
    // Collapsed state → show Expand button
    var c = AppState.clusterMap[groupKey];
    document.getElementById('panel-title-text').textContent =
      c.toolType + ' \xd7' + c.memberIds.length + ' nodes';
    var expandBtn = document.createElement('button');
    expandBtn.className = 'ctrl-btn';
    expandBtn.style.cssText = 'display:block;width:100%;padding:7px;margin-bottom:14px;background:var(--accent);color:#fff;border-color:var(--accent);font-size:13px;';
    expandBtn.textContent = 'Expand';
    expandBtn.onclick = function() { expandCluster(groupKey); _refreshClusterPanel(groupKey); };
    body.appendChild(expandBtn);
    if (window._YXRAY_SQL_ENDPOINT) {
      var sqlBtn = document.createElement('button');
      sqlBtn.className = 'ctrl-btn';
      sqlBtn.style.cssText = 'display:block;width:100%;padding:7px;margin-bottom:14px;font-size:13px;';
      sqlBtn.textContent = '→ SQL';
      sqlBtn.onclick = (function(gk) { return function() { _exportClusterSQL(gk); }; })(groupKey);
      body.appendChild(sqlBtn);
    }
    // Select the cluster node so vis-network applies the amber highlight color
    if (network) network.selectNodes([groupKey]);
    c.memberIds.forEach(function(mid) {
      var entry = CONFIG_MAP[String(mid)];
      if (!entry) return;
      var hdr = document.createElement('div');
      hdr.className = 'cluster-member-header';
      hdr.textContent = entry.label;
      body.appendChild(hdr);
      renderConfigRows(entry, body);
    });
  } else if (AppState.groupMembers[groupKey]) {
    // Expanded state → show Collapse button
    var group = AppState.groupMembers[groupKey];
    document.getElementById('panel-title-text').textContent =
      group.toolType + ' \xd7' + group.memberIds.length + ' nodes';
    var collapseBtn = document.createElement('button');
    collapseBtn.className = 'ctrl-btn';
    collapseBtn.style.cssText = 'display:block;width:100%;padding:7px;margin-bottom:14px;font-size:13px;';
    collapseBtn.textContent = 'Collapse';
    collapseBtn.onclick = function() { recollapseGroup(groupKey); _refreshClusterPanel(groupKey); };
    body.appendChild(collapseBtn);
    if (window._YXRAY_SQL_ENDPOINT) {
      var sqlBtn2 = document.createElement('button');
      sqlBtn2.className = 'ctrl-btn';
      sqlBtn2.style.cssText = 'display:block;width:100%;padding:7px;margin-bottom:14px;font-size:13px;';
      sqlBtn2.textContent = '→ SQL';
      sqlBtn2.onclick = (function(gk) { return function() { _exportClusterSQL(gk); }; })(groupKey);
      body.appendChild(sqlBtn2);
    }
    if (network) network.selectNodes([]);
    group.memberIds.forEach(function(mid) {
      var entry = CONFIG_MAP[String(mid)];
      if (!entry) return;
      var hdr = document.createElement('div');
      hdr.className = 'cluster-member-header';
      hdr.textContent = entry.label;
      body.appendChild(hdr);
      renderConfigRows(entry, body);
    });
  }
  _setPanelBtn('excel');
  document.getElementById('config-panel').classList.add('open');
}

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

var _panelNodeId = null;

function _setPanelBtn(mode) {
  var btn = document.getElementById('panel-copy-btn');
  if (!btn) return;
  if (mode === 'excel') {
    btn.textContent = '↓ Excel';
    btn.dataset.mode = 'excel';
  } else {
    btn.textContent = 'Copy';
    btn.dataset.mode = 'copy';
  }
}

function openPanel(nodeId) {
  _panelNodeId = nodeId;
  _setPanelBtn('copy');
  var body = document.getElementById('panel-body');
  body.innerHTML = '';

  // Memo node — show editable memo panel
  if (typeof nodeId === 'string' && nodeId.indexOf('memo:') === 0) {
    var m = AppState.memoData[nodeId];
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

  // Cluster node (collapsed) — delegate to shared refresh helper
  if (AppState.clusterMap[nodeId]) {
    _refreshClusterPanel(nodeId);
    return;
  }

  // Expanded cluster member — show config + collapse button
  var _groupKey = AppState.expandedGroups[nodeId];
  if (_groupKey) {
    var _group = AppState.groupMembers[_groupKey];
    var _entry = CONFIG_MAP[String(nodeId)];
    document.getElementById('panel-title-text').textContent =
      _entry ? _entry.label : 'Node ' + nodeId;
    var collapseBtn = document.createElement('button');
    collapseBtn.className = 'ctrl-btn';
    collapseBtn.style.cssText = 'display:block;width:100%;padding:7px;margin-bottom:14px;font-size:13px;';
    collapseBtn.textContent = 'Collapse: ' + (_group ? _group.toolType : 'group');
    collapseBtn.onclick = (function(gk) { return function() { recollapseGroup(gk); _refreshClusterPanel(gk); }; })(_groupKey);
    body.appendChild(collapseBtn);
    if (_entry) renderConfigRows(_entry, body);
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
  _panelNodeId = null;
}

function downloadSummaryExcel() {
  var steps = (function() {
    var el = document.getElementById('summary-data');
    return el ? JSON.parse(el.textContent) : [];
  })();
  var insights = (function() {
    var el = document.getElementById('insights-data');
    return el ? JSON.parse(el.textContent) : [];
  })();

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function xmlRow(cells) {
    return '<Row>' + cells.map(function(c) {
      return '<Cell><Data ss:Type="String">' + esc(c) + '</Data></Cell>';
    }).join('') + '</Row>';
  }
  function xmlSheet(name, rows) {
    return '<Worksheet ss:Name="' + esc(name) + '"><Table>' +
      rows.map(xmlRow).join('') + '</Table></Worksheet>';
  }

  var hasChange = steps.some(function(s) { return s.change; });
  var summaryHeaders = ['#', 'Type', 'Category', 'Description'];
  if (hasChange) summaryHeaders.push('Change');
  var summaryRows = [summaryHeaders].concat(steps.map(function(s, i) {
    var r = [i + 1, s.short_type || '', s.category || '', s.description || ''];
    if (hasChange) r.push(s.change || '');
    return r;
  }));

  var inputRows = [['ID', 'Type', 'Description']].concat(
    insights.filter(function(d) { return d.role === 'input'; })
      .map(function(d) { return [d.tool_id || '', d.short_type || '', d.description || '']; })
  );
  var outputRows = [['ID', 'Type', 'Description']].concat(
    insights.filter(function(d) { return d.role === 'output'; })
      .map(function(d) { return [d.tool_id || '', d.short_type || '', d.description || '']; })
  );

  var containers = (function() {
    var el = document.getElementById('containers-data');
    return el ? JSON.parse(el.textContent) : [];
  })();
  var containerRows = [['#', 'Label']].concat(
    containers.map(function(c, i) { return [i + 1, c.label || '']; })
  );

  var sheets = xmlSheet('Summary', summaryRows) +
    xmlSheet('Input', inputRows) +
    xmlSheet('Output', outputRows);
  if (containers.length > 0) sheets += xmlSheet('Containers', containerRows);

  var xml = '<?xml version="1.0"?>\n<?mso-application progid="Excel.Sheet"?>\n' +
    '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ' +
    'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">' +
    sheets +
    '</Workbook>';

  var rawTitle = (document.querySelector('.header-title') || {}).textContent || 'workflow';
  var baseName = rawTitle.trim().replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9_\-.]/g, '_');
  var now = new Date();
  var ts = now.getFullYear().toString() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + '_' +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  var blob = new Blob([xml], {type: 'application/vnd.ms-excel'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'summary_' + baseName + '_' + ts + '.xls';
  document.body.appendChild(a);
  a.click();
  setTimeout(function() { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
}

function downloadClusterExcel() {
  var groupKey = _panelNodeId;
  var memberIds = [];
  if (AppState.clusterMap[groupKey]) {
    memberIds = AppState.clusterMap[groupKey].memberIds;
  } else if (AppState.groupMembers[groupKey]) {
    memberIds = AppState.groupMembers[groupKey].memberIds;
  }
  if (memberIds.length === 0) return;

  var toolType = ((AppState.clusterMap[groupKey] || AppState.groupMembers[groupKey]) || {}).toolType || 'cluster';

  var columns = memberIds.map(function(mid) {
    var entry = CONFIG_MAP[String(mid)];
    if (!entry) return ['Node ' + mid];
    var col = [entry.label];
    Object.keys(entry.config).forEach(function(k) {
      var v = entry.config[k];
      var valStr = (typeof v === 'object') ? JSON.stringify(v, null, 2) : String(v);
      valStr.split('\n').forEach(function(line, i) {
        col.push(i === 0 ? k + ': ' + line : '  ' + line);
      });
    });
    return col;
  });

  var maxLen = columns.reduce(function(m, c) { return Math.max(m, c.length); }, 0);
  columns.forEach(function(c) { while (c.length < maxLen) c.push(''); });

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  var rowsXml = '';
  for (var r = 0; r < maxLen; r++) {
    rowsXml += '<Row' + (r === 0 ? ' ss:Index="2"' : '') + '>';
    columns.forEach(function(col, c) {
      rowsXml += '<Cell' + (c === 0 ? ' ss:Index="2"' : '') + '><Data ss:Type="String">' + esc(col[r]) + '</Data></Cell>';
    });
    rowsXml += '</Row>';
  }

  var xml = '<?xml version="1.0"?>\n<?mso-application progid="Excel.Sheet"?>\n' +
    '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ' +
    'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">' +
    '<Worksheet ss:Name="Cluster"><Table>' + rowsXml + '</Table></Worksheet>' +
    '</Workbook>';

  var baseName = toolType.replace(/[^A-Za-z0-9_\-.]/g, '_');
  var now = new Date();
  var ts = now.getFullYear().toString() +
    String(now.getMonth() + 1).padStart(2, '0') +
    String(now.getDate()).padStart(2, '0') + '_' +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') +
    String(now.getSeconds()).padStart(2, '0');

  var blob = new Blob([xml], {type: 'application/vnd.ms-excel'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'cluster_' + baseName + '_' + ts + '.xls';
  document.body.appendChild(a);
  a.click();
  setTimeout(function() { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
}


function copyPanelContent() {
  var title = document.getElementById('panel-title-text').textContent.trim();
  var body = document.getElementById('panel-body');
  var lines = [title, ''];
  Array.prototype.forEach.call(body.children, function(node) {
    if (node.classList.contains('cluster-member-header')) {
      lines.push('── ' + node.textContent.trim() + ' ──');
      lines.push('');
    } else if (node.classList.contains('config-row')) {
      var key = node.querySelector('.config-key');
      var val = node.querySelector('.config-val');
      if (key && val) lines.push(key.textContent.trim() + ': ' + val.textContent.trim());
    } else if (node.classList.contains('config-val')) {
      lines.push(node.textContent.trim());
    }
  });
  var text = lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  var btn = document.getElementById('panel-copy-btn');
  function showFeedback(ok) {
    if (!btn) return;
    btn.textContent = ok ? 'Copied!' : 'Failed';
    btn.style.color = ok ? 'var(--accent)' : '#f87171';
    setTimeout(function() { btn.textContent = 'Copy'; btn.style.color = ''; }, 1500);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      function() { showFeedback(true); },
      function() { showFeedback(false); }
    );
  } else {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showFeedback(true); }
    catch(e) { showFeedback(false); }
    document.body.removeChild(ta);
  }
}

document.getElementById('panel-title-text').addEventListener('click', function() {
  if (_panelNodeId !== null && typeof focusNode === 'function') focusNode(_panelNodeId, null);
});
document.getElementById('panel-copy-btn').addEventListener('click', function() {
  var btn = document.getElementById('panel-copy-btn');
  if (btn && btn.dataset.mode === 'excel') downloadClusterExcel();
  else copyPanelContent();
});
document.getElementById('panel-close-btn').addEventListener('click', closePanel);
document.getElementById('panel-overlay').addEventListener('click', closePanel);
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    if (AppState.connectMode) { exitConnectMode(); return; }
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
  if (AppState.memoEditTarget) deleteMemoNode(AppState.memoEditTarget);
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
    hover: s.getPropertyValue('--node-hover').trim(),
  };
}

function browseNodeColor() {
  return isDark
    ? {background: '#334155', border: '#475569',
       highlight: {background: '#92400e', border: '#f59e0b'},
       hover: {background: '#475569', border: '#475569'}}
    : {background: '#94a3b8', border: '#64748b',
       highlight: {background: '#92400e', border: '#f59e0b'},
       hover: {background: '#cbd5e1', border: '#64748b'}};
}

// Returns the base (un-highlighted, un-dimmed) color update object for node n.
// col = nodeColors() result. Used by clearSearch and applyTheme.
function baseNodeColorUpdate(n, col) {
  if (AppState.clusterMap[n.id]) {
    var cm = AppState.clusterMap[n.id];
    if (cm.isContainer && cm.fillColorHex) {
      var ns = _containerNodeStyle(cm.fillColorHex);
      return {id: n.id, color: ns.color, font: {color: ns.fontColor}};
    }
    var cs = cm.isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
    return {id: n.id, color: cs.normal, font: {color: contrastColor(cs.normal.background)}};
  }
  if (typeof n.id === 'string' && n.id.indexOf('memo:') === 0) {
    return {id: n.id, font: {color: '#000000'}};
  }
  if (BROWSE_NODE_IDS[n.id]) {
    var bc = browseNodeColor();
    return {id: n.id, color: bc, font: {color: contrastColor(bc.background)}, shadow: false};
  }
  return {id: n.id, color: {
    background: col.bg, border: col.bd,
    highlight: {background: '#92400e', border: '#f59e0b'},
    hover: {background: col.hover, border: col.bd}
  }, font: {color: contrastColor(col.bg)}, shadow: false};
}

function buildNodeDataLookup() {
  var nodeDataLookup = {};
  NODES_DATA.forEach(function(nd) { nodeDataLookup[nd.id] = nd; });
  return nodeDataLookup;
}

function nodeMatchesSearch(nodeId, testStr, nodeDataLookup) {
  var nd = nodeDataLookup[nodeId];
  var configStr = JSON.stringify(CONFIG_MAP[nodeId] || {});
  return testStr(String(nodeId)) || testStr((nd && nd.label) || '') || testStr(configStr);
}

function visibleNodeMatchesSearch(node, testStr, nodeDataLookup) {
  var configStr = JSON.stringify(CONFIG_MAP[node.id] || {});
  return testStr(String(node.id)) || testStr(node.label || '') ||
         testStr(configStr) || nodeMatchesSearch(node.id, testStr, nodeDataLookup);
}

function firstClusterMemberMatch(clusterId, testStr, nodeDataLookup, visited) {
  var cm = AppState.clusterMap[clusterId];
  if (!cm) return null;
  visited = visited || {};
  if (visited[clusterId]) return null;
  visited[clusterId] = true;

  var memberIds = cm.memberIds || [];
  for (var mi = 0; mi < memberIds.length; mi++) {
    var mid = memberIds[mi];
    if (AppState.clusterMap[mid]) {
      var nestedMatch = firstClusterMemberMatch(mid, testStr, nodeDataLookup, visited);
      if (nestedMatch !== null) return nestedMatch;
    } else if (nodeMatchesSearch(mid, testStr, nodeDataLookup)) {
      return mid;
    }
  }
  return null;
}

function allClusterMemberMatches(clusterId, testStr, nodeDataLookup, visited, results) {
  var cm = AppState.clusterMap[clusterId];
  if (!cm) return results;
  visited = visited || {};
  results = results || [];
  if (visited[clusterId]) return results;
  visited[clusterId] = true;
  var memberIds = cm.memberIds || [];
  for (var mi = 0; mi < memberIds.length; mi++) {
    var mid = memberIds[mi];
    if (AppState.clusterMap[mid]) {
      allClusterMemberMatches(mid, testStr, nodeDataLookup, visited, results);
    } else if (nodeMatchesSearch(mid, testStr, nodeDataLookup)) {
      results.push(mid);
    }
  }
  return results;
}

function makeSearchTester(query) {
  var re;
  try { re = new RegExp(query, 'i'); } catch(e) { re = null; }
  var q = query.toLowerCase();
  return function(s) {
    s = String(s);
    return re ? re.test(s) : s.toLowerCase().indexOf(q) !== -1;
  };
}

function focusSearchMatch(nodeId, animationDuration) {
  if (!network || nodeId === null || nodesDataset.get(nodeId) === null) return false;
  network.focus(nodeId, {
    scale: FOCUS_SCALE,
    animation: {duration: animationDuration, easingFunction: 'easeInOutQuad'}
  });
  return true;
}

function focusFirstVisibleSearchMatch(query, candidateIds) {
  var testStr = makeSearchTester(query);
  var nodeDataLookup = buildNodeDataLookup();
  for (var i = 0; i < candidateIds.length; i++) {
    var id = candidateIds[i];
    if (nodesDataset.get(id) !== null && nodeMatchesSearch(id, testStr, nodeDataLookup)) {
      return focusSearchMatch(id, 300);
    }
  }
  return false;
}

function _toolTypeToBadgeRole(toolType) {
  var t = (toolType || '').toLowerCase();
  if (t === 'filter') return 'filter';
  if (t === 'formula' || t === 'multirowformula' || t === 'multifieldbinner') return 'formula';
  if (t.indexOf('join') !== -1 || t === 'findreplace' || t === 'spatialmatch') return 'join';
  if (t === 'union') return 'union';
  if (t === 'summarize' || t === 'sample' || t === 'tile') return 'aggregate';
  if (t === 'crosstab' || t === 'transpose' || t === 'regex') return 'reshape';
  if (t.indexOf('output') !== -1 || t === 'browse' || t === 'browsev2') return 'output';
  if (t.indexOf('input') !== -1 || t === 'textinput' || t === 'dbfileinput') return 'input';
  return 'union';
}

function _toolTypeToStepCategory(toolType) {
  var t = (toolType || '').toLowerCase();
  if (t.indexOf('input') !== -1 || t === 'textinput' || t === 'dbfileinput' || t === 'recordid') return 'input';
  if (t.indexOf('output') !== -1 || t === 'browse' || t === 'browsev2') return 'output';
  if (t !== '') return 'transform';
  return 'unknown';
}

function _escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function _highlightEl(el, re) {
  if (!el.dataset.origText) el.dataset.origText = el.textContent;
  el.innerHTML = _escapeHtml(el.dataset.origText).replace(re, '<mark class="search-mark">$1</mark>');
}
function _clearPanelHighlights() {
  document.querySelectorAll('[data-orig-text]').forEach(function(el) {
    el.textContent = el.dataset.origText;
    delete el.dataset.origText;
  });
}
function _highlightPanelText(query) {
  _clearPanelHighlights();
  if (!query) return;
  var q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  var re;
  try { re = new RegExp('(' + q + ')', 'gi'); } catch(e) { return; }
  var insightsBody = document.getElementById('insights-panel-body');
  if (insightsBody) {
    insightsBody.querySelectorAll('.ki-badge, .ki-desc').forEach(function(el) { _highlightEl(el, re); });
  }
  var summaryBody = document.getElementById('summary-panel-body');
  if (summaryBody) {
    summaryBody.querySelectorAll('.step-badge, .step-desc').forEach(function(el) { _highlightEl(el, re); });
  }
}

function doSearch(query, skipFocus, skipPanel) {
  query = query.trim();
  if (!query) { clearSearch(); return; }
  searchActive = true;
  document.getElementById('search-clear-btn').style.display = 'block';

  var testStr = makeSearchTester(query);

  var col = nodeColors();
  var allNodes = nodesDataset.get();
  var updates = [];
  var firstMatch = null;
  var matchedEntries = [];

  // Build a lookup from original node data (pre-clustering) for member searches.
  var nodeDataLookup = buildNodeDataLookup();

  allNodes.forEach(function(n) {
    // Memo nodes: match label text for firstMatch, but skip amber/dim color changes.
    // Memo nodes are user overlays and should remain visually neutral during search.
    if (typeof n.id === 'string' && n.id.indexOf('memo:') === 0) {
      var mMatch = testStr(n.label || '');
      updates.push({id: n.id, font: {color: '#000000'}});
      if (mMatch && firstMatch === null) firstMatch = n.id;
      return;
    }
    // Regular nodes: search id, label, and flattened config values
    var matches = visibleNodeMatchesSearch(n, testStr, nodeDataLookup);

    // Cluster nodes: also search inside each member node
    if (!matches && AppState.clusterMap[n.id]) {
      matches = firstClusterMemberMatch(n.id, testStr, nodeDataLookup) !== null;
    }

    if (matches) {
      if (firstMatch === null) firstMatch = n.id;
      if (AppState.clusterMap[n.id]) {
        var cm = AppState.clusterMap[n.id];
        var matchBg;
        if (cm.isContainer && cm.fillColorHex) {
          matchBg   = cm.fillColorHex;
        } else {
          var cs = cm.isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type;
          matchBg   = cs.matchBg;
        }
        updates.push({id: n.id, color: {
          background: matchBg, border: '#f59e0b',
          highlight: {background: matchBg, border: '#f59e0b'},
          hover:     {background: matchBg, border: '#f59e0b'}
        }, font: {color: contrastColor(matchBg)}});
        var memberMatches = allClusterMemberMatches(n.id, testStr, nodeDataLookup, {}, []);
        if (memberMatches.length > 0) {
          memberMatches.forEach(function(mid) {
            var mnd = nodeDataLookup[mid];
            var mst = mnd ? (mnd.title || '').split('.').pop() : '';
            matchedEntries.push({id: mid, shortType: mst, role: _toolTypeToBadgeRole(mst), category: _toolTypeToStepCategory(mst), label: mnd ? (mnd.label || '') : ''});
          });
        } else {
          matchedEntries.push({id: n.id, shortType: cm.toolType || '?', role: _toolTypeToBadgeRole(cm.toolType), category: _toolTypeToStepCategory(cm.toolType), label: n.label || cm.toolType || ''});
        }
      } else {
        updates.push({id: n.id, color: {
          background: '#92400e', border: '#f59e0b',
          highlight: {background: '#78350f', border: '#fbbf24'},
          hover: {background: '#78350f', border: '#fbbf24'}
        }, font: {color: '#ffffff'},
           shadow: {enabled: true, color: 'rgba(245,158,11,0.45)', size: 10, x: 0, y: 0}});
        var nd = nodeDataLookup[n.id];
        var st = nd ? (nd.title || '').split('.').pop() : (n.label || '');
        matchedEntries.push({id: n.id, shortType: st, role: _toolTypeToBadgeRole(st), category: _toolTypeToStepCategory(st), label: nd ? (nd.label || n.label || '') : (n.label || '')});
      }
    } else {
      if (AppState.clusterMap[n.id]) {
        var cm2 = AppState.clusterMap[n.id];
        var dimColor;
        var dimBg;
        if (cm2.isContainer && cm2.fillColorHex) {
          dimBg = _darkenHex(cm2.fillColorHex, 35);
          dimColor = {background: dimBg, border: dimBg,
                      highlight: {background: dimBg, border: dimBg},
                      hover:     {background: dimBg, border: dimBg}};
        } else {
          var cd = (cm2.isContainer ? CLUSTER_STYLE.container : CLUSTER_STYLE.type).dim;
          dimBg = cd.background;
          dimColor = {background: dimBg, border: cd.border,
                      highlight: {background: dimBg, border: dimBg},
                      hover:     {background: dimBg, border: dimBg}};
        }
        updates.push({id: n.id, color: dimColor, font: {color: contrastColor(dimBg)}});
      } else {
        updates.push({id: n.id, color: {
          background: col.bg, border: col.bd,
          highlight: {background: col.bg, border: col.bd},
          hover: {background: col.bg, border: col.bd}
        }, font: {color: contrastColor(col.bg)}});
      }
    }
  });

  nodesDataset.update(updates);
  if (!skipFocus && firstMatch !== null) {
    focusSearchMatch(firstMatch, 400);
  }
  _highlightPanelText(query);
  if (!skipPanel && typeof openSearchResultsPanel === 'function') openSearchResultsPanel(matchedEntries);
}

function clearSearch() {
  _clearPanelHighlights();
  if (typeof closeSearchResultsPanel === 'function') closeSearchResultsPanel();
  searchActive = false;
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear-btn').style.display = 'none';
  var col = nodeColors();
  nodesDataset.update(nodesDataset.get().map(function(n) { return baseNodeColorUpdate(n, col); }));
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
  var nodeHover = s.getPropertyValue('--node-hover').trim();
  // Iterate only nodes/edges currently in the DataSet.
  // Using NODES_DATA.map() here would re-create clustered-away nodes because
  // DataSet.update() inserts missing IDs as new (label-less) items.
  var nodeUpdates = [];
  nodesDataset.getIds().forEach(function(id) {
    if (AppState.clusterMap[id]) return;  // cluster node: fixed color (purple/teal) — skip
    if (typeof id === 'string' && id.indexOf('memo:') === 0) return;  // memo: keep yellow
    if (BROWSE_NODE_IDS[id]) {
      var bc = browseNodeColor();
      nodeUpdates.push({id: id, color: bc, font: {color: contrastColor(bc.background)}});
      return;
    }
    nodeUpdates.push({id: id, color: {background: nodeBg, border: nodeBd,
      highlight: {background: '#92400e', border: '#f59e0b'},
      hover: {background: nodeHover, border: nodeBd}}, font: {color: contrastColor(nodeBg)}});
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

// ── Config panel drag-resize ──────────────────────────────────────────────
(function() {
  var panel = document.getElementById('config-panel');
  var handle = document.getElementById('panel-drag-handle');
  if (!handle || !panel) return;
  var startX, startW;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault();
    e.stopPropagation();
    startX = e.clientX;
    startW = panel.offsetWidth;
    handle.classList.add('dragging');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  function onMove(e) {
    var dx = startX - e.clientX;
    var newW = Math.max(220, Math.min(Math.floor(window.innerWidth * 0.85), startW + dx));
    panel.style.width = newW + 'px';
  }
  function onUp() {
    handle.classList.remove('dragging');
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }
})();

// ── Minimap resize (drag top-left handle) ─────────────────────────────────
(function() {
  var handle = document.getElementById('minimap-resize-handle');
  var mc = document.getElementById('minimap-canvas');
  if (!handle || !mc) return;
  var MIN_W = 140, MIN_H = 90, MAX_W = 500, MAX_H = 360;
  var startX, startY, startW, startH;
  handle.addEventListener('mousedown', function(e) {
    e.preventDefault();
    e.stopPropagation();
    startX = e.clientX;
    startY = e.clientY;
    startW = mc.width;
    startH = mc.height;
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  function onMove(e) {
    // Dragging toward top-left expands; toward bottom-right shrinks.
    var dx = startX - e.clientX;
    var dy = startY - e.clientY;
    var newW = Math.max(MIN_W, Math.min(MAX_W, startW + dx));
    var newH = Math.max(MIN_H, Math.min(MAX_H, startH + dy));
    mc.width  = Math.round(newW);
    mc.height = Math.round(newH);
    if (network) network.redraw();
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }
})();

// ── SQL Export (server mode only) ────────────────────────────────────────────

function _exportClusterSQL(groupKey) {
  var c = AppState.clusterMap[groupKey] || AppState.groupMembers[groupKey];
  var memberIds = c ? c.memberIds.map(Number) : [];
  fetch(window._YXRAY_SQL_ENDPOINT, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tool_ids: memberIds})
  })
  .then(function(r) { return r.json(); })
  .then(function(data) { _showSQLModal(data); })
  .catch(function(err) { alert('SQL export failed: ' + err); });
}

function _showSQLModal(data) {
  var existing = document.getElementById('sql-export-modal');
  if (existing) existing.remove();
  var overlay = document.createElement('div');
  overlay.id = 'sql-export-modal';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9998;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;';
  overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };
  var box = document.createElement('div');
  box.style.cssText = 'background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:24px;max-width:620px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.4);';
  var hdr = document.createElement('div');
  hdr.style.cssText = 'font-size:14px;font-weight:600;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;';
  var title = document.createElement('span');
  title.textContent = 'SQL Export';
  var closeBtn = document.createElement('span');
  closeBtn.textContent = '\u00d7';
  closeBtn.style.cssText = 'cursor:pointer;font-size:20px;line-height:1;';
  closeBtn.onclick = function() { overlay.remove(); };
  hdr.appendChild(title);
  hdr.appendChild(closeBtn);
  var pre = document.createElement('pre');
  pre.style.cssText = 'background:var(--bg);padding:14px;border-radius:6px;font-size:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-all;margin:0 0 10px;';
  pre.textContent = data.sql;
  var status = document.createElement('div');
  status.style.cssText = 'font-size:12px;color:var(--text-muted);margin-bottom:12px;';
  status.textContent = data.is_partial
    ? 'partial \u2014 ' + (data.warnings || []).join('; ')
    : 'complete';
  var copyBtn = document.createElement('button');
  copyBtn.className = 'ctrl-btn';
  copyBtn.textContent = 'Copy SQL';
  copyBtn.onclick = function() {
    navigator.clipboard.writeText(data.sql).then(function() {
      copyBtn.textContent = 'Copied!';
      setTimeout(function() { copyBtn.textContent = 'Copy SQL'; }, 1500);
    });
  };
  box.appendChild(hdr);
  box.appendChild(pre);
  box.appendChild(status);
  box.appendChild(copyBtn);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}
