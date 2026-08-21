"""Behavior tests for the reference helpers in reference_impl/.

Generated scaffolds call most of these helpers without embedding their
definitions; these tests pin the runtime behavior the generated code
relies on. to_display_string is the exception — nothing generates a call
to it, so its tests pin what a reviewer gets when they add one by hand.
"""

import importlib.util
import inspect
import logging
import random
import sys
import time
from decimal import Decimal
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

_REFERENCE_IMPL_DIR = Path(__file__).resolve().parents[1] / "reference_impl"


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        name, _REFERENCE_IMPL_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves cls.__module__ through sys.modules — register
    # before exec so @dataclass works inside the loaded script
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


select_helpers = _load_script("select_edits")
find_any = _load_script("find_any_append")
fill = _load_script("fill_empty")
display = _load_script("to_display_string")


# ── to_display_string ───────────────────────────────────────────────────────


def test_to_display_string_drops_the_decimal_on_whole_numbers() -> None:
    # Alteryx renders an integer-valued number without ".0" when it turns
    # it into a string; astype("string") alone would give "1.0".
    out = display.to_display_string(pd.Series([1.0, 1.5, 12000.0]))
    assert list(out) == ["1", "1.5", "12000"]
    assert out.dtype == "string"


def test_to_display_string_keeps_missing_as_na_for_fill_empty() -> None:
    # Missing stays <NA> so the composition with fill_empty works: the
    # placeholder is applied after the numeric formatting.
    out = display.to_display_string(pd.Series([1.0, None]))
    assert out.isna().iloc[1]
    assert list(fill.fill_empty(out, "-")) == ["1", "-"]


def test_to_display_string_converts_real_floats_inside_an_object_column() -> None:
    # The columns generated code produces are routinely object (np.where
    # output, a column carrying a placeholder), and the numbers inside them
    # are still real floats. Gating on the column's dtype made this a
    # no-op — the case the helper exists for.
    out = display.to_display_string(
        pd.Series([1.0, 1.5, "001", "1.0", None], dtype="object")
    )
    assert list(out)[:4] == ["1", "1.5", "001", "1"]
    assert out.isna().iloc[4]


def test_to_display_string_leaves_zero_padded_codes_alone() -> None:
    # "001" -> "1" would silently corrupt an ID column. A leading zero is
    # never trimmed, whether the column is object or string dtype, and even
    # when a real number or a trimmable "1.0" sits beside it.
    assert list(display.to_display_string(pd.Series(["001", "1.0"]))) == ["001", "1"]
    assert list(display.to_display_string(pd.Series(["001"], dtype="string"))) == [
        "001"
    ]
    assert list(display.to_display_string(pd.Series(["001", 1.0], dtype="object"))) == [
        "001",
        "1",
    ]


def test_to_display_string_leaves_booleans_as_words() -> None:
    # bool is a subclass of int, so without the explicit exclusion
    # True/False would come out as "1"/"0" — in a bool column and in an
    # object column alike.
    assert list(display.to_display_string(pd.Series([True, False]))) == [
        "True",
        "False",
    ]
    assert list(display.to_display_string(pd.Series([True, 1.0], dtype="object"))) == [
        "True",
        "1",
    ]


def test_to_display_string_handles_decimal_cells() -> None:
    # Decimal is not registered as numbers.Real, so it needs naming
    # explicitly — apply_select_edits points at Decimal for FixedDecimal
    # columns that need the precision.
    out = display.to_display_string(
        pd.Series([Decimal("1.0"), Decimal("1.5")], dtype="object")
    )
    assert list(out) == ["1", "1.5"]


def test_to_display_string_leaves_dates_alone() -> None:
    # The worst silent failure: a datetime column formatted as a number
    # becomes an epoch integer, and NaT becomes int64 min. Masking with
    # .where() on the original dtype reintroduces this — the non-matching
    # cells come back as NaT, which pd.to_numeric reads as int64 min and
    # whose .abs() overflows past the range guard.
    out = display.to_display_string(pd.Series(pd.to_datetime(["2024-01-01", None])))
    assert list(out)[0].startswith("2024-01-01")
    assert out.isna().iloc[1]
    # Same for a Timestamp sitting in an object column next to a number.
    mixed = display.to_display_string(
        pd.Series([pd.Timestamp("2024-01-01"), 1.0], dtype="object")
    )
    assert list(mixed)[0].startswith("2024-01-01")
    assert list(mixed)[1] == "1"


def test_to_display_string_survives_a_duplicate_index() -> None:
    # Filters and concat leave duplicate labels behind; assigning an
    # index-aligned Series into the result raises "cannot reindex on an
    # axis with duplicate labels" there.
    out = display.to_display_string(pd.Series([1.0, 2.0, "x"], index=[0, 0, 1]))
    assert list(out) == ["1", "2", "x"]


def test_to_display_string_survives_a_non_default_index() -> None:
    out = display.to_display_string(pd.Series([1.0, 2.5], index=[5, 9]))
    assert list(out) == ["1", "2.5"]


def test_to_display_string_does_not_overflow_on_huge_floats() -> None:
    # astype("Int64") on 1e300 raises "cannot safely cast"; values outside
    # the Int64 range keep their plain representation instead.
    out = display.to_display_string(pd.Series([1e300, float("inf"), 1.0]))
    assert list(out) == ["1e+300", "inf", "1"]


def test_to_display_string_handles_nullable_integer_columns() -> None:
    out = display.to_display_string(pd.Series([1, None], dtype="Int64"))
    assert list(out)[0] == "1"
    assert out.isna().iloc[1]


def test_to_display_string_does_not_mutate_its_input() -> None:
    s = pd.Series([1.0, 2.5])
    display.to_display_string(s)
    assert s.dtype == "float64"
    assert list(s) == [1.0, 2.5]


def test_to_display_string_then_fill_empty_is_the_documented_order() -> None:
    # The Size case: a Double column that needs a text placeholder.
    size = pd.Series([1.0, None, 12000.0])
    assert list(fill.fill_empty(display.to_display_string(size), "-")) == [
        "1",
        "-",
        "12000",
    ]
    # Either order produces the same values, now that the numbers inside
    # the object column the fill leaves behind are still recognised.
    assert list(display.to_display_string(fill.fill_empty(size, "-"))) == [
        "1",
        "-",
        "12000",
    ]


def test_to_display_string_formats_values_that_are_already_text() -> None:
    # Columns routinely arrive pre-stringified (read_csv with dtype=str, an
    # upstream np.where), so the number never reaches this function as a
    # float. Trimming a zero fraction off a canonical decimal covers that
    # without parsing the column, so nothing can be lost.
    text = pd.Series(["1.0", "1.5", "12000.0", "10.00"], dtype="object")
    assert list(display.to_display_string(text)) == ["1", "1.5", "12000", "10"]


@pytest.mark.parametrize(
    "value",
    [
        "001",  # a leading zero may be significant — a code, not a number
        "001.0",  # same, even with a zero fraction
        "SM",  # not a number at all; to_numeric would make this NaN
        "1e5",  # exponent form — rewriting it would look like a different value
        "-0.0",  # signed zero: do not invent "-0"
        " 1.0",  # not canonical; trimming whitespace is the caller's call
        "1,000.0",  # thousands separator
        "1.",  # no fraction digits
        "",
    ],
)
def test_to_display_string_only_trims_canonical_decimals(value) -> None:
    assert list(display.to_display_string(pd.Series([value], dtype="object"))) == [
        value
    ]


def test_prefixing_to_numeric_only_adds_normalization_and_loss() -> None:
    # The comparison behind "default to no pd.to_numeric" in section 20.
    # Both routes agree on canonical text; where they differ, the parsing
    # route either normalizes a non-canonical form or destroys a value.
    source = pd.Series(
        ["1.0", "12000.0", "1.50", "01.0", "1e5", "001", "SM", "1,000.0"],
        dtype="object",
    )
    plain = list(fill.fill_empty(display.to_display_string(source), "-"))
    parsed = list(
        fill.fill_empty(
            display.to_display_string(pd.to_numeric(source, errors="coerce")), "-"
        )
    )
    assert plain[:2] == parsed[:2] == ["1", "12000"]
    # Extra normalization the parsing route buys.
    assert plain[2:5] == ["1.50", "01.0", "1e5"]
    assert parsed[2:5] == ["1.5", "1", "100000"]
    # What it costs: a code loses its padding, and two values disappear
    # behind the placeholder.
    assert plain[5:] == ["001", "SM", "1,000.0"]
    assert parsed[5:] == ["1", "-", "-"]


def test_parsing_text_back_to_numbers_gives_the_same_result() -> None:
    # pd.to_numeric first also works, but it is the lossy route (see the
    # test below) — the helper handles the common case without it.
    text = pd.Series(["1.0", "1.5", "", None, "12000.0"], dtype="object")
    numeric = pd.to_numeric(text, errors="coerce")
    expected = ["1", "1.5", "-", "-", "12000"]
    assert list(fill.fill_empty(display.to_display_string(numeric), "-")) == expected
    assert list(fill.fill_empty(display.to_display_string(text), "-")) == expected


def test_coercing_text_silently_drops_non_numeric_values() -> None:
    # Why the helper trims text instead of parsing the column: coercion
    # turns "SM" and "XL" into NaN, and the fill then paints them with the
    # placeholder, so the loss is invisible in the output. Same shape of
    # problem as the Conversion Error warning in apply_select_edits.
    source = pd.Series(["1.0", "SM", "XL", "", "3.0"], dtype="object")
    numeric = pd.to_numeric(source, errors="coerce")
    assert list(fill.fill_empty(display.to_display_string(numeric), "-")) == [
        "1",
        "-",
        "-",
        "-",
        "3",
    ]
    lost = numeric.isna() & source.notna() & source.ne("")
    assert sorted(source[lost]) == ["SM", "XL"]
    # Straight through the helper, the size labels survive.
    assert list(fill.fill_empty(display.to_display_string(source), "-")) == [
        "1",
        "SM",
        "XL",
        "-",
        "3",
    ]


def test_filling_before_formatting_can_raise_on_a_nullable_column() -> None:
    # Why the documented order is still stringify-then-fill: fill_empty
    # preserves dtype, so a text placeholder in an Int64 column raises.
    # After to_display_string the column is text and the fill always fits.
    nullable = pd.Series([1, None], dtype="Int64")
    with pytest.raises(TypeError):
        fill.fill_empty(nullable, "-")
    assert list(fill.fill_empty(display.to_display_string(nullable), "-")) == ["1", "-"]


# ── fill_empty ──────────────────────────────────────────────────────────────


def test_fill_empty_fills_null_and_empty_string() -> None:
    s = pd.Series(["a", "", None])
    assert list(fill.fill_empty(s, "N/A")) == ["a", "N/A", "N/A"]


def test_fill_empty_leaves_whitespace_only_alone() -> None:
    # Alteryx IsEmpty() does not treat "   " as empty; the helper adds no
    # Trim() of its own — that stays visible in the Alteryx expression.
    assert list(fill.fill_empty(pd.Series(["   "]), "N/A")) == ["   "]


def test_fill_empty_accepts_a_series_as_the_fill_value() -> None:
    # IF IsEmpty([A]) THEN [B] ELSE [A] ENDIF — aligned on the index.
    a = pd.Series(["x", "", None])
    b = pd.Series(["b0", "b1", "b2"])
    assert list(fill.fill_empty(a, b)) == ["x", "b1", "b2"]


def test_fill_empty_does_not_mutate_its_input() -> None:
    s = pd.Series(["a", None])
    fill.fill_empty(s, "z")
    assert s.isna().iloc[1]


@pytest.mark.parametrize(
    ("series", "value"),
    [
        (pd.Series([1, 2, None], dtype="Int64"), 0),
        (pd.Series(["a", "", None], dtype="string"), "N/A"),
        (pd.Series(pd.Categorical(["x", None, "y"], categories=["x", "y", "z"])), "z"),
        (pd.Series(pd.to_datetime(["2024-01-01", None])), pd.Timestamp("2020-01-01")),
    ],
)
def test_fill_empty_preserves_dtype(series, value) -> None:
    # The whole reason this helper exists instead of np.where: np.where
    # returns an ndarray, so the filled column comes back as float64 /
    # object / str depending on the input. Losing the dtype on exactly the
    # columns a missing-value fill targets is what we are avoiding.
    assert fill.fill_empty(series, value).dtype == series.dtype


@pytest.mark.parametrize(
    ("series", "value"),
    [
        (pd.Series([1, 2, None], dtype="Int64"), 0),
        (pd.Series(["a", "", None], dtype="string"), "N/A"),
        (pd.Series(["a", "", None]), "N/A"),
        (pd.Series(pd.Categorical(["x", None, "y"], categories=["x", "y", "z"])), "z"),
        (pd.Series(pd.to_datetime(["2024-01-01", None])), pd.Timestamp("2020-01-01")),
    ],
)
def test_fill_empty_matches_df_loc_assignment(series, value) -> None:
    # The in-place form a reviewer would reach for by hand:
    #     mask = df[col].isna() | df[col].eq("")
    #     df.loc[mask, col] = value
    # Same values and same dtype — the helper returns a Series only so it
    # can also create a new column and stay one line per formula.
    df = pd.DataFrame({"c": series})
    df.loc[series.isna() | series.eq(""), "c"] = value
    expected = df["c"]
    actual = fill.fill_empty(series, value)
    assert actual.dtype == expected.dtype
    assert list(actual) == list(expected)


def test_fill_empty_raises_when_the_dtype_cannot_hold_the_value() -> None:
    # Filling an Int64 column with a string raises rather than silently
    # producing something else. This is the loud half of preserving dtype,
    # and it is a real behavior change from np.where, which returns
    # ['1.0', '2.0', 'N/A'] here — the integers stringified via float.
    with pytest.raises(TypeError):
        fill.fill_empty(pd.Series([1, 2, None], dtype="Int64"), "N/A")


# ── apply_select_edits ──────────────────────────────────────────────────────


def test_apply_select_edits_unknown_deselected_keeps_only_selected() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": [2], "extra": [3]})
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("a"),
            edit("b", "b2"),
            edit("*Unknown", selected=False),
        ],
    )
    assert list(out.columns) == ["a", "b2"]


def test_apply_select_edits_ignores_absent_deselected_column() -> None:
    # Alteryx XML routinely carries stale field lists; dropping a column
    # that no longer exists must not raise KeyError.
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "unlisted": [2]})
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("a", "id"),
            edit("gone", selected=False),
            edit("*Unknown"),
        ],
    )
    assert list(out.columns) == ["id", "unlisted"]


def test_apply_select_edits_unknown_selected_keeps_unlisted_columns() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": [2], "extra": [3]})
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("a"),
            edit("b", selected=False),
            edit("*Unknown"),
        ],
    )
    assert list(out.columns) == ["a", "extra"]


def test_apply_select_edits_unknown_deselected_skips_absent_selected() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1]})
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("a"),
            edit("renamed_away", "x"),
            edit("*Unknown", selected=False),
        ],
    )
    assert list(out.columns) == ["a"]


def test_apply_select_edits_type_string() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1, 2]})
    out = select_helpers.apply_select_edits(df, [edit("a", type="V_WString")])
    assert out["a"].dtype == "string"
    assert list(out["a"]) == ["1", "2"]


def test_apply_select_edits_type_int_sizes_and_rounding() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame(
        {
            "i16": ["1", "2"],
            "i64": ["3", "bad"],
            "dbl": [1.5, 2.4],
        }
    )
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("i16", type="Int16"),
            edit("i64", type="Int64"),
            edit("dbl", type="Int32"),
        ],
    )
    assert out["i16"].dtype == "Int16"
    assert out["i64"].dtype == "Int64"
    # 変換失敗は Alteryx の Conversion Error と同じく null
    assert out["i64"].isna().iloc[1]
    # Double→Int は四捨五入（切り捨てだと astype が落ちるうえ Alteryx と不一致）
    assert out["dbl"].dtype == "Int32"
    assert list(out["dbl"]) == [2, 2]


def test_apply_select_edits_type_float_and_date() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame(
        {
            "f": ["1.5", ""],
            "d": ["2024-01-02 15:30:00", "not a date"],
            "dt": ["2024-01-02 15:30:00", None],
        }
    )
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("f", type="Double"),
            edit("d", type="Date"),
            edit("dt", type="DateTime"),
        ],
    )
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
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("old", new_name="new", type="Int64"),
        ],
    )
    assert list(out.columns) == ["new"]
    assert out["new"].dtype == "Int64"


def test_apply_select_edits_type_unsupported_or_absent_is_skipped() -> None:
    # 未対応型（Blob 等）と存在しない列は警告のみで落ちない
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    out = select_helpers.apply_select_edits(
        df,
        [
            edit("a", type="Blob"),
            edit("gone", type="Int64"),
            edit("b"),
            edit("*Unknown", selected=False),
        ],
    )
    assert list(out.columns) == ["a", "b"]
    assert out["a"].iloc[0] == 1


def test_apply_select_edits_type_does_not_mutate_input() -> None:
    edit = select_helpers.SelectColumnEdit
    df = pd.DataFrame({"a": ["1"]})
    original_dtype = df["a"].dtype
    select_helpers.apply_select_edits(df, [edit("a", type="Int64")])
    assert df["a"].dtype == original_dtype
    assert df["a"].iloc[0] == "1"


# ── find_any_append ────────────────────────────────────────────────


def _run(targets, lookup, **kwargs):
    kwargs.setdefault("find_field", "text")
    kwargs.setdefault("search_field", "kw")
    kwargs.setdefault("append_fields", ["label"])
    # case_sensitive has no default in the helper — callers must state it
    kwargs.setdefault("case_sensitive", True)
    return find_any.find_any_append(targets, lookup, verbose=False, **kwargs)


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


def test_find_any_leftmost_match_wins_over_lookup_order() -> None:
    # lookup order is [cherry, apple] while "cherry" sits leftmost in the
    # text: the winner is decided by position in the target text, not by
    # lookup order. ReplaceMultipleFound does not change it either (both
    # settings golden-verified on the same data), which is why the helper
    # has no RMF argument at all.
    targets = pd.DataFrame({"text": ["cherry apple pie"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "CHR"
    # never a join — one target stays one row
    assert len(out) == 1


def test_find_any_golden_leftmost_match() -> None:
    # Pins the semantics measured on real Alteryx golden output, run with
    # BOTH ReplaceMultipleFound settings on the same data: the needle
    # appearing leftmost in the target text wins. Not the first matching
    # lookup row (row 0 would give A1 for "cherry apple pie") and not the
    # last (rows 1/4 would give C3) — and the golden output was identical
    # for RMF=True and RMF=False.
    targets = pd.DataFrame(
        {
            "text": [
                "cherry apple pie",  # apple & cherry match; cherry is leftmost
                "berry cherry jam",  # berry & cherry match; berry is leftmost
                "apple only",  # single match — control
                "no match here",  # no match — control
                "apple berry cherry mix",  # all three match; apple is leftmost
            ]
        }
    )
    lookup = pd.DataFrame(
        {
            "kw": ["apple", "berry", "cherry"],
            "label": ["A1", "B2", "C3"],
        }
    )
    expected = ["C3", "B2", "A1", pd.NA, "A1"]
    out = _run(targets, lookup)
    assert list(out["label"]) == expected
    # rows 0/1/4 match 2-3 lookup rows each and the count still does not
    # move: 1 target = 1 output row. The helper's summary log leaves this
    # invariant to the tests instead of printing before/after counts.
    assert len(out) == len(targets)


def test_find_any_same_start_earlier_lookup_row_wins() -> None:
    # "app" and "apple" both start at position 0 in "apple pie": the earlier
    # lookup row wins the tie, for BOTH RMF settings. Golden-verified on
    # real Alteryx output.
    targets = pd.DataFrame({"text": ["apple pie"]})
    lookup = pd.DataFrame({"kw": ["app", "apple"], "label": ["SHORT", "LONG"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "SHORT"


def test_find_any_same_start_tie_reversed_order() -> None:
    # Same nested needles with the lookup rows reversed: the earlier row
    # (now "apple") wins — golden-verified. This rules out length-based
    # models ("shorter needle" / "earliest end"), which would still pick
    # "app": the same-start tie goes to lookup order, not needle length.
    targets = pd.DataFrame({"text": ["apple pie"]})
    lookup = pd.DataFrame({"kw": ["apple", "app"], "label": ["LONG", "SHORT"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "LONG"


def test_find_any_leftmost_start_beats_earliest_end() -> None:
    # "apple" starts at 0 and ends at 5; "ppl" starts at 1 but ends at 4.
    # Golden-verified: "apple" wins — the START position decides, not the
    # end position ("first match to complete" would have picked "ppl").
    targets = pd.DataFrame({"text": ["apple pie"]})
    lookup = pd.DataFrame({"kw": ["apple", "ppl"], "label": ["LONG", "MID"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "LONG"


def test_find_any_duplicate_needle_last_row_wins() -> None:
    # The same search value on multiple lookup rows: the LAST row's values
    # are appended, for BOTH RMF settings (dictionary-style overwrite).
    # Golden-verified on real Alteryx output.
    targets = pd.DataFrame({"text": ["apple pie"]})
    lookup = pd.DataFrame({"kw": ["apple", "apple"], "label": ["X", "Y"]})
    out = _run(targets, lookup)
    assert out["label"].iloc[0] == "Y"


def test_find_any_nan_and_empty_needles_do_not_match() -> None:
    # golden-verified: real Alteryx also ignores empty-string and NULL search
    # values (a lookup with "", NULL and "apple" appends nothing to a
    # no-match target row)
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


def test_find_any_appended_integer_float_drops_dot_zero() -> None:
    # same float64 promotion on an APPEND column: a NaN in "code" turns 123
    # into 123.0, and the appended value must still read "123" — otherwise a
    # string comparison against golden output shows a phantom diff
    targets = pd.DataFrame({"text": ["apple pie", "nothing here"]})
    lookup = pd.DataFrame(
        {
            "kw": ["apple", "zzz"],
            "code": [123, None],
        }
    )
    out = _run(targets, lookup, append_fields=["code"])
    assert out["code"].iloc[0] == "123"
    # an unmatched target keeps NA (not the string "nan")
    assert pd.isna(out["code"].iloc[1])


def test_stringify_drops_dot_zero_only_for_integral_floats() -> None:
    assert find_any._stringify(123.0) == "123"
    assert find_any._stringify(123) == "123"
    assert find_any._stringify(1.5) == "1.5"
    assert find_any._stringify("apple") == "apple"


def test_find_any_appended_geometry_is_kept_raw_not_stringified() -> None:
    # SpatialObj (shapely Geometry) append values must not go through
    # _stringify: str(polygon) would expand every coordinate into a WKT
    # string, which is both slow for complex geometries and silently
    # replaces the intended spatial object with plain text.
    shapely_geometry = pytest.importorskip("shapely.geometry")
    polygon = shapely_geometry.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    targets = pd.DataFrame({"text": ["apple pie", "nothing here"]})
    lookup = pd.DataFrame(
        {
            "kw": ["apple", "zzz"],
            "SpatialObj": [polygon, None],
        }
    )
    out = _run(targets, lookup, append_fields=["SpatialObj"])
    assert out["SpatialObj"].iloc[0] is polygon
    assert pd.isna(out["SpatialObj"].iloc[1])


def test_find_any_is_geometry_never_touches_the_wkt_property(monkeypatch) -> None:
    # A prior version detected geometries with
    # hasattr(value, "geom_type") and hasattr(value, "wkt"). shapely's
    # wkt is a *property* that renders the full WKT string on every
    # access, so that "existence probe" was itself generating the huge
    # string it was supposed to avoid. isinstance() must be the entire
    # check — this pins that no attribute named "wkt" is ever touched by
    # making it raise if accessed, then asserting detection still works.
    shapely_geometry = pytest.importorskip("shapely.geometry")
    shapely_base = pytest.importorskip("shapely.geometry.base")

    def _poison(self: object) -> str:
        raise AssertionError(
            "wkt was accessed — geometry detection must use isinstance() only"
        )

    monkeypatch.setattr(shapely_base.BaseGeometry, "wkt", property(_poison))
    polygon = shapely_geometry.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert find_any._is_geometry(polygon) is True


def test_find_any_appended_many_distinct_geometries_are_all_kept_raw() -> None:
    # A single reused polygon can't catch a per-row geometry-detection bug:
    # the winner-selection cache stringifies each winning lookup row only
    # once, so with one polygon shared by every target row the check runs
    # once no matter how many target rows there are. Use a distinct polygon
    # per lookup row instead, so the cache can't hide a cost or a mistake
    # that only shows up once per distinct geometry.
    shapely_geometry = pytest.importorskip("shapely.geometry")
    row_count = 200
    polygons = [
        shapely_geometry.Polygon(
            [(x / 1000, (x / 1000) ** 2 + offset) for x in range(300)]
        )
        for offset in range(row_count)
    ]
    # fixed-width, delimited keys so no keyword is ever a substring of
    # another (e.g. "keyword_1" inside "keyword_10") — a collision there
    # would fail on the leftmost-match rule itself, not on geometry
    # handling, and would be mistaken for this test catching the bug
    keys = [f"KW{i:03d}X" for i in range(row_count)]
    targets = pd.DataFrame({"text": keys})
    lookup = pd.DataFrame({"kw": keys, "SpatialObj": polygons})
    out = _run(targets, lookup, append_fields=["SpatialObj"])
    assert all(
        actual is expected
        for actual, expected in zip(out["SpatialObj"], polygons, strict=True)
    )


def test_find_any_is_geometry_is_much_cheaper_than_probing_for_wkt() -> None:
    # Self-calibrating perf check (no wall-clock magic number, so it can't
    # be flaky on a slow CI box): isinstance() must stay far cheaper than
    # the old hasattr(value, "geom_type") and hasattr(value, "wkt") check,
    # measured on distinct complex polygons in the same run so only the
    # ratio matters. hasattr(value, "wkt") is what actually caused the
    # ~25s slowdown this fix addresses, since wkt is a property that
    # renders the whole geometry to WKT text on every access.
    shapely_geometry = pytest.importorskip("shapely.geometry")
    polygons = [
        shapely_geometry.Polygon(
            [(x / 1000, (x / 1000) ** 2 + offset) for x in range(20_000)]
        )
        for offset in range(20)
    ]

    def _is_geometry_via_hasattr(value: object) -> bool:
        return hasattr(value, "geom_type") and hasattr(value, "wkt")

    start = time.perf_counter()
    for polygon in polygons:
        find_any._is_geometry(polygon)
    fixed_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    for polygon in polygons:
        _is_geometry_via_hasattr(polygon)
    buggy_elapsed = time.perf_counter() - start

    assert fixed_elapsed * 20 < buggy_elapsed


def test_find_any_case_insensitive_matches_when_requested() -> None:
    targets = pd.DataFrame({"text": ["Apple Pie"]})
    lookup = pd.DataFrame({"kw": ["apple"], "label": ["L"]})
    sensitive = _run(targets, lookup, case_sensitive=True)
    insensitive = _run(targets, lookup, case_sensitive=False)
    assert pd.isna(sensitive["label"].iloc[0])
    assert insensitive["label"].iloc[0] == "L"


def test_find_any_case_insensitive_keeps_the_adoption_rules() -> None:
    # NoCase=True (case_sensitive=False) only widens what MATCHES; which
    # match wins is unchanged — still the needle appearing leftmost in the
    # target text, then lookup order for a tie. The first three rows are
    # golden-verified on real Alteryx output (NoCase=True over the same
    # apple/berry/cherry lookup as the 5-row leftmost golden); the last row
    # applies the golden same-start tie rule under NoCase.
    targets = pd.DataFrame(
        {
            "text": [
                "Cherry APPLE pie",  # both match case-insensitively; Cherry is leftmost
                "BERRY cherry jam",  # BERRY is leftmost
                "Apple only",  # single match — control
                "APP APPLE",  # tie at position 0 → earlier lookup row (app)
            ]
        }
    )
    lookup = pd.DataFrame(
        {
            "kw": ["apple", "berry", "cherry", "app"],
            "label": ["A1", "B2", "C3", "SHORT"],
        }
    )
    out = _run(targets, lookup, case_sensitive=False)
    assert list(out["label"]) == ["C3", "B2", "A1", "SHORT"]


def test_find_any_output_is_target_columns_plus_append_fields() -> None:
    # The output carries every original Targets column (in order) plus the
    # append_fields — and nothing else: not the search key column, not the
    # lookup columns left out of append_fields, not the internal row ids.
    targets = pd.DataFrame(
        {
            "text": ["apple pie", "no hit"],
            "other": ["keep", "keep"],
        }
    )
    lookup = pd.DataFrame(
        {
            "kw": ["apple"],
            "label": ["L"],
            "code": ["C"],
            "unused": ["U"],
        }
    )
    out = _run(targets, lookup, append_fields=["label", "code"])
    assert list(out.columns) == ["text", "other", "label", "code"]
    assert list(out["other"]) == ["keep", "keep"]


def test_find_any_verbose_summary_prints_and_keeps_result_identical() -> None:
    # The verbose branch builds a separate debug frame and prints a summary;
    # it must not leak debug columns into the result or blow up on the
    # ambiguous-rows table (2 lookup rows match row 0).
    targets = pd.DataFrame({"text": ["cherry apple pie", "no hit"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    quiet = _run(targets, lookup)
    loud = find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=True,
    )
    pd.testing.assert_frame_equal(loud, quiet)


def test_find_any_requires_an_explicit_case_sensitive() -> None:
    # case_sensitive has no default on purpose: whether case matters is a
    # translation decision the caller must state, not one the helper takes
    # on their behalf. The scaffold always emits it.
    targets = pd.DataFrame({"text": ["apple pie"]})
    lookup = pd.DataFrame({"kw": ["apple"], "label": ["L"]})
    with pytest.raises(TypeError):
        find_any.find_any_append(
            targets,
            lookup,
            find_field="text",
            search_field="kw",
            append_fields=["label"],
            verbose=False,
        )


def test_find_any_needles_are_matched_literally_not_as_regex() -> None:
    # The winner search compiles the needles into one alternation, so every
    # needle must be escaped: "1.5" must not match "125", "a+b" must not
    # match "aab", and "[xy]" must not match a bare "x".
    targets = pd.DataFrame({"text": ["125", "aab", "x", "1.5 exact", "[xy] exact"]})
    lookup = pd.DataFrame(
        {
            "kw": ["1.5", "a+b", "[xy]"],
            "label": ["DOT", "PLUS", "CLASS"],
        }
    )
    out = _run(targets, lookup)
    assert list(out["label"]) == [pd.NA, pd.NA, pd.NA, "DOT", "CLASS"]


def test_find_any_case_insensitive_duplicate_needle_keeps_earlier_row() -> None:
    # "Apple" and "apple" are different lookup values (both survive the
    # duplicate drop) that compare equal under NoCase. They match at the same
    # position, so the earlier lookup row wins and its own append values must
    # come back — the match must resolve to a lookup row, not merely to the
    # matched text.
    targets = pd.DataFrame({"text": ["APPLE pie"]})
    lookup = pd.DataFrame(
        {
            "kw": ["Apple", "apple"],
            "label": ["FIRST", "SECOND"],
            "code": ["C1", "C2"],
        }
    )
    out = _run(targets, lookup, append_fields=["label", "code"], case_sensitive=False)
    assert list(out.iloc[0][["label", "code"]]) == ["FIRST", "C1"]


def _brute_force_labels(targets, lookup, *, case_sensitive):
    """愚直な参照実装: 全 needle を試し「最も左、同点なら lookup 順で先の行」。

    実装とは独立に採用規則だけを書き下したオラクル。同じ検索値が複数行に
    あるときは後の行が有効（辞書的上書き）なので、先に最後の行だけ残す。
    """
    stringify = find_any._stringify
    last_row_of = {}
    for row, value in enumerate(lookup["kw"]):
        if pd.isna(value):
            continue
        last_row_of[value] = row
    kept = sorted(last_row_of.values())

    labels = []
    for raw_text in targets["text"]:
        if pd.isna(raw_text):
            labels.append(pd.NA)
            continue
        haystack = stringify(raw_text)
        if not case_sensitive:
            haystack = haystack.lower()
        best_pos, best_row = None, None
        for row in kept:
            needle = stringify(lookup["kw"].iloc[row])
            if not needle:
                continue
            if not case_sensitive:
                needle = needle.lower()
            pos = haystack.find(needle)
            if pos >= 0 and (best_pos is None or pos < best_pos):
                best_pos, best_row = pos, row
        if best_row is None:
            labels.append(pd.NA)
        else:
            value = lookup["label"].iloc[best_row]
            labels.append(stringify(value) if pd.notna(value) else pd.NA)
    return labels


def test_find_any_matches_the_brute_force_rule_on_random_frames() -> None:
    # Property test with a fixed seed: whatever the winner search does
    # internally, it must agree with the plainly written adoption rule on
    # nested and duplicate needles, ties, several match positions, regex
    # metacharacters, NaN/None/int/empty values, NoCase, and unmatched rows.
    rng = random.Random(20260727)
    alphabet = "abABC.*[]+?あ1"

    def word():
        return "".join(rng.choices(alphabet, k=rng.randint(1, 5)))

    for _ in range(150):
        texts = []
        for _ in range(rng.randint(1, 10)):
            roll = rng.random()
            if roll < 0.1:
                texts.append(None)
            elif roll < 0.16:
                texts.append(rng.randint(1, 200))
            elif roll < 0.2:
                texts.append("")
            else:
                texts.append(" ".join(word() for _ in range(rng.randint(1, 3))))
        kws, labels = [], []
        for i in range(rng.randint(1, 7)):
            roll = rng.random()
            kws.append(
                None
                if roll < 0.12
                else ""
                if roll < 0.2
                else rng.randint(1, 200)
                if roll < 0.26
                else word()
            )
            labels.append(f"L{i}")
        seed_text = next((t for t in texts if isinstance(t, str) and len(t) > 2), None)
        if seed_text is not None:
            # guarantee nested needles, an exact duplicate and a same-start tie
            kws += [seed_text[:1], seed_text[:2], seed_text[1:3], seed_text[:2]]
            labels += ["N1", "N2", "MID", "DUP"]
        targets = pd.DataFrame({"text": texts})
        lookup = pd.DataFrame({"kw": kws, "label": labels})
        for case_sensitive in (True, False):
            out = _run(targets, lookup, case_sensitive=case_sensitive)
            expected = _brute_force_labels(
                targets, lookup, case_sensitive=case_sensitive
            )
            assert list(out["label"]) == expected, (
                f"targets={texts} lookup={kws} case_sensitive={case_sensitive}"
            )


def test_find_any_diagnostics_off_returns_the_same_output() -> None:
    # collect_match_diagnostics decides how much is COMPUTED, never what is
    # returned: only the ambiguity counts go away. Everything the caller gets
    # back — values, row order, column order, dtypes, unmatched rows — must be
    # identical with the diagnostics on and off.
    cases = [
        # leftmost wins / several matches per target / no match
        (
            pd.DataFrame(
                {
                    "text": [
                        "cherry apple pie",
                        "berry cherry jam",
                        "apple only",
                        "no match here",
                        "apple berry cherry mix",
                    ]
                }
            ),
            pd.DataFrame(
                {"kw": ["apple", "berry", "cherry"], "label": ["A1", "B2", "C3"]}
            ),
            True,
        ),
        # nested needles, same-start tie
        (
            pd.DataFrame({"text": ["apple pie"]}),
            pd.DataFrame({"kw": ["app", "apple"], "label": ["SHORT", "LONG"]}),
            True,
        ),
        # duplicate needles, NULL/empty needles, NaN haystack
        (
            pd.DataFrame({"text": ["apple pie", None, "", 123]}),
            pd.DataFrame(
                {
                    "kw": ["apple", "apple", None, "", 123],
                    "label": ["X", "Y", "N", "E", "NUM"],
                }
            ),
            True,
        ),
        # NoCase
        (
            pd.DataFrame({"text": ["Cherry APPLE pie", "nothing"]}),
            pd.DataFrame({"kw": ["apple", "cherry"], "label": ["A1", "C3"]}),
            False,
        ),
    ]
    for targets, lookup, case_sensitive in cases:
        on = _run(targets, lookup, case_sensitive=case_sensitive)
        off = _run(
            targets,
            lookup,
            case_sensitive=case_sensitive,
            collect_match_diagnostics=False,
        )
        pd.testing.assert_frame_equal(off, on)


def test_find_any_diagnostics_off_still_applies_the_adoption_rule() -> None:
    # Regression test for the diagnostics-off path on its own terms: the
    # expected values are written out here, not taken from the other path.
    targets = pd.DataFrame(
        {
            "text": [
                "cherry apple pie",  # apple & cherry match; cherry is leftmost
                "berry cherry jam",  # berry & cherry match; berry is leftmost
                "apple only",  # single match
                "no match here",  # no match
                "apple berry cherry mix",  # all three match; apple is leftmost
            ]
        }
    )
    lookup = pd.DataFrame(
        {
            "kw": ["apple", "berry", "cherry"],
            "label": ["A1", "B2", "C3"],
        }
    )
    out = _run(targets, lookup, collect_match_diagnostics=False)
    assert list(out["label"]) == ["C3", "B2", "A1", pd.NA, "A1"]
    assert list(out.columns) == ["text", "label"]
    assert len(out) == len(targets)


def test_find_any_diagnostics_off_summary_drops_only_the_ambiguity_table(
    capsys,
) -> None:
    targets = pd.DataFrame({"text": ["cherry apple pie", "no hit"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=True,
        collect_match_diagnostics=False,
    )
    printed = capsys.readouterr().out
    # row and match counts survive — matched rows comes from the winner, not
    # from the diagnostics
    assert "rows          : 2" in printed
    assert "matched rows  : 1" in printed
    # the ambiguity table is gone, and says why rather than reading as zero
    assert "collect_match_diagnostics=False" in printed
    assert "== top 10 ==" not in printed


def test_find_any_logger_routes_the_summary_away_from_stdout(caplog, capsys) -> None:
    # Generated scaffolds hand the helper their module logger so its output
    # shares one path with every other tool's logger.info/logger.warning
    # instead of splitting across stdout.
    targets = pd.DataFrame({"text": ["cherry apple pie", "no hit"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    logger = logging.getLogger("find_any_append_test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        find_any.find_any_append(
            targets,
            lookup,
            find_field="text",
            search_field="kw",
            append_fields=["label"],
            case_sensitive=True,
            log_label="ToolID_7",
            logger=logger,
            verbose=True,
            collect_match_diagnostics=True,
        )

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "ToolID_7" in logged
    assert "rows          : 2" in logged
    assert "== top 10 ==" in logged
    # nothing printed: the whole point of passing a logger
    assert capsys.readouterr().out == ""
    # the blank lines that space the printed summary carry nothing as log
    # records, so they are dropped rather than emitted as empty INFO lines
    assert all(record.getMessage().strip() for record in caplog.records)


def test_find_any_without_logger_still_prints(capsys) -> None:
    # The default stays print: this file gets copied into notebooks and
    # ad-hoc scripts that never call logging.basicConfig, where logger.info
    # would fall under the root WARNING level and show nothing at all.
    targets = pd.DataFrame({"text": ["cherry apple pie"]})
    lookup = pd.DataFrame({"kw": ["cherry"], "label": ["CHR"]})
    find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=True,
    )
    assert "rows          : 1" in capsys.readouterr().out


def test_find_any_logger_is_silent_when_verbose_is_off(caplog) -> None:
    # logger decides where the output goes; verbose still decides whether
    # there is any.
    targets = pd.DataFrame({"text": ["cherry apple pie"]})
    lookup = pd.DataFrame({"kw": ["cherry"], "label": ["CHR"]})
    logger = logging.getLogger("find_any_append_quiet_test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        find_any.find_any_append(
            targets,
            lookup,
            find_field="text",
            search_field="kw",
            append_fields=["label"],
            case_sensitive=True,
            logger=logger,
            verbose=False,
        )
    assert caplog.records == []


def test_find_any_diagnostics_are_off_by_default(capsys) -> None:
    # The ambiguity scan is opt-in: it costs a lookup-rows x targets pass and
    # is a review aid, not something every run should pay for. Generated code
    # asks for it explicitly.
    assert (
        inspect.signature(find_any.find_any_append)
        .parameters["collect_match_diagnostics"]
        .default
        is False
    )

    targets = pd.DataFrame({"text": ["cherry apple pie", "no hit"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=True,
    )
    printed = capsys.readouterr().out
    assert "collect_match_diagnostics=False" in printed
    assert "matched rows  : 1" in printed


def test_find_any_diagnostics_are_only_scanned_when_something_reads_them(
    monkeypatch,
) -> None:
    # The diagnostics feed the verbose summary and nothing else — they are
    # not returned. Asking for them with verbose off would compute a
    # lookup-rows x targets scan that no one can read, so it is skipped.
    targets = pd.DataFrame({"text": ["cherry apple pie"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    calls = []
    real_scan = find_any._scan_diagnostics
    monkeypatch.setattr(
        find_any,
        "_scan_diagnostics",
        lambda *args, **kwargs: (calls.append(1), real_scan(*args, **kwargs))[1],
    )

    find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=False,
        collect_match_diagnostics=True,
    )
    assert calls == []

    find_any.find_any_append(
        targets,
        lookup,
        find_field="text",
        search_field="kw",
        append_fields=["label"],
        case_sensitive=True,
        verbose=True,
        collect_match_diagnostics=True,
    )
    assert len(calls) == 1


def test_find_any_has_no_replace_multiple_found_argument() -> None:
    # ReplaceMultipleFound has no effect on FindAny + Append output (golden-
    # verified with both settings), so the helper does not accept it —
    # keeping a no-op argument would suggest it changes something.
    assert (
        "replace_multiple_found"
        not in inspect.signature(find_any.find_any_append).parameters
    )


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
    out = find_any.find_any_append(
        targets,
        lookup,
        find_field="key",
        search_field="key",
        append_fields=["label"],
        case_sensitive=True,
        verbose=False,
    )
    assert list(out.columns) == ["key", "label"]
    assert list(out["label"]) == ["L1", pd.NA]
    # the target's own key column is untouched (not overwritten by the needle)
    assert list(out["key"]) == ["ABC-101-X", "no hit"]
