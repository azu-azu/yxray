"""Tests for DiffGraphRenderer — GRPH-01 through GRPH-04."""

from __future__ import annotations

import json

from tests.fixtures.graph import (
    ALL_CHANGE_TYPES_DIFF,
    ALL_CONNECTIONS,
    ALL_NODES_NEW,
    ALL_NODES_OLD,
    CONN_A_TO_B,
    EMPTY_DIFF,
    MODIFIED_DIFF,
    NODE_MODIFIED_NEW,
    NODE_MODIFIED_OLD,
    NODE_UNCHANGED_A,
    NODE_UNCHANGED_B,
)
from yxray.models import DiffResult
from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.renderers import (
    DiffGraphRenderer,
    HTMLRenderer,
    SingleGraphRenderer,
)
from yxray.renderers._graph_builder import COLOR_MAP


def _extract_graph_nodes(html: str) -> list[dict]:
    """Extract the GRAPH_NODES array from a graph HTML fragment."""
    marker = "var GRAPH_NODES = "
    start = html.index(marker) + len(marker)
    # Find the closing ]; (nodes is a flat array of dicts — no nested arrays)
    end = html.index("]", start) + 1
    return json.loads(html[start:end])


def test_render_self_contained() -> None:
    """GRPH-01 / REPT-04: no CDN references; graph-container and vis.Network present."""
    renderer = DiffGraphRenderer()
    html = renderer.render(
        ALL_CHANGE_TYPES_DIFF,
        ALL_CONNECTIONS,
        ALL_NODES_OLD,
        ALL_NODES_NEW,
    )
    assert "cdn." not in html
    assert "graph-container" in html
    assert "vis.Network" in html



def test_single_graph_has_summary_panel_js() -> None:
    """Single graph includes summary panel open/close functions."""
    html = SingleGraphRenderer().render(WorkflowDoc(filepath="fixture.yxmd"))

    assert "openSummaryPanel" in html
    assert "closeSummaryPanel" in html
    assert "toggleStepDetail" in html


def test_single_graph_embeds_topological_node_layers() -> None:
    """Cluster ordering receives dependency layers from the renderer."""
    doc = WorkflowDoc(
        filepath="fixture.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(1), tool_type="InputData", x=0.0, y=0.0
            ),
            AlteryxNode(tool_id=ToolID(2), tool_type="Select", x=100.0, y=0.0),
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )

    html = SingleGraphRenderer().render(doc)
    marker = '<script id="yxray-data" type="application/json">'
    data_json = html.split(marker, maxsplit=1)[1].split("</script>", maxsplit=1)[0]
    data = json.loads(data_json)

    assert data["node_layer"] == {"1": 0, "2": 1}


def test_render_returns_fragment_not_full_document() -> None:
    """GRPH-01: output is a fragment, not a full HTML document."""
    renderer = DiffGraphRenderer()
    html = renderer.render(
        EMPTY_DIFF,
        (),
        (NODE_UNCHANGED_A, NODE_UNCHANGED_B),
        (NODE_UNCHANGED_A, NODE_UNCHANGED_B),
    )
    assert "<html" not in html
    assert "<body" not in html
    # Fragment must contain the graph container element
    assert "graph-container" in html or "graph-section" in html


def test_node_colors_match_diff_status() -> None:
    """GRPH-03: each diff-status category maps to the correct hex color."""
    renderer = DiffGraphRenderer()
    html = renderer.render(
        ALL_CHANGE_TYPES_DIFF,
        ALL_CONNECTIONS,
        ALL_NODES_OLD,
        ALL_NODES_NEW,
    )
    nodes = _extract_graph_nodes(html)
    by_status = {n["status"]: n["color"] for n in nodes}

    assert by_status["added"]["background"] == COLOR_MAP["added"]  # #d1fae5
    assert by_status["removed"]["background"] == COLOR_MAP["removed"]  # #fee2e2
    assert by_status["modified"]["background"] == COLOR_MAP["modified"]  # #fef3c7
    assert by_status["connection"]["background"] == COLOR_MAP["connection"]  # #dbeafe
    assert by_status["unchanged"]["background"] == COLOR_MAP["unchanged"]  # #f1f5f9


def test_node_count_matches_all_unique_tool_ids() -> None:
    """GRPH-01: node count equals all unique tool IDs across old+new workflow."""
    # ALL_NODES_OLD: 811(removed), 812(mod_old), 813(conn_src), 814(conn_dst), 815(unch)
    # ALL_NODES_NEW: 810(added),   812(mod_new), 813(conn_src), 814(conn_dst), 815(unch)
    # Unique IDs: 810, 811, 812, 813, 814, 815 = 6 nodes
    renderer = DiffGraphRenderer()
    html = renderer.render(
        ALL_CHANGE_TYPES_DIFF,
        ALL_CONNECTIONS,
        ALL_NODES_OLD,
        ALL_NODES_NEW,
    )
    nodes = _extract_graph_nodes(html)
    assert len(nodes) == 6


def test_hierarchical_layout_produces_positions() -> None:
    """GRPH-02: hierarchical layout assigns valid x/y positions to all nodes."""
    renderer = DiffGraphRenderer()
    # Simple two-node chain: 801 -> 802 with a connection
    html = renderer.render(
        EMPTY_DIFF,
        (CONN_A_TO_B,),
        (NODE_UNCHANGED_A, NODE_UNCHANGED_B),
        (NODE_UNCHANGED_A, NODE_UNCHANGED_B),
    )
    nodes = _extract_graph_nodes(html)
    assert len(nodes) == 2

    for node in nodes:
        assert "x" in node
        assert "y" in node
        # Both coordinates must be numeric (float-convertible)
        float(node["x"])
        float(node["y"])

    # Source node (801, layer 0) should have a smaller x than destination (802, layer 1)
    pos_by_id = {n["id"]: n["x"] for n in nodes}
    assert pos_by_id[801] < pos_by_id[802]


def test_canvas_layout_uses_alteryx_coordinates() -> None:
    """GRPH-02: canvas_layout=True uses raw Alteryx X/Y, not computed positions."""
    n_old = AlteryxNode(
        tool_id=ToolID(820), tool_type="InputData", x=100.0, y=200.0, config={}
    )
    n_new = AlteryxNode(
        tool_id=ToolID(820), tool_type="InputData", x=300.0, y=400.0, config={}
    )
    renderer = DiffGraphRenderer()
    html = renderer.render(DiffResult(), (), (n_old,), (n_new,), canvas_layout=True)
    nodes = _extract_graph_nodes(html)
    assert len(nodes) == 1
    assert nodes[0]["x"] == 300.0
    assert nodes[0]["y"] == 400.0


def test_diff_panel_data_available_for_modified_node() -> None:
    """GRPH-04: diff panel elements are present in graph fragment for modified nodes."""
    renderer = DiffGraphRenderer()
    html = renderer.render(
        MODIFIED_DIFF,
        (),
        (NODE_MODIFIED_OLD,),
        (NODE_MODIFIED_NEW,),
    )
    # DIFF_DATA is read from the page's diff-data script tag
    assert "DIFF_DATA" in html
    # Slide-in panel div
    assert "diff-panel" in html
    # Escape key handler
    assert "Escape" in html
    # Overlay for outside-click close
    assert "graph-overlay" in html


def test_html_renderer_embeds_graph_fragment() -> None:
    """GRPH-01: HTMLRenderer embeds a graph fragment when graph_html is provided."""
    html_renderer = HTMLRenderer()
    fake_graph = "<div id='test-graph'>GRAPH_PLACEHOLDER</div>"
    html = html_renderer.render(
        DiffResult(),
        graph_html=fake_graph,
    )
    assert "test-graph" in html
    assert "GRAPH_PLACEHOLDER" in html
    assert "diff-data" in html
    assert "Added" in html
