import pytest

from yxray.alteryx_expr import ExprTranslationError, translate_expr


def t(expr: str) -> str:
    return translate_expr(expr, "df")


# ── Fields, literals, operators ─────────────────────────────────────────────


def test_field_reference() -> None:
    assert t("[Age] > 18") == 'df["Age"] > 18'


def test_equals_becomes_double_equals() -> None:
    assert t('[CAPEX/OPEX] = "CAPEX"') == 'df["CAPEX/OPEX"] == \'CAPEX\''


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
        "np.select([df[\"x\"] > 10, df[\"x\"] > 5], ['big', 'mid'],"
        " default='small')"
    )


def test_nested_if_in_then_branch() -> None:
    expr = 'IF [a] = 1 THEN IF [b] = 2 THEN "x" ELSE "y" ENDIF ELSE "z" ENDIF'
    assert t(expr) == (
        "np.where(df[\"a\"] == 1,"
        " np.where(df[\"b\"] == 2, 'x', 'y'), 'z')"
    )


def test_iif() -> None:
    assert t("IIF([x] > 0, 1, 0)") == 'np.where(df["x"] > 0, 1, 0)'


# ── Functions ───────────────────────────────────────────────────────────────


def test_isnull() -> None:
    assert t("IsNull([x])") == 'df["x"].isna()'


def test_isempty() -> None:
    assert t("IsEmpty([x])") == '(df["x"].isna() | (df["x"] == ""))'


def test_contains() -> None:
    assert (
        t('Contains([Name], "abc")')
        == "df[\"Name\"].str.contains('abc', case=False, na=False)"
    )


def test_trim_uppercase() -> None:
    assert t("Trim([x])") == 'df["x"].str.strip()'
    assert t("Uppercase([x])") == 'df["x"].str.upper()'


def test_tonumber() -> None:
    assert t("ToNumber([x])") == 'pd.to_numeric(df["x"], errors="coerce")'


def test_in_list() -> None:
    assert t('[x] IN ("a", "b")') == "df[\"x\"].isin(['a', 'b'])"


def test_unknown_function_kept_verbatim() -> None:
    assert (
        t('DateTimeDiff([a], [b], "days")')
        == "DateTimeDiff(df[\"a\"], df[\"b\"], 'days')"
    )


def test_comments_stripped() -> None:
    assert t("[a] > 1 // check\n/* block */ AND [b] > 2") == (
        '(df["a"] > 1) & (df["b"] > 2)'
    )


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
