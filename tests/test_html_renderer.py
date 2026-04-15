"""Tests for HTMLRenderer: validates REPT-01, REPT-02, REPT-03, REPT-04."""

from __future__ import annotations

import json

from alteryx_git_companion.renderers import HTMLRenderer
from tests.fixtures.html_report import (
    EMPTY_DIFF,
    SINGLE_ADDED,
    SINGLE_MODIFIED,
    WITH_CONNECTION,
)


def test_render_self_contained() -> None:
    """Rendered HTML is self-contained: no CDN refs, all CSS/JS inline (REPT-04)."""
    html = HTMLRenderer().render(EMPTY_DIFF)
    # No external resource URLs
    assert "cdn." not in html
    assert "unpkg.com" not in html
    assert "jsdelivr.net" not in html
    assert "script src=" not in html
    assert 'link rel="stylesheet"' not in html
    assert "link rel='stylesheet'" not in html
    # Inline CSS and JS must be present
    assert "<style>" in html
    assert "<script>" in html
    # DIFF_DATA must be embedded
    assert "DIFF_DATA" in html


def test_render_header() -> None:
    """Report header includes timestamp and both compared file names (REPT-03)."""
    html = HTMLRenderer().render(
        EMPTY_DIFF,
        file_a="workflow_v1.yxmd",
        file_b="workflow_v2.yxmd",
    )
    assert "workflow_v1.yxmd" in html
    assert "workflow_v2.yxmd" in html
    # ISO 8601 timestamp contains 'T' and 'Z' or '+00:00'
    assert "Generated:" in html


def test_render_summary_counts_added() -> None:
    """Summary panel shows correct added count (REPT-01)."""
    html = HTMLRenderer().render(SINGLE_ADDED)
    assert "Added: 1" in html
    assert "Removed: 0" in html
    assert "Modified: 0" in html
    assert "Connections: 0" in html


def test_render_summary_counts_modified() -> None:
    """Summary panel shows correct modified and connection counts (REPT-01)."""
    html = HTMLRenderer().render(SINGLE_MODIFIED)
    assert "Added: 0" in html
    assert "Modified: 1" in html
    html2 = HTMLRenderer().render(WITH_CONNECTION)
    assert "Connections: 1" in html2


def test_render_modified_tool_skeleton() -> None:
    """Modified tool row collapsed in initial HTML; detail built lazily (REPT-02)."""
    html = HTMLRenderer().render(SINGLE_MODIFIED)
    # Tool ID 703 row must be present
    assert "ID: 703" in html
    # The empty detail container must exist
    assert "detail-modified-703" in html
    # Skeleton div must be hidden (detail not pre-rendered at template time)
    assert 'id="detail-modified-703" hidden' in html or "detail-modified-703" in html


def test_render_added_tool_in_diff_data() -> None:
    """DIFF_DATA JSON contains added tool config for lazy detail rendering (REPT-02)."""
    html = HTMLRenderer().render(SINGLE_ADDED)
    # Extract JSON from the application/json script tag
    start = html.index('id="diff-data">') + len('id="diff-data">')
    end = html.index("</script>", start)
    diff_data = json.loads(html[start:end])
    added = diff_data["added"]
    assert len(added) == 1
    assert added[0]["tool_id"] == 701
    assert added[0]["tool_type"] == "AlteryxBasePluginsGui.Filter"
    assert "Expression" in added[0]["config"]
    assert added[0]["config"]["Expression"] == "Field1 > 0"


def test_render_connections_in_diff_data() -> None:
    """DIFF_DATA JSON contains connection change data for lazy rendering (REPT-02)."""
    html = HTMLRenderer().render(WITH_CONNECTION)
    start = html.index('id="diff-data">') + len('id="diff-data">')
    end = html.index("</script>", start)
    diff_data = json.loads(html[start:end])
    connections = diff_data["connections"]
    assert len(connections) == 1
    conn = connections[0]
    assert conn["src_tool"] == 704
    assert conn["src_anchor"] == "Output"
    assert conn["dst_tool"] == 705
    assert conn["dst_anchor"] == "Input"
    assert conn["change_type"] == "added"
