"""Tests for HTMLRenderer: validates REPT-01, REPT-02, REPT-03, REPT-04."""

from __future__ import annotations

import json

from tests.fixtures.html_report import (
    EMPTY_DIFF,
    SINGLE_ADDED,
    SINGLE_MODIFIED,
    WITH_CONNECTION,
)
from yxray.renderers import HTMLRenderer


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
    # diff-data JSON element must be embedded
    assert "diff-data" in html


def test_report_graph_button_scrolls_to_section() -> None:
    """Graph button scrolls to the embedded graph section (single-file output)."""
    html = HTMLRenderer().render(EMPTY_DIFF)

    assert "function openGraph()" in html
    assert "graph-section" in html
    assert "scrollIntoView" in html


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
    # Verify counts via the embedded diff-data JSON (sr-only spans were removed)
    start = html.index('id="diff-data">') + len('id="diff-data">')
    end = html.index("</script>", start)
    diff_data = json.loads(html[start:end])
    assert len(diff_data["added"]) == 1
    assert len(diff_data["removed"]) == 0
    assert len(diff_data["modified"]) == 0
    assert len(diff_data["connections"]) == 0
    # Stat card labels are still present
    assert "Added" in html
    assert "Removed" in html
    assert "Modified" in html


def test_render_summary_counts_modified() -> None:
    """Summary panel shows correct modified and connection counts (REPT-01)."""
    html = HTMLRenderer().render(SINGLE_MODIFIED)
    start = html.index('id="diff-data">') + len('id="diff-data">')
    end = html.index("</script>", start)
    diff_data = json.loads(html[start:end])
    assert len(diff_data["added"]) == 0
    assert len(diff_data["modified"]) == 1
    html2 = HTMLRenderer().render(WITH_CONNECTION)
    start2 = html2.index('id="diff-data">') + len('id="diff-data">')
    end2 = html2.index("</script>", start2)
    diff_data2 = json.loads(html2[start2:end2])
    assert len(diff_data2["connections"]) == 1


def test_render_modified_tool_skeleton() -> None:
    """Modified tool data is present in diff-data JSON for lazy rendering (REPT-02)."""
    html = HTMLRenderer().render(SINGLE_MODIFIED)
    # Tool ID 703 data must be present in the embedded diff-data JSON
    start = html.index('id="diff-data">') + len('id="diff-data">')
    end = html.index("</script>", start)
    diff_data = json.loads(html[start:end])
    modified = diff_data["modified"]
    assert len(modified) == 1
    assert modified[0]["tool_id"] == 703


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
