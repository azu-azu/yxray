"""Output-port routing regressions, using invented workflows and records only."""

import importlib
import logging
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from lxml import etree

from yxray.models import AlteryxConnection, AlteryxNode, AnchorName, ToolID, WorkflowDoc
from yxray.parser import _element_to_dict, _tree_to_workflow
from yxray.scaffold import (
    node_code_snippets,
    scaffold,
    scaffold_simple,
    scaffold_simple_blocks,
)


def _node(number, kind, config=None):
    return AlteryxNode(
        tool_id=ToolID(number), tool_type=kind, x=0, y=0, config=config or {}
    )


def _edge(source, port, target, input_port="Input"):
    return AlteryxConnection(
        src_tool=ToolID(source),
        src_anchor=AnchorName(port),
        dst_tool=ToolID(target),
        dst_anchor=AnchorName(input_port),
    )


def _join_config():
    return {
        "JoinInfo": [
            {"@connection": side, "Field": {"@field": "key"}}
            for side in ("Left", "Right")
        ],
        "SelectConfiguration": {
            "Configuration": {
                "@outputConnection": "Join",
                "SelectFields": {
                    "SelectField": [
                        {"@field": "Left_key", "@input": "Left_", "@selected": "True"},
                        {"@field": "*Unknown", "@selected": "False"},
                    ]
                },
            }
        },
    }


def _join_doc(*ports):
    return WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(
            _node(1, "InputData"),
            _node(2, "InputData"),
            _node(3, "Join", _join_config()),
            _node(4, "Union"),
        ),
        connections=(
            _edge(1, "Output", 3, "Left"),
            _edge(2, "Output", 3, "Right"),
            *(_edge(3, port, 4, f"#{i}") for i, port in enumerate(ports, 1)),
        ),
    )


@pytest.fixture
def namespace(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "reference_impl")
    )
    helper = importlib.import_module("join_selected")
    return {
        "pd": pd,
        "logger": logging.getLogger(__name__),
        "join_selected": helper.join_selected,
        "join_unmatched": helper.join_unmatched,
    }


def _execute(doc, namespace):
    _, blocks = scaffold_simple_blocks(doc)
    for block in blocks:
        if block.tool_id not in (1, 2):
            exec("\n".join(block.lines), namespace)
    return namespace


def test_left_output_empty_right_preserves_all_left_columns_and_rows(namespace):
    # J's Select keeps only key, but L must retain payload and duplicate indexes.
    left = pd.DataFrame({"key": [1, 1, 2], "payload": ["a", "b", "c"]}, index=[9, 9, 2])
    namespace.update(df_1=left, df_2=pd.DataFrame({"key": pd.Series(dtype="int64")}))
    ns = _execute(_join_doc("Left"), namespace)
    pd.testing.assert_frame_equal(ns["df_3_l"], left)
    assert len(ns["df_4"]) == 3
    assert "join_selected(" not in node_code_snippets(_join_doc("Left"))[3]


def test_join_left_right_union_routes_distinct_frames(namespace):
    namespace.update(
        df_1=pd.DataFrame({"key": [1, 1, 2], "payload": ["a", "b", "c"]}),
        df_2=pd.DataFrame({"key": [1, 1, 3], "right_payload": ["x", "y", "z"]}),
    )
    doc = _join_doc("Join", "Left", "Right")
    ns = _execute(doc, namespace)
    assert ns["df_3_j"].to_dict("list") == {"key": [1, 1, 1, 1]}
    assert ns["df_3_l"].to_dict("list") == {"key": [2], "payload": ["c"]}
    assert ns["df_3_r"].to_dict("list") == {"key": [3], "right_payload": ["z"]}
    assert len(ns["df_4"]) == 6
    for code in (scaffold(doc), scaffold_simple(doc)):
        assert "pd.concat([df_3_j, df_3_l, df_3_r]" in code
        assert "3.Left -> 4.#2; input=df_3_l" in code
        compile(code, "<scaffold>", "exec")
    assert "Connected outputs: Join, Left, Right" in node_code_snippets(doc)[3]


@pytest.mark.parametrize("mode", ["Simple", "Custom"])
def test_filter_splits_once_and_routes_both_outputs_with_duplicate_indexes(
    namespace, mode
):
    config = (
        {
            "Mode": "Simple",
            "Simple": {"Field": "value", "Operator": ">", "Operands": {"Operand": "1"}},
        }
        if mode == "Simple"
        else {"Expression": '[value] > 1 AND !IsEmpty([label]) AND [label] != "skip"'}
    )
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(_node(1, "InputData"), _node(2, "Filter", config), _node(3, "Union")),
        connections=(
            _edge(1, "Output", 2),
            _edge(2, "True", 3, "#1"),
            _edge(2, "False", 3, "#2"),
        ),
    )
    namespace["df_1"] = pd.DataFrame(
        {"value": pd.array([0, 2, None], dtype="Int64"), "label": ["a", "b", "c"]},
        index=[8, 8, 8],
    )
    _, blocks = scaffold_simple_blocks(doc)
    for block in blocks:
        if block.tool_id != 1:
            exec("\n".join(block.lines), namespace)
    assert namespace["df_2_t"]["label"].tolist() == ["b"]
    assert namespace["df_2_f"]["label"].tolist() == ["a", "c"]
    assert len(namespace["df_3"]) == 3


@pytest.mark.parametrize("side", ["Left", "Right"])
def test_unmatched_composite_keys_nulls_duplicates_and_marker_names(namespace, side):
    left = pd.DataFrame(
        {
            "key": [1, 1, 2, None],
            "zone": ["a", "a", "b", "c"],
            "_merge": ["x", "y", "z", "n"],
        },
        index=[4, 4, 4, 4],
    )
    right = pd.DataFrame({"code": [1, 1, None, 3], "area": ["a", "a", "c", "d"]})
    result = namespace["join_unmatched"](
        left, right, keys=[("key", "code"), ("zone", "area")], side=side
    )
    expected = left.iloc[[2]] if side == "Left" else right.iloc[[3]]
    pd.testing.assert_frame_equal(result, expected)


def test_multiple_ports_from_same_source_feed_distinct_join_inputs(namespace):
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(
            *_join_doc("Left", "Join").nodes[:3],
            _node(4, "Join", _join_config()),
            _node(5, "Browse"),
        ),
        connections=(
            *_join_doc().connections,
            _edge(3, "Left", 4, "Left"),
            _edge(3, "Join", 4, "Right"),
            _edge(4, "Left", 5),
        ),
    )
    code = node_code_snippets(doc)[4]
    assert "df_3_l, df_3_j" in code
    assert "df_4_l" in node_code_snippets(doc)[5]


@pytest.mark.parametrize("kind", ["AppendFields", "FindReplace", "SpatialMatch"])
def test_other_multi_input_consumers_resolve_ports(kind):
    first, second = {
        "AppendFields": ("Targets", "Sources"),
        "FindReplace": ("Targets", "Source"),
        "SpatialMatch": ("Targets", "Universe"),
    }[kind]
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(
            *_join_doc().nodes[:3],
            _node(
                4,
                kind,
                {
                    "FieldFind": "key",
                    "FieldSearch": "key",
                    "FindMode": "FindWhole",
                    "ReplaceMode": "Append",
                    "ReplaceAppendFields": {"Field": {"@field": "key"}},
                },
            ),
        ),
        connections=(
            *_join_doc().connections,
            _edge(3, "Left", 4, first),
            _edge(3, "Join", 4, second),
        ),
    )
    code = node_code_snippets(doc)[4]
    # Exclude diagnostics, so this checks expressions actually consume the frames.
    executable = "\n".join(
        line for line in code.splitlines() if not line.startswith("#")
    )
    assert "df_3_l" in executable
    assert "df_3_j" in executable


def test_unknown_output_stops_instead_of_assuming_join(namespace):
    doc = _join_doc("Output")
    for code in (node_code_snippets(doc)[3], node_code_snippets(doc)[4]):
        assert "Unresolved output: 3.Output" in code
        assert "join_selected(" not in code
        with pytest.raises(NotImplementedError, match="Unresolved output"):
            exec(code, namespace)


def test_metainfo_is_not_connection_evidence(namespace):
    root = etree.fromstring(b"""<AlteryxDocument><Nodes><Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Join.Join"/>
      <Properties><Configuration/><MetaInfo connection="Left"><RecordInfo/>
      </MetaInfo></Properties></Node></Nodes></AlteryxDocument>""")
    doc = _tree_to_workflow(etree.ElementTree(root), "invented.yxmd")
    assert not doc.connections
    assert "Connections section is absent" in doc.connection_warnings[0]
    code = node_code_snippets(doc)[3]
    assert "Connections section is absent" in code
    assert "raise NotImplementedError" in code


def test_parser_to_generator_preserves_left_output():
    root = etree.fromstring(b"""<AlteryxDocument><Nodes>
      <Node ToolID="1"><GuiSettings Plugin="InputData"/><Properties><Configuration/>
      </Properties></Node><Node ToolID="2"><GuiSettings Plugin="InputData"/>
      <Properties><Configuration/></Properties></Node>
      <Node ToolID="3"><GuiSettings Plugin="Join"/><Properties><Configuration>
      <JoinInfo connection="Left"><Field field="key"/></JoinInfo>
      <JoinInfo connection="Right"><Field field="key"/></JoinInfo>
      </Configuration></Properties></Node>
      <Node ToolID="4"><GuiSettings Plugin="Browse"/><Properties><Configuration/>
      </Properties></Node></Nodes><Connections>
      <Connection><Origin ToolID="1" Connection="Output"/>
      <Destination ToolID="3" Connection="Left"/></Connection>
      <Connection><Origin ToolID="2" Connection="Output"/>
      <Destination ToolID="3" Connection="Right"/></Connection>
      <Connection name="named-edge"><Origin ToolID="3" Connection="Left"/>
      <Destination ToolID="4" Connection="Input"/></Connection>
      </Connections></AlteryxDocument>""")
    doc = _tree_to_workflow(etree.ElementTree(root), "invented.yxmd")
    assert doc.connection_warnings == ()
    assert doc.connections[-1].name == "named-edge"
    assert "side='Left'" in node_code_snippets(doc)[3]
    assert "len(df_3_l)" in node_code_snippets(doc)[4]


def test_missing_source_port_is_diagnosed_not_defaulted_to_j():
    root = etree.fromstring(b"""<AlteryxDocument><Nodes>
      <Node ToolID="3"><GuiSettings Plugin="Join"/><Properties><Configuration/>
      </Properties></Node></Nodes><Connections><Connection><Origin ToolID="3"/>
      <Destination ToolID="4" Connection="Input"/></Connection>
      </Connections></AlteryxDocument>""")
    doc = _tree_to_workflow(etree.ElementTree(root), "invented.yxmd")
    assert "Origin.Connection is missing" in doc.connection_warnings[0]
    assert "raise NotImplementedError" in node_code_snippets(doc)[3]


def test_union_honors_explicit_connection_order(namespace):
    doc = _join_doc("Join", "Left")
    union = replace(
        doc.nodes[-1],
        config={
            "SetOutputOrder": {"@value": "True"},
            "OutputOrder": {"Connection": ["#2", "#1"]},
        },
    )
    doc = replace(doc, nodes=(*doc.nodes[:-1], union))
    namespace.update(
        df_1=pd.DataFrame({"key": [1, 2]}),
        df_2=pd.DataFrame({"key": [1]}),
    )
    ns = _execute(doc, namespace)
    assert ns["df_4"]["key"].tolist() == [2, 1]


def test_union_order_uses_parsed_names_when_destination_ports_are_both_input(namespace):
    doc = _join_doc("Join", "Left")
    config = _element_to_dict(
        etree.fromstring(b"""<Configuration>
      <SetOutputOrder value="True"/><OutputOrder>
      <Connection>#2</Connection><Connection>#1</Connection>
      </OutputOrder></Configuration>""")
    )
    doc = replace(
        doc,
        nodes=(*doc.nodes[:-1], replace(doc.nodes[-1], config=config)),
        connections=tuple(
            replace(edge, name=str(edge.dst_anchor), dst_anchor=AnchorName("Input"))
            if edge.dst_tool == 4
            else edge
            for edge in doc.connections
        ),
    )
    namespace.update(
        df_1=pd.DataFrame({"key": [1, 2]}), df_2=pd.DataFrame({"key": [1]})
    )
    assert _execute(doc, namespace)["df_4"]["key"].tolist() == [2, 1]


def test_incomplete_union_order_stops_instead_of_guessing():
    doc = _join_doc("Join", "Left")
    union = replace(
        doc.nodes[-1],
        config={
            "SetOutputOrder": {"@value": "True"},
            "OutputOrder": {"Connection": ["#1"]},
        },
    )
    doc = replace(doc, nodes=(*doc.nodes[:-1], union))
    assert "raise NotImplementedError" in node_code_snippets(doc)[4]


def test_empty_filter_true_feeds_right_input_of_left_join(namespace):
    # The reported failure: Count=1 has no matches, yet Join's L output
    # must preserve every left row. Use a tiny independent example.
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(
            _node(1, "InputData"),
            _node(2, "InputData"),
            _node(3, "Filter", {"Expression": "[Count] = 1"}),
            _node(4, "Join", _join_config()),
            _node(5, "Browse"),
        ),
        connections=(
            _edge(2, "Output", 3),
            _edge(1, "Output", 4, "Left"),
            _edge(3, "True", 4, "Right"),
            _edge(4, "Left", 5),
        ),
    )
    left = pd.DataFrame({"key": [1, 1, 2], "payload": ["a", "b", "c"]})
    namespace.update(df_1=left, df_2=pd.DataFrame({"key": [1, 2], "Count": [7, 9]}))
    ns = _execute(doc, namespace)
    assert ns["df_3_t"].empty
    pd.testing.assert_frame_equal(ns["df_4_l"], left)


@pytest.mark.parametrize("expression", ["", "[key] ?? unknown"])
def test_connected_filter_missing_or_untranslated_predicate_stops(expression):
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(
            _node(1, "InputData"),
            _node(2, "Filter", {"Expression": expression}),
            _node(3, "Browse"),
        ),
        connections=(_edge(1, "Output", 2), _edge(2, "False", 3)),
    )
    assert "raise NotImplementedError" in node_code_snippets(doc)[2]


def test_unsupported_other_output_does_not_silently_alias_default():
    doc = WorkflowDoc(
        filepath="invented.yxmd",
        nodes=(_node(1, "Unique"), _node(2, "Browse")),
        connections=(_edge(1, "Duplicate", 2),),
    )
    assert "Unimplemented output: 1.Duplicate" in node_code_snippets(doc)[2]


def test_terminal_preview_explicitly_reports_unknown_usage():
    code = node_code_snippets(_join_doc())[3]
    assert "used output is unknown" in code
    assert "isolated preview only" in code
