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
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[Age] > 18"},
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
    config_map = _config_map(doc)
    hint = config_map["2"]["python_hint"]
    assert hint.startswith("# ToolID_2\n")
    assert "# Alteryx expression — review translation" in hint
    assert "NOTE" not in hint
    assert 'df_1["Age"] > 18' in hint


def test_python_hint_copy_indents_for_def_body() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Filter",
            x=10,
            y=0,
            config={"Expression": "[Age] > 18"},
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

    assert "function _indentForFunctionBody(text)" in html
    assert "_clipboardWrite(_indentForFunctionBody(entry.python_hint)" in html


def test_select_python_hint_matches_scaffold_snippet() -> None:
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
        AlteryxNode(
            tool_id=ToolID(2),
            tool_type="Select",
            x=10,
            y=0,
            config={"SelectFields": {"SelectField": [{"@field": "Age"}]}},
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
    config_map = _config_map(doc)
    assert 'SelectColumnEdit("Age")' in config_map["2"]["python_hint"]
    assert "apply_select_edits" in config_map["2"]["python_hint"]


def test_input_python_hint_stays_generic() -> None:
    doc = _doc(
        AlteryxNode(
            tool_id=ToolID(1),
            tool_type="InputData",
            x=0,
            y=0,
            config={"File": "a.csv"},
        ),
    )
    config_map = _config_map(doc)
    assert config_map["1"]["python_hint"] == (
        "# ToolID_1\npd.read_csv(...) / pd.read_excel(...)"
    )


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

    assert 'id="panel-copy-tool-id-btn"' in html
    assert "function copyPanelToolId()" in html
    assert "document.getElementById('panel-copy-tool-id-btn')" in html
    assert "function _flowOrderBareIdsText(memberIds)" in html
    assert "copyIdsBtn.textContent = 'Copy IDs'" in html
    assert "copyToolIdsBtn.textContent = 'Copy ToolIDs'" in html
    assert (
        "_renderClusterInfoBlock(_group.toolType, _group.memberIds, body)" not in html
    )
    assert "function _renderToolIdCopyBlock(toolId, body)" not in html


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
    assert "function renameManualCluster(groupKey, label)" in html
    assert "function openManualClusterRenameModal(groupKey)" in html
    assert 'id="manual-cluster-modal-title"' in html
    assert "function importManualClusterConfigFromFile(file)" in html
    assert "function computeDeclaredContainerMembership()" in html
    assert "isManualClusterConfigForWorkflow(stored) ? stored : null" in html
    assert "yxray-manual-clusters-" in html
    assert "multiselect: true" in html
    assert '"manual_clusters": [{"label": "prep", "tool_ids": [1, 2]}]' in html


def test_manual_cluster_panel_offers_rename() -> None:
    """The cluster panel exposes a rename button for manual clusters in both the
    collapsed and expanded states, and the modal doubles as the rename dialog."""
    html = SingleGraphRenderer().render(WorkflowDoc(filepath="fixture.yxmd"))

    assert "function _manualClusterRenameBtn(groupKey)" in html
    assert "btn.textContent = 'Rename manual cluster'" in html
    assert "_setManualClusterModalTitle(title)" in html
    assert "'Rename Cluster'" in html
    assert "function validateManualClusterRename(label, existingKey)" in html
    assert "if (AppState.manualClusterRenameKey) {" in html
    assert "group.manualKey = manualClusterKey(stored)" in html


def test_config_map_includes_raw_node_xml() -> None:
    """The panel's config map carries each node's original <Node> XML so the
    report can show it as a 'source' section at the bottom of the right pane."""
    raw = '<Node ToolID="1">\n  <GuiSettings Plugin="X"/>\n</Node>'
    doc = _doc(
        AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0, raw_xml=raw),
    )
    config_map = _config_map(doc)
    assert config_map["1"]["raw_xml"] == raw


def test_panel_renders_source_xml_section() -> None:
    """The JS bundle renders the raw XML as the last panel section."""
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    html = SingleGraphRenderer().render(doc)
    assert "source (Node XML)" in html
    assert "entry.raw_xml" in html


def test_config_map_carries_batch_macro_overrides() -> None:
    """Each tool in a rewrite chain gets the view of it that answers its own
    panel: the destination sees what replaces its field, the Action sees what
    it writes, the Control Parameter sees where its value lands."""
    import pathlib
    import tempfile

    from tests.fixtures import BATCH_MACRO_YXMC
    from yxray.parser import parse_one

    path = pathlib.Path(tempfile.mkdtemp()) / "batch.yxmc"
    path.write_bytes(BATCH_MACRO_YXMC)
    config_map = _config_map(parse_one(path, filter_ui_tools=False))

    assert config_map["2"]["runtime_overrides"] == [
        "File ← [#1] 出力ファイル名 — Action 102"
    ]
    assert config_map["102"]["runtime_overrides"] == [
        "rewrites 2/File as [#1] 出力ファイル名"
    ]
    assert config_map["101"]["runtime_overrides"] == [
        "[#1] 出力ファイル名 → 2/File via Action 102"
    ]
    # A Control Parameter's <Configuration/> is empty, so without the
    # annotation the panel would have nothing but the plugin name to show.
    assert config_map["101"]["annotation"] == "コントロールパラメーター (101)"
    assert config_map["101"]["config"] == {}


def test_config_map_has_no_overrides_for_a_plain_workflow() -> None:
    doc = _doc(AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0))
    entry = _config_map(doc)["1"]
    assert entry["runtime_overrides"] == []
    assert entry["annotation"] == ""
