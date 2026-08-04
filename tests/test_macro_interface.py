"""Batch-macro interface: parsing, per-tool warnings, and data-graph hygiene.

The tools that make a batch macro work — Control Parameter and Action — say
nothing about themselves inside their own <Node>: the configuration element
is empty. Everything here is about reading the two document-level blocks that
do hold the answer, and about keeping the interface edges out of the data
flow they are not part of.
"""

from __future__ import annotations

import pathlib

import pytest

from tests.fixtures import BATCH_MACRO_YXMC, MINIMAL_YXMD
from yxray.macro_overrides import detect_macro_overrides
from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.parser import parse_one
from yxray.scaffold import scaffold
from yxray.topology import build_predecessor_map, topo_order


@pytest.fixture
def macro_path(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "batch.yxmc"
    path.write_bytes(BATCH_MACRO_YXMC)
    return path


# ── Parsing ────────────────────────────────────────────────────────────────


def test_control_params_are_indexed_by_position(macro_path: pathlib.Path) -> None:
    # The [#N] an Action refers to is the parameter's position in
    # <BatchMacro><ControlParams> — not a stored id.
    (param,) = parse_one(macro_path).macro_interface.control_params
    assert param.index == 1
    assert param.description == "出力ファイル名"
    # The canvas ToolID is only recoverable from the default name.
    assert param.tool_id == 101
    assert param.label == "出力ファイル名"


def test_actions_resolve_their_destination_and_params(
    macro_path: pathlib.Path,
) -> None:
    (action,) = parse_one(macro_path).macro_interface.actions
    assert action.tool_id == 102
    assert action.expression == "[#1]"
    assert action.destination_tool_id == 2
    assert action.destination_field == "File"
    assert action.param_indexes == (1,)


def test_macro_interface_survives_the_ui_node_filter(
    macro_path: pathlib.Path,
) -> None:
    # The blocks sit outside <Nodes>, so filtering interface *nodes* must not
    # take the interface *model* with them — that is what made the tools
    # invisible in the .md before.
    filtered = parse_one(macro_path, filter_ui_tools=True)
    unfiltered = parse_one(macro_path, filter_ui_tools=False)
    assert filtered.macro_interface == unfiltered.macro_interface
    assert filtered.macro_interface


def test_plain_workflow_has_an_empty_interface(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "plain.yxmd"
    path.write_bytes(MINIMAL_YXMD)
    interface = parse_one(path).macro_interface
    assert not interface
    assert interface.control_params == ()
    assert interface.actions == ()


def test_annotation_text_is_parsed(macro_path: pathlib.Path) -> None:
    # A Control Parameter's <Configuration/> is empty, so the annotation is
    # the only identity the node itself carries.
    nodes = {
        int(n.tool_id): n for n in parse_one(macro_path, filter_ui_tools=False).nodes
    }
    assert nodes[101].annotation == "コントロールパラメーター (101)"
    assert nodes[102].annotation == "値を更新"
    assert nodes[1].annotation == ""


# ── Warnings ───────────────────────────────────────────────────────────────


def test_override_warning_names_the_field_action_and_parameter(
    macro_path: pathlib.Path,
) -> None:
    (warning,) = detect_macro_overrides(parse_one(macro_path))
    assert warning.tool_id == 2
    assert warning.field == "File"
    assert warning.action_tool_id == 102
    assert "Action 102" in warning.message
    assert "[#1] 出力ファイル名 (ToolID 101)" in warning.message
    assert "design-time default" in warning.message


def test_no_warning_when_the_destination_tool_is_absent(
    macro_path: pathlib.Path,
) -> None:
    # Nothing to attach the warning to, so it is dropped rather than keyed
    # to a tool the caller cannot render.
    doc = parse_one(macro_path)
    without_output = WorkflowDoc(
        filepath=doc.filepath,
        nodes=tuple(n for n in doc.nodes if int(n.tool_id) != 2),
        connections=doc.connections,
        macro_interface=doc.macro_interface,
    )
    assert detect_macro_overrides(without_output) == []


def test_explain_output_warns_on_the_rewritten_tool(
    macro_path: pathlib.Path,
) -> None:
    # The scaffold's own File value is the design-time default; the warning
    # has to sit with the block that uses it. This is the wiring _explain_impl
    # does — merging the warnings into the map the scaffold already renders.
    doc = parse_one(macro_path)
    warnings_by_tool = {w.tool_id: [w.message] for w in detect_macro_overrides(doc)}
    code = scaffold(doc, warnings_by_tool=warnings_by_tool)
    block = code.split("ToolID_2")[1]
    assert "Batch macro" in block
    assert "rewrites" in block


# ── Data-graph hygiene ─────────────────────────────────────────────────────


def test_interface_edges_never_become_data_predecessors(
    macro_path: pathlib.Path,
) -> None:
    # The Action is wired into the Output tool, and its connection is listed
    # first in the fixture. Before this was filtered, preds[0] was the Action
    # and the scaffold emitted `df_?` — invalid Python that depended only on
    # the order connections happen to appear in the XML.
    for filter_ui_tools in (True, False):
        doc = parse_one(macro_path, filter_ui_tools=filter_ui_tools)
        assert build_predecessor_map(doc) == {2: [1]}
        assert 102 not in topo_order(doc)
        code = scaffold(doc)
        assert "df_?" not in code
        assert "df_1.to_csv" in code


def test_interface_nodes_are_not_scaffolded_as_data_tools(
    macro_path: pathlib.Path,
) -> None:
    # Even when they are parsed in, they carry no rows — a `df_101 = ...`
    # stub would be noise in the generated script.
    code = scaffold(parse_one(macro_path, filter_ui_tools=False))
    assert "df_101" not in code
    assert "df_102" not in code


def test_unknown_predecessor_tools_are_dropped() -> None:
    # Same guard, reached from the other side: a connection whose source was
    # never parsed at all (a hand-trimmed file) must not reach the scaffold.
    doc = WorkflowDoc(
        filepath="w.yxmd",
        nodes=(
            AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
            AlteryxNode(tool_id=ToolID(2), tool_type="Unique", x=10, y=0),
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(99),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    assert build_predecessor_map(doc) == {2: [1]}
