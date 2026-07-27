"""Behavior tests for the reference helpers in reference_impl/.

Generated scaffolds call these helpers without embedding their
definitions; these tests pin the runtime behavior the generated code
relies on.
"""

import importlib.util
import inspect
import random
import sys
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


select_helpers = _load_script("apply_select_edits")
find_any = _load_script("simulate_find_any_append")


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


# ── simulate_find_any_append ────────────────────────────────────────────────


def _run(targets, lookup, **kwargs):
    kwargs.setdefault("find_field", "text")
    kwargs.setdefault("search_field", "kw")
    kwargs.setdefault("append_fields", ["label"])
    # case_sensitive has no default in the helper — callers must state it
    kwargs.setdefault("case_sensitive", True)
    return find_any.simulate_find_any_append(targets, lookup, verbose=False, **kwargs)


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
    loud = find_any.simulate_find_any_append(
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
        find_any.simulate_find_any_append(
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
    find_any.simulate_find_any_append(
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


def test_find_any_diagnostics_are_off_by_default(capsys) -> None:
    # The ambiguity scan is opt-in: it costs a lookup-rows x targets pass and
    # is a review aid, not something every run should pay for. Generated code
    # asks for it explicitly.
    assert (
        inspect.signature(find_any.simulate_find_any_append)
        .parameters["collect_match_diagnostics"]
        .default
        is False
    )

    targets = pd.DataFrame({"text": ["cherry apple pie", "no hit"]})
    lookup = pd.DataFrame({"kw": ["cherry", "apple"], "label": ["CHR", "APL"]})
    find_any.simulate_find_any_append(
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

    find_any.simulate_find_any_append(
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

    find_any.simulate_find_any_append(
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
        not in inspect.signature(find_any.simulate_find_any_append).parameters
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
    out = find_any.simulate_find_any_append(
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
