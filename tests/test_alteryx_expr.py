import pytest

from yxray.alteryx_expr import (
    ExprTranslationError,
    translate_expr,
    translate_filter_masks,
)


def t(expr: str) -> str:
    return translate_expr(expr, "df").code


# ── Fields, literals, operators ─────────────────────────────────────────────


def test_field_reference() -> None:
    assert t("[Age] > 18") == 'df["Age"] > 18'


def test_equals_becomes_double_equals() -> None:
    assert t('[CAPEX/OPEX] = "CAPEX"') == "df[\"CAPEX/OPEX\"] == 'CAPEX'"


def test_not_equals_diamond() -> None:
    assert t("[a] <> 1") == 'df["a"] != 1'


def test_arithmetic() -> None:
    assert t("[Price] * [Qty] + 10") == 'df["Price"] * df["Qty"] + 10'


def test_unary_minus() -> None:
    assert t("-[x] + 1") == '-df["x"] + 1'


# ── Boolean logic: comparisons must be parenthesized under & and | ─────────


def test_and_parenthesizes_comparisons() -> None:
    assert t("[a] = 1 AND [b] = 2") == '(df["a"] == 1) & (df["b"] == 2)'


def test_or_and_precedence() -> None:
    assert (
        t("[a] = 1 OR [b] = 2 AND [c] = 3")
        == '(df["a"] == 1) | (df["b"] == 2) & (df["c"] == 3)'
    )


def test_not() -> None:
    assert t("NOT [a] = 1") == '~(df["a"] == 1)'


def test_bang_not() -> None:
    assert t('!Contains([x], "abc")') == (
        "~df[\"x\"].str.contains('abc', case=False, regex=False, na=False)"
    )


def test_bang_not_combined_with_and() -> None:
    assert (
        t('!Contains([a], "x") AND Contains([b], "y")')
        == "~df[\"a\"].str.contains('x', case=False, regex=False, na=False)"
        " & df[\"b\"].str.contains('y', case=False, regex=False, na=False)"
    )


def test_keywords_case_insensitive() -> None:
    assert t("[a] = 1 and [b] = 2") == '(df["a"] == 1) & (df["b"] == 2)'


# ── IF / IIF ────────────────────────────────────────────────────────────────


def test_if_then_else() -> None:
    assert (
        t('IF [x] > 1 THEN "hi" ELSE "lo" ENDIF')
        == "np.where(df[\"x\"] > 1, 'hi', 'lo')"
    )


def test_if_without_else_defaults_to_nan() -> None:
    assert t('IF [x] > 1 THEN "hi" ENDIF') == "np.where(df[\"x\"] > 1, 'hi', np.nan)"


def test_elseif_chain_becomes_select() -> None:
    expr = 'IF [x] > 10 THEN "big" ELSEIF [x] > 5 THEN "mid" ELSE "small" ENDIF'
    assert t(expr) == (
        "np.select([df[\"x\"] > 10, df[\"x\"] > 5], ['big', 'mid'], default='small')"
    )


def test_nested_if_in_then_branch() -> None:
    expr = 'IF [a] = 1 THEN IF [b] = 2 THEN "x" ELSE "y" ENDIF ELSE "z" ENDIF'
    assert t(expr) == (
        "np.where(df[\"a\"] == 1, np.where(df[\"b\"] == 2, 'x', 'y'), 'z')"
    )


def test_iif() -> None:
    assert t("IIF([x] > 0, 1, 0)") == 'np.where(df["x"] > 0, 1, 0)'


# ── Missing-value fill peephole ─────────────────────────────────────────────
# An IF whose ELSE hands back the column it just tested for missing is a
# fill, not a branch. np.where would translate it correctly but returns an
# ndarray, dropping the column's dtype (Int64 -> float64, string/category
# -> object) — precisely on the columns a fill targets.


def test_isnull_fill_becomes_fillna() -> None:
    translation = translate_expr("IF IsNull([Amount]) THEN 0 ELSE [Amount] ENDIF", "df")
    assert translation.code == 'df["Amount"].fillna(0)'
    # No np.* on this path, so the block must not pull in numpy.
    assert translation.uses_numpy is False
    assert translation.uses_fill_empty is False


def test_isempty_fill_becomes_fill_empty_helper() -> None:
    # No pandas built-in covers NULL-or-empty: fillna() alone would leave
    # "" in place, so this one needs the reference_impl helper.
    translation = translate_expr(
        'IF IsEmpty([Status]) THEN "N/A" ELSE [Status] ENDIF', "df"
    )
    assert translation.code == "fill_empty(df[\"Status\"], 'N/A')"
    assert translation.uses_fill_empty is True
    assert translation.uses_numpy is False


def test_iif_missing_fill_uses_the_same_peephole() -> None:
    assert t("IIF(IsNull([Amount]), 0, [Amount])") == 'df["Amount"].fillna(0)'
    assert (
        t('IIF(IsEmpty([Status]), "N/A", [Status])')
        == "fill_empty(df[\"Status\"], 'N/A')"
    )


def test_missing_fill_value_may_be_another_column() -> None:
    # Both fillna() and fill_empty() align a Series argument on the index.
    assert t("IF IsNull([A]) THEN [B] ELSE [A] ENDIF") == 'df["A"].fillna(df["B"])'


def test_missing_fill_matches_expressions_not_just_columns() -> None:
    # The tested operand is an expression; folding it into the helper also
    # evaluates it once instead of the three times a literal translation
    # would produce.
    assert (
        t('IF IsEmpty(Trim([S])) THEN "-" ELSE Trim([S]) ENDIF')
        == "fill_empty(df[\"S\"].str.strip(), '-')"
    )


def test_null_literal_as_fill_value_still_reports_numpy() -> None:
    translation = translate_expr("IF IsEmpty([S]) THEN Null() ELSE [S] ENDIF", "df")
    assert translation.code == 'fill_empty(df["S"], np.nan)'
    assert translation.uses_fill_empty is True
    # np.nan comes from Null(), so numpy is still needed here.
    assert translation.uses_numpy is True


def test_negated_test_is_the_same_fill_with_the_branches_swapped() -> None:
    # Alteryx authors write the test either way round and mean the same
    # thing; !IsEmpty(...) THEN [c] keeps the value in the THEN branch.
    translation = translate_expr('IF !IsEmpty([S]) THEN [S] ELSE "N/A" ENDIF', "df")
    assert translation.code == "fill_empty(df[\"S\"], 'N/A')"
    assert translation.uses_numpy is False
    assert translation.uses_fill_empty is True


def test_negated_isnull_fill_becomes_fillna() -> None:
    assert t("IF !IsNull([A]) THEN [A] ELSE 0 ENDIF") == 'df["A"].fillna(0)'


def test_not_keyword_negation_is_recognised_too() -> None:
    # NOT and ! emit the same `~`, so both reach the peephole.
    assert t("IF NOT IsNull([A]) THEN [A] ELSE 0 ENDIF") == 'df["A"].fillna(0)'


def test_negated_iif_fill_uses_the_peephole() -> None:
    assert t('IIF(!IsEmpty([S]), [S], "N/A")') == "fill_empty(df[\"S\"], 'N/A')"


def test_negated_fill_matches_expressions_not_just_columns() -> None:
    assert (
        t('IF !IsEmpty(Trim([S])) THEN Trim([S]) ELSE "-" ENDIF')
        == "fill_empty(df[\"S\"].str.strip(), '-')"
    )


def test_negated_test_with_a_different_then_column_is_not_a_fill() -> None:
    assert (
        t("IF !IsNull([A]) THEN [B] ELSE 0 ENDIF")
        == 'np.where(~df["A"].isna(), df["B"], 0)'
    )


def test_negated_non_missing_test_is_not_a_fill() -> None:
    # A `~` in front of something that is not a missing test must not be
    # mistaken for the negated fill shape.
    assert (
        t("IF ![A] > 1 THEN [A] ELSE 0 ENDIF") == 'np.where(~(df["A"] > 1), df["A"], 0)'
    )


def test_different_else_column_is_not_a_fill() -> None:
    # ELSE hands back a *different* column: both branches produce new
    # values, so this is a genuine branch and stays np.where.
    translation = translate_expr("IF IsNull([A]) THEN 0 ELSE [B] ENDIF", "df")
    assert translation.code == 'np.where(df["A"].isna(), 0, df["B"])'
    assert translation.uses_numpy is True
    assert translation.uses_fill_empty is False


def test_transformed_else_branch_is_not_a_fill() -> None:
    assert (
        t("IF IsNull([A]) THEN 0 ELSE [A] * 2 ENDIF")
        == 'np.where(df["A"].isna(), 0, df["A"] * 2)'
    )


def test_missing_else_is_not_a_fill() -> None:
    # No ELSE means non-matching rows become NULL, not the original value.
    assert t("IF IsNull([A]) THEN 0 ENDIF") == 'np.where(df["A"].isna(), 0, np.nan)'


def test_elseif_chain_is_not_a_fill() -> None:
    assert (
        t("IF IsNull([A]) THEN 0 ELSEIF [A] > 5 THEN 1 ELSE [A] ENDIF")
        == 'np.select([df["A"].isna(), df["A"] > 5], [0, 1], default=df["A"])'
    )


# ── Functions ───────────────────────────────────────────────────────────────


def test_isnull() -> None:
    assert t("IsNull([x])") == 'df["x"].isna()'


def test_isempty() -> None:
    assert t("IsEmpty([x])") == '(df["x"].isna() | (df["x"] == ""))'


def test_contains() -> None:
    assert (
        t('Contains([Name], "abc")')
        == "df[\"Name\"].str.contains('abc', case=False, regex=False, na=False)"
    )


def test_trim_uppercase() -> None:
    assert t("Trim([x])") == 'df["x"].str.strip()'
    assert t("Uppercase([x])") == 'df["x"].str.upper()'


def test_tonumber() -> None:
    assert t("ToNumber([x])") == 'pd.to_numeric(df["x"], errors="coerce")'


def test_tostring_uses_string_dtype() -> None:
    # .astype(str) would turn missing values into the literal "nan"
    assert t("ToString([x])") == 'df["x"].astype("string")'


def test_tostring_decimal_places() -> None:
    assert t("ToString([x], 2)") == (
        'df["x"].map(lambda v: format(v, ".2f") if pd.notna(v) else pd.NA)'
        '.astype("string")'
    )


def test_tostring_decimal_places_and_grouping() -> None:
    assert t("ToString([x], 0, 1)") == (
        'df["x"].map(lambda v: format(v, ",.0f") if pd.notna(v) else pd.NA)'
        '.astype("string")'
    )
    result = translate_expr("ToString([x], 0, 1)", "df")
    assert result.uses_tostring_format is True


def test_tostring_grouping_zero_is_no_grouping() -> None:
    assert t("ToString([x], 1, 0)") == (
        'df["x"].map(lambda v: format(v, ".1f") if pd.notna(v) else pd.NA)'
        '.astype("string")'
    )


def test_tostring_without_format_args_does_not_set_flag() -> None:
    assert translate_expr("ToString([x])", "df").uses_tostring_format is False


def test_tostring_with_non_literal_decimal_places_raises() -> None:
    # A per-row decimal count has no simple vectorized equivalent.
    with pytest.raises(ExprTranslationError):
        t("ToString([x], [Decimals], 1)")


def test_tostring_with_non_literal_grouping_raises() -> None:
    with pytest.raises(ExprTranslationError):
        t("ToString([x], 2, [Grouping])")


def test_tostring_with_too_many_args_raises() -> None:
    with pytest.raises(ExprTranslationError):
        t("ToString([x], 2, 1, 1)")


def test_in_list() -> None:
    assert t('[x] IN ("a", "b")') == "df[\"x\"].isin(['a', 'b'])"


def test_substring_with_length() -> None:
    # 0-indexed: Substring("DENVER", 2, 3) == "NVE"
    assert t("Substring([field], 5, 2)") == 'df["field"].str[5:5+2]'


def test_substring_without_length() -> None:
    assert t("Substring([field], 3)") == 'df["field"].str[3:]'


def test_substring_zero_indexed_denver() -> None:
    # Regression: Substring("DENVER", 2, 3) == "NVE", not "ENV"
    assert t("Substring([City], 2, 3)") == 'df["City"].str[2:2+3]'


def test_left() -> None:
    assert t("Left([field], 3)") == 'df["field"].str[:3]'


def test_right() -> None:
    assert t("Right([field], 2)") == 'df["field"].str[-2:]'


def test_right_expression_length_parenthesized() -> None:
    # Regression: str[-1 + 1:] is str[0:] — the whole string, silently wrong
    assert t("Right([field], 1 + 1)") == 'df["field"].str[-(1 + 1):]'


def test_datetimeadd_months() -> None:
    assert (
        t('DateTimeAdd(DateTimeToday(), -2, "months")')
        == "pd.Timestamp.today().normalize() + pd.DateOffset(months=-2)"
    )


def test_datetimeadd_days() -> None:
    assert t('DateTimeAdd([dt], 7, "days")') == 'df["dt"] + pd.DateOffset(days=7)'


def test_todate() -> None:
    assert t('ToDate("2024-01-01")') == "pd.to_datetime('2024-01-01')"


def test_unknown_function_kept_verbatim() -> None:
    assert (
        t('DateTimeDiff([a], [b], "days")')
        == 'DateTimeDiff(df["a"], df["b"], \'days\')'
    )


def test_comments_stripped() -> None:
    assert t("[a] > 1 // check\n/* block */ AND [b] > 2") == (
        '(df["a"] > 1) & (df["b"] > 2)'
    )


# ── translate_filter_masks: top-level AND/OR splitting ─────────────────────


def test_masks_and_chain_splits_operands() -> None:
    result = translate_filter_masks("[a] = 1 AND [b] = 2 AND [c] = 3", "df")
    assert result.joiner == "&"
    assert [m.code for m in result.masks] == [
        'df["a"] == 1',
        'df["b"] == 2',
        'df["c"] == 3',
    ]
    assert [m.fragment for m in result.masks] == [
        "[a] = 1",
        "[b] = 2",
        "[c] = 3",
    ]


def test_masks_or_chain_splits_operands() -> None:
    result = translate_filter_masks("[a] = 1 OR [b] = 2", "df")
    assert result.joiner == "|"
    assert [m.fragment for m in result.masks] == ["[a] = 1", "[b] = 2"]


def test_masks_split_one_level_only_or_wins() -> None:
    # AND binds tighter, so the AND group is a single OR operand.
    result = translate_filter_masks("[a] = 1 OR [b] = 2 AND [c] = 3", "df")
    assert result.joiner == "|"
    assert [m.fragment for m in result.masks] == [
        "[a] = 1",
        "[b] = 2 AND [c] = 3",
    ]


def test_masks_leading_and_group_folds_into_or_operand() -> None:
    result = translate_filter_masks("[a] = 1 AND [b] = 2 OR [c] = 3", "df")
    assert result.joiner == "|"
    assert [m.fragment for m in result.masks] == [
        "[a] = 1 AND [b] = 2",
        "[c] = 3",
    ]


def test_masks_single_condition_is_one_mask() -> None:
    result = translate_filter_masks("[Age] > 18", "df")
    assert len(result.masks) == 1
    assert result.combined == 'df["Age"] > 18'


def test_masks_if_expression_is_one_mask() -> None:
    expr = 'IF [x] > 1 THEN "hi" ELSE "lo" ENDIF'
    result = translate_filter_masks(expr, "df")
    assert len(result.masks) == 1
    assert result.masks[0].fragment == expr


def test_masks_parenthesized_chain_is_one_mask() -> None:
    # Splitting is top-level only; a parenthesized chain is a single atom.
    result = translate_filter_masks("([a] = 1 AND [b] = 2)", "df")
    assert len(result.masks) == 1


@pytest.mark.parametrize(
    "expr",
    [
        "[Age] > 18",
        '!Contains([Status], "drop") AND !IsEmpty([Status])',
        "[a] = 1 OR [b] = 2 AND [c] = 3",
        "[a] = 1 AND [b] = 2 OR [c] = 3",
        "NOT [a] = 1 AND [b] IN (1, 2)",
        'IF [x] > 1 THEN "hi" ELSE "lo" ENDIF',
    ],
)
def test_masks_combined_matches_translate_expr(expr: str) -> None:
    result = translate_filter_masks(expr, "df")
    assert result.combined == translate_expr(expr, "df").code


def test_masks_fragments_drop_comments_and_newlines() -> None:
    expr = "[a] = 1 // note\nAND [b] = /* block\ncomment */ 2 AND\n[c] =\n3"
    result = translate_filter_masks(expr, "df")
    fragments = [m.fragment for m in result.masks]
    assert fragments == ["[a] = 1", "[b] = 2", "[c] = 3"]
    assert all("\n" not in f for f in fragments)


def test_masks_fragment_keeps_original_spacing_between_tokens() -> None:
    result = translate_filter_masks('[a]>1 AND Contains([b], "x")', "df")
    assert [m.fragment for m in result.masks] == [
        "[a]>1",
        'Contains([b], "x")',
    ]


def test_masks_empty_expression_raises() -> None:
    with pytest.raises(ExprTranslationError):
        translate_filter_masks("   ", "df")


def test_masks_untranslatable_raises() -> None:
    with pytest.raises(ExprTranslationError):
        translate_filter_masks("[a] = something", "df")


# ── Errors (callers fall back to plain substitution) ───────────────────────


def test_unbalanced_if_raises() -> None:
    with pytest.raises(ExprTranslationError):
        t('IF [x] > 1 THEN "hi"')


def test_bare_identifier_raises() -> None:
    with pytest.raises(ExprTranslationError):
        t("[a] = something")


def test_empty_expression_raises() -> None:
    with pytest.raises(ExprTranslationError):
        t("   ")


# ── uses_numpy: declared at emission, not re-derived from strings ──────────


def test_uses_numpy_false_for_plain_comparison() -> None:
    assert translate_expr("[Age] > 18", "df").uses_numpy is False


def test_uses_numpy_true_for_if_expression() -> None:
    assert translate_expr('IF [x] > 1 THEN "hi" ELSE "lo" ENDIF', "df").uses_numpy


def test_uses_numpy_true_for_iif() -> None:
    assert translate_expr("IIF([x] > 0, 1, 0)", "df").uses_numpy


def test_uses_numpy_true_for_null_function() -> None:
    assert translate_expr("Null()", "df").uses_numpy


def test_uses_numpy_false_for_pandas_only_functions() -> None:
    assert translate_expr("ToNumber([x]) + 1", "df").uses_numpy is False


def test_masks_report_numpy() -> None:
    with_np = translate_filter_masks("IF [x] > 1 THEN 1 ELSE 0 ENDIF", "df")
    without_np = translate_filter_masks("[a] = 1 AND [b] = 2", "df")
    assert with_np.uses_numpy is True
    assert without_np.uses_numpy is False
