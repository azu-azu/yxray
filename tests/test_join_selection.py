"""Join selection tests using only invented schemas and data."""

import importlib
from pathlib import Path

import pandas as pd
import pytest
from lxml import etree

from yxray.parser import _element_to_dict
from yxray.scaffold._combine import gen_join
from yxray.scaffold._common import PathStyle, ToolContext


@pytest.fixture
def join_helper(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "reference_impl")
    )
    return importlib.import_module("join_selected").join_selected


def _generate(rows, *, keys=None, order=False):
    keys = keys or [("key", "key")]
    ctx = ToolContext(
        tool_id=3,
        segment="Join",
        config={
            "JoinInfo": [
                {"@connection": side, "Field": [{"@field": pair[i]} for pair in keys]}
                for i, side in enumerate(("Left", "Right"))
            ],
            "SelectConfiguration": {
                "Configuration": {
                    "@outputConnection": "Join",
                    "OrderChanged": {"@value": str(order)},
                    "SelectFields": {"SelectField": rows},
                }
            },
        },
        preds=[1, 2],
        anchors={"Left": 1, "Right": 2},
        names={1: "df_1", 2: "df_2", 3: "df_3"},
        paths=PathStyle(lambda *_: "", lambda *_: "", False),
        node_map={},
        pred_map={},
    )
    return gen_join(ctx).code


def _row(side, name, selected=True, **attrs):
    return {"@input": side, "@field": side + name, "@selected": str(selected), **attrs}


def test_generated_join_preserves_left_and_selected_right(join_helper):
    rows = [
        _row("Right_", "key", False),
        _row("Right_", "label", False),
        {"@field": "*Unknown", "@selected": "True"},
    ]
    left = pd.DataFrame({"key": [1, 1], "label": ["a", "b"], "group": ["l", "l"]})
    right = pd.DataFrame(
        {"key": [1, 1], "label": ["c", "d"], "group": ["r", "s"], "part": [2, 3]}
    )
    namespace = {"df_1": left, "df_2": right, "join_selected": join_helper}
    exec(_generate(rows), namespace)
    out = namespace["df_3"]
    assert list(out.columns) == ["key", "label", "group", "Right_group", "part"]
    assert len(out) == 4  # two by two, never deduplicate either side
    assert out["label"].tolist() == ["a", "a", "b", "b"]
    pd.testing.assert_frame_equal(left, namespace["df_1"])
    assert list(right.columns) == ["key", "label", "group", "part"]


def test_unknown_false_removes_unlisted_fields_and_right_keys(join_helper):
    rows = [
        _row("Left_", "key"),
        _row("Left_", "label"),
        {"@field": "*Unknown", "@selected": "False"},
    ]
    left = pd.DataFrame({"key": [1], "label": ["a"], "extra": [8]})
    right = pd.DataFrame({"key": [1, 1], "part": [2, 3]})
    ns = {"df_1": left, "df_2": right, "join_selected": join_helper}
    exec(_generate(rows), ns)
    assert ns["df_3"].to_dict("list") == {"key": [1, 1], "label": ["a", "a"]}


@pytest.mark.parametrize("order", [False, True])
def test_different_multi_keys_right_key_selection_rename_and_order(join_helper, order):
    rows = [
        _row("Right_", "code", **{"@rename": "chosen"}),
        _row("Left_", "value"),
        {"@field": "*Unknown", "@selected": "False"},
    ]
    left = pd.DataFrame({"key": [1, 1], "region": ["a", "b"], "value": [7, 8]})
    right = pd.DataFrame({"code": [1], "zone": ["b"]})
    ns = {"df_1": left, "df_2": right, "join_selected": join_helper}
    exec(_generate(rows, keys=[("key", "code"), ("region", "zone")], order=order), ns)
    out = ns["df_3"]
    assert list(out.columns) == (["chosen", "value"] if order else ["value", "chosen"])
    assert out.to_dict("list") == {"chosen": [1], "value": [8]}


def test_same_named_keys_can_both_survive(join_helper):
    out = join_helper(
        pd.DataFrame({"key": [1]}),
        pd.DataFrame({"key": [1]}),
        keys=[("key", "key")],
        columns=[],
    )
    assert out.to_dict("list") == {"key": [1], "Right_key": [1]}


def test_existing_prefix_names_do_not_confuse_input_identity(join_helper):
    left = pd.DataFrame({"key": [1], "Right_value": [4]})
    right = pd.DataFrame({"key": [1], "Right_value": [9]})
    out = join_helper(
        left,
        right,
        keys=[("key", "key")],
        columns=[("Right_", "key", False, None, None)],
    )
    assert out.to_dict("list") == {
        "key": [1],
        "Right_value": [4],
        "Right_Right_value": [9],
    }


def test_missing_saved_field_warns_but_is_not_materialized(join_helper, caplog):
    out = join_helper(
        pd.DataFrame({"key": [1]}),
        pd.DataFrame({"key": [1]}),
        keys=[("key", "key")],
        columns=[
            ("Left_", "absent", True, None, None),
            ("", "*Unknown", False, None, None),
        ],
    )
    assert out.shape == (1, 0)
    assert "missing input field" in caplog.text


def test_wildcard_position_and_type_conversion(join_helper):
    out = join_helper(
        pd.DataFrame({"key": [1], "value": ["2"]}),
        pd.DataFrame({"key": [1], "extra": [5]}),
        keys=[("key", "key")],
        order_changed=True,
        columns=[
            ("Right_", "extra", True, "first", None),
            ("", "*Unknown", True, None, None),
            ("Left_", "value", True, "amount", "Double"),
            ("Right_", "key", False, None, None),
        ],
    )
    assert list(out.columns) == ["first", "key", "amount"]
    assert out["amount"].iloc[0] == 2.0
    assert pd.api.types.is_numeric_dtype(out["amount"])


def test_ambiguous_output_names_fail_instead_of_silent_duplicates(join_helper):
    with pytest.raises(ValueError, match="collide"):
        join_helper(
            pd.DataFrame({"key": [1], "value": [4], "Right_value": [5]}),
            pd.DataFrame({"key": [1], "value": [9]}),
            keys=[("key", "key")],
            columns=[],
        )


def test_explicit_rename_resolves_output_collision(join_helper):
    out = join_helper(
        pd.DataFrame({"key": [1], "value": [4], "Right_value": [5]}),
        pd.DataFrame({"key": [1], "value": [9]}),
        keys=[("key", "key")],
        columns=[("Right_", "value", True, "other", None)],
    )
    assert out["other"].tolist() == [9]


def test_empty_match_has_expected_columns(join_helper):
    out = join_helper(
        pd.DataFrame({"key": [1]}),
        pd.DataFrame({"key": [2]}),
        keys=[("key", "key")],
        columns=[],
    )
    assert out.empty
    assert list(out.columns) == ["key", "Right_key"]


def test_xml_parser_to_generated_execution(join_helper):
    xml = etree.fromstring(b"""<Configuration>
      <JoinInfo connection="Left"><Field field="key"/></JoinInfo>
      <JoinInfo connection="Right"><Field field="key"/></JoinInfo>
      <SelectConfiguration><Configuration outputConnection="Join">
        <OrderChanged value="False"/><SelectFields>
          <SelectField field="Right_key" input="Right_" selected="False"/>
          <SelectField field="Right_value" input="Right_"
                       selected="True" rename="other"/>
          <SelectField field="*Unknown" selected="True"/>
        </SelectFields>
      </Configuration></SelectConfiguration>
    </Configuration>""")
    config = _element_to_dict(xml)
    ctx = ToolContext(
        3,
        "Join",
        config,
        [1, 2],
        {"Left": 1, "Right": 2},
        {1: "df_1", 2: "df_2", 3: "df_3"},
        PathStyle(lambda *_: "", lambda *_: "", False),
        {},
        {},
    )
    ns = {
        "df_1": pd.DataFrame({"key": [1], "value": [4]}),
        "df_2": pd.DataFrame({"key": [1], "value": [9]}),
        "join_selected": join_helper,
    }
    exec(gen_join(ctx).code, ns)
    assert ns["df_3"].to_dict("list") == {"key": [1], "value": [4], "other": [9]}


def test_ambiguous_side_is_flagged():
    code = _generate([{"@field": "value", "@selected": "True"}])
    assert "TODO: ambiguous" in code
    assert "join_selected(" not in code


def test_generated_literals_cannot_execute_field_text(join_helper):
    name = 'quote"\\\nfield'
    code = _generate(
        [_row("Left_", name), {"@field": "*Unknown", "@selected": "False"}]
    )
    ns = {
        "df_1": pd.DataFrame({"key": [1], name: [4]}),
        "df_2": pd.DataFrame({"key": [1]}),
        "join_selected": join_helper,
    }
    exec(code, ns)
    assert ns["df_3"].to_dict("list") == {name: [4]}


def test_record_position_does_not_use_stale_field_keys():
    ctx = ToolContext(
        3,
        "Join",
        {"@joinByRecordPos": "True", "JoinExpression": "[L:key] = [R:key]"},
        [1, 2],
        {"Left": 1, "Right": 2},
        {1: "df_1", 2: "df_2", 3: "df_3"},
        PathStyle(lambda *_: "", lambda *_: "", False),
        {},
        {},
    )
    code = gen_join(ctx).code
    assert "pd.merge" not in code
    assert "NotImplementedError" in code


def test_non_join_selection_is_not_applied():
    ctx = ToolContext(
        3,
        "Join",
        {
            "JoinExpression": "[L:key] = [R:key]",
            "SelectConfiguration": {
                "Configuration": {
                    "@outputConnection": "Left",
                    "SelectFields": {"SelectField": _row("Left_", "key", False)},
                }
            },
        },
        [1, 2],
        {"Left": 1, "Right": 2},
        {1: "df_1", 2: "df_2", 3: "df_3"},
        PathStyle(lambda *_: "", lambda *_: "", False),
        {},
        {},
    )
    assert "pd.merge" in gen_join(ctx).code
