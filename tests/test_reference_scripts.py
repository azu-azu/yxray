"""Behavior tests for the reference helpers in scripts/.

Generated scaffolds call these helpers without embedding their
definitions; these tests pin the runtime behavior the generated code
relies on.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves cls.__module__ through sys.modules — register
    # before exec so @dataclass works inside the loaded script
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


select_helpers = _load_script("apply_select_edits")
find_any = _load_script("simulate_find_any_append")


# ── apply_select_edits ──────────────────────────────────────────────────────


def test_apply_select_edits_unknown_deselected_keeps_only_selected() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": [2], "extra": [3]})
    out = select_helpers.apply_select_edits(df, [
        edit("a"),
        edit("b", "b2"),
        edit("*Unknown", selected=False),
    ])
    assert list(out.columns) == ["a", "b2"]


def test_apply_select_edits_ignores_absent_deselected_column() -> None:
    # Alteryx XML routinely carries stale field lists; dropping a column
    # that no longer exists must not raise KeyError.
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "unlisted": [2]})
    out = select_helpers.apply_select_edits(df, [
        edit("a", "id"),
        edit("gone", selected=False),
        edit("*Unknown"),
    ])
    assert list(out.columns) == ["id", "unlisted"]


def test_apply_select_edits_unknown_selected_keeps_unlisted_columns() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": [2], "extra": [3]})
    out = select_helpers.apply_select_edits(df, [
        edit("a"),
        edit("b", selected=False),
        edit("*Unknown"),
    ])
    assert list(out.columns) == ["a", "extra"]


def test_apply_select_edits_unknown_deselected_skips_absent_selected() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1]})
    out = select_helpers.apply_select_edits(df, [
        edit("a"),
        edit("renamed_away", "x"),
        edit("*Unknown", selected=False),
    ])
    assert list(out.columns) == ["a"]


def test_apply_select_edits_type_string() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1, 2]})
    out = select_helpers.apply_select_edits(df, [edit("a", type="V_WString")])
    assert out["a"].dtype == "string"
    assert list(out["a"]) == ["1", "2"]


def test_apply_select_edits_type_int_sizes_and_rounding() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({
        "i16": ["1", "2"],
        "i64": ["3", "bad"],
        "dbl": [1.5, 2.4],
    })
    out = select_helpers.apply_select_edits(df, [
        edit("i16", type="Int16"),
        edit("i64", type="Int64"),
        edit("dbl", type="Int32"),
    ])
    assert out["i16"].dtype == "Int16"
    assert out["i64"].dtype == "Int64"
    # 変換失敗は Alteryx の Conversion Error と同じく null
    assert out["i64"].isna().iloc[1]
    # Double→Int は四捨五入（切り捨てだと astype が落ちるうえ Alteryx と不一致）
    assert out["dbl"].dtype == "Int32"
    assert list(out["dbl"]) == [2, 2]


def test_apply_select_edits_type_float_and_date() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({
        "f": ["1.5", ""],
        "d": ["2024-01-02 15:30:00", "not a date"],
        "dt": ["2024-01-02 15:30:00", None],
    })
    out = select_helpers.apply_select_edits(df, [
        edit("f", type="Double"),
        edit("d", type="Date"),
        edit("dt", type="DateTime"),
    ])
    assert out["f"].dtype == "float64"
    assert out["f"].iloc[0] == 1.5
    # Date は時刻部分を持たない（normalize）、DateTime は保持
    assert out["d"].iloc[0] == pd.Timestamp("2024-01-02")
    assert pd.isna(out["d"].iloc[1])
    assert out["dt"].iloc[0] == pd.Timestamp("2024-01-02 15:30:00")


def test_apply_select_edits_type_bool() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"b": ["1", "0", "True", "false", "junk"]})
    out = select_helpers.apply_select_edits(df, [edit("b", type="Bool")])
    assert out["b"].dtype == "boolean"
    assert list(out["b"][:4]) == [True, False, True, False]
    assert pd.isna(out["b"].iloc[4])


def test_apply_select_edits_type_applied_before_rename() -> None:
    # type は rename 前の列名で指定される（Alteryx XML と同じ）ため、
    # rename と併用しても変換が効くこと
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"old": ["1", "2"]})
    out = select_helpers.apply_select_edits(df, [
        edit("old", new_name="new", type="Int64"),
    ])
    assert list(out.columns) == ["new"]
    assert out["new"].dtype == "Int64"


def test_apply_select_edits_type_unsupported_or_absent_is_skipped() -> None:
    # 未対応型（Blob 等）と存在しない列は警告のみで落ちない
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    out = select_helpers.apply_select_edits(df, [
        edit("a", type="Blob"),
        edit("gone", type="Int64"),
        edit("b"),
        edit("*Unknown", selected=False),
    ])
    assert list(out.columns) == ["a", "b"]
    assert out["a"].iloc[0] == 1


def test_apply_select_edits_type_does_not_mutate_input() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": ["1"]})
    original_dtype = df["a"].dtype
    select_helpers.apply_select_edits(df, [edit("a", type="Int64")])
    assert df["a"].dtype == original_dtype
    assert df["a"].iloc[0] == "1"


# ── simulate_find_any_append ────────────────────────────────────────────────


def _run(targets, lookup, **kwargs):
    kwargs.setdefault("find_field", "text")
    kwargs.setdefault("search_field", "kw")
    kwargs.setdefault("append_fields", ["label"])
    return find_any.simulate_find_any_append(
        targets, lookup, verbose=False, **kwargs
    )


def test_find_any_substring_match_appends_and_keeps_row_count() -> None:
    targets = pd.DataFrame({"text": ["ABC-101-X", "no hit"]})
    lookup = pd.DataFrame({"kw": ["101"], "label": ["L1"]})
    out = _run(targets, lookup)
    assert len(out) == 2
    assert list(out["label"]) == ["L1", pd.NA]
    # output is "Targets columns + append_fields" only — the search key column
    # (kw / FieldSearch) is used to look up but never added to the output,
    # matching real Alteryx Append output
    assert list(out.columns) == ["text", "label"]


def test_find_any_multiple_matches_last_vs_first() -> None:
    targets = pd.DataFrame({"text": ["cherry apple pie"]})
    lookup = pd.DataFrame({"kw": ["apple", "cherry"], "label": ["APL", "CHR"]})
    last = _run(targets, lookup, replace_multiple_found=True)
    first = _run(targets, lookup, replace_multiple_found=False)
    # lookup-table order decides: last match wins with RMF=True, first with False
    assert last["label"].iloc[0] == "CHR"
    assert first["label"].iloc[0] == "APL"
    # never a join — one target stays one row either way
    assert len(last) == 1
    assert len(first) == 1


def test_find_any_nan_and_empty_needles_do_not_match() -> None:
    targets = pd.DataFrame({"text": ["nan value here", "anything"]})
    lookup = pd.DataFrame({"kw": [None, ""], "label": ["N", "E"]})
    out = _run(targets, lookup)
    assert out["label"].isna().all()


def test_find_any_nan_haystack_does_not_match_nan_needle_text() -> None:
    targets = pd.DataFrame({"text": [None, "real nan text"]})
    lookup = pd.DataFrame({"kw": ["nan"], "label": ["L"]})
    out = _run(targets, lookup)
    # row 0 is NaN → no match; row 1 contains the literal substring "nan"
    assert pd.isna(out["label"].iloc[0])
    assert out["label"].iloc[1] == "L"


def test_find_any_integer_float_promotion_still_matches() -> None:
    # a NaN in the column promotes int to float64 (123 → 123.0); _stringify
    # must drop the trailing ".0" so "123" still matches
    targets = pd.DataFrame({"text": [123, None]})
    lookup = pd.DataFrame({"kw": [123], "label": ["L"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "L"


def test_find_any_case_insensitive_matches_when_requested() -> None:
    targets = pd.DataFrame({"text": ["Apple Pie"]})
    lookup = pd.DataFrame({"kw": ["apple"], "label": ["L"]})
    sensitive = _run(targets, lookup, case_sensitive=True)
    insensitive = _run(targets, lookup, case_sensitive=False)
    assert pd.isna(sensitive["label"].iloc[0])
    assert insensitive["label"].iloc[0] == "L"


def test_find_any_rejects_column_overlap_with_targets() -> None:
    targets = pd.DataFrame({"text": ["x"], "label": ["existing"]})
    lookup = pd.DataFrame({"kw": ["x"], "label": ["L"]})
    with pytest.raises(ValueError) as excinfo:
        _run(targets, lookup)
    message = str(excinfo.value)
    # the message must name the offending column and tell the user to rename
    assert "label" in message
    assert "rename" in message


def test_find_any_same_name_key_does_not_collide() -> None:
    # FieldFind == FieldSearch (both "key"): the search value is used to look
    # up but never added to the output, so the key column is not duplicated
    # and no collision is raised.
    targets = pd.DataFrame({"key": ["ABC-101-X", "no hit"]})
    lookup = pd.DataFrame({"key": ["101"], "label": ["L1"]})
    out = find_any.simulate_find_any_append(
        targets,
        lookup,
        find_field="key",
        search_field="key",
        append_fields=["label"],
        verbose=False,
    )
    assert list(out.columns) == ["key", "label"]
    assert list(out["label"]) == ["L1", pd.NA]
    # the target's own key column is untouched (not overwritten by the needle)
    assert list(out["key"]) == ["ABC-101-X", "no hit"]
