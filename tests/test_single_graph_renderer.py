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
    assert 'df_1["Age"] > 18' in config_map["2"]["python_hint"]


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
