"""Tests for SingleGraphRenderer's python-hint enrichment in the config map."""

from __future__ import annotations

import json
import re

from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.renderers.single_graph_renderer import SingleGraphRenderer

_DATA_RE = re.compile(
    r'<script id="yxray-data" type="application/json">(.*?)</script>', re.DOTALL
)


def _config_map(doc: WorkflowDoc) -> dict[str, dict]:
    html = SingleGraphRenderer().render(doc)
    match = _DATA_RE.search(html)
    assert match is not None
    return json.loads(match.group(1))["config_map"]


def _doc(*nodes: AlteryxNode, connections: tuple = ()) -> WorkflowDoc:
    return WorkflowDoc(filepath="test.yxmd", nodes=nodes, connections=connections)


def test_filter_python_hint_matches_scaffold_snippet() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Filter", x=10, y=0,
            config={"Expression": "[Age] > 18"},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    config_map = _config_map(doc)
    assert 'df1["Age"] > 18' in config_map["2"]["python_hint"]


def test_select_python_hint_stays_generic() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2), tool_type="Select", x=10, y=0,
            config={"SelectFields": {"SelectField": [{"@field": "Age"}]}},
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    config_map = _config_map(doc)
    assert config_map["2"]["python_hint"] == "df = df[[...]].rename(columns={...})"


def test_input_python_hint_stays_generic() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1), tool_type="InputData", x=0, y=0,
            config={"File": "a.csv"},
        ),
    )
    config_map = _config_map(doc)
    assert config_map["1"]["python_hint"] == "pd.read_csv(...) / pd.read_excel(...)"


def test_config_map_includes_declared_container_id() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(10), tool_type="ToolContainer", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=10,
            y=10,
            container_id=10,
        ),
    )

    config_map = _config_map(doc)

    assert config_map["1"]["containerId"] == 10


def test_header_can_be_collapsed() -> None:
    html = SingleGraphRenderer().render(
        WorkflowDoc(filepath="fixture.yxmd"),
        key_insights=[{"role": "input", "tool_id": 1, "description": "Input source"}],
    )

    assert 'class="header-utility-row"' in html
    assert 'id="search-input"' in html
    assert 'id="io-primary-actions"' in html
    assert 'id="io-add-memo-btn"' in html
    assert 'id="header-collapse-btn"' in html
    assert 'id="header-expand-btn"' in html
    assert "setHeaderCollapsed" in html
    assert "yxray-header-collapsed-" in html


def test_node_panel_has_int_and_labeled_tool_id_copy_buttons() -> None:
    html = SingleGraphRenderer().render(WorkflowDoc(filepath="fixture.yxmd"))

    assert "function _renderToolIdCopyBlock(toolId, body)" in html
    assert "copyIdBtn.textContent = 'Copy ID'" in html
    assert "copyToolIdBtn.textContent = 'Copy ToolID'" in html
    assert "var labeledText = 'ToolID ' + idText" in html
    assert "_renderClusterInfoBlock(_group.toolType, _group.memberIds, body)" in html


def test_manual_cluster_controls_are_available() -> None:
    manual_config = {
        "schema_version": 1,
        "workflow_fingerprint": "abc",
        "manual_clusters": [{"label": "prep", "tool_ids": [1, 2]}],
    }
    html = SingleGraphRenderer().render(
        WorkflowDoc(filepath="fixture.yxmd"),
        manual_cluster_config=manual_config,
    )

    assert 'id="io-create-cluster-btn"' in html
    assert 'id="io-import-clusters-btn"' in html
    assert 'id="io-export-clusters-btn"' in html
    assert 'id="manual-cluster-import-input"' in html
    assert 'id="manual-cluster-modal"' in html
    assert "function buildManualClusters(config)" in html
    assert "function removeManualCluster(groupKey)" in html
    assert "function importManualClusterConfigFromFile(file)" in html
    assert "function computeDeclaredContainerMembership()" in html
    assert "isManualClusterConfigForWorkflow(stored) ? stored : null" in html
    assert "yxray-manual-clusters-" in html
    assert "multiselect: true" in html
    assert '"manual_clusters": [{"label": "prep", "tool_ids": [1, 2]}]' in html
