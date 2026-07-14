from yxray.config_utils import comment_safe, operand_literal, py_str


def test_py_str_plain_identifier_is_double_quoted() -> None:
    # Unchanged from the old '"{name}"' interpolation for normal names.
    assert py_str("Score") == '"Score"'


def test_py_str_keeps_non_ascii_readable() -> None:
    # ensure_ascii=False — Japanese names stay literal, not \uXXXX-escaped.
    assert py_str("日付列") == '"日付列"'


def test_py_str_escapes_embedded_quote() -> None:
    # A double-quote in the name must not break the generated literal.
    literal = py_str('Sales "Amount"')
    assert eval(literal) == 'Sales "Amount"'


def test_py_str_escapes_backslash_and_newline() -> None:
    for value in ("a\\b", "line1\nline2", 'q"uote', "tab\there"):
        literal = py_str(value)
        # The literal is valid Python and round-trips to the original value.
        assert eval(literal) == value


def test_py_str_coerces_non_str() -> None:
    assert eval(py_str(42)) == "42"


def test_comment_safe_single_line_unchanged() -> None:
    assert comment_safe("[Status] = 1") == "[Status] = 1"


def test_comment_safe_collapses_newlines() -> None:
    # A newline would otherwise end the comment and expose the rest as code.
    assert (
        comment_safe('[Status] = "A"\nOR [Flag] = 1')
        == '[Status] = "A" OR [Flag] = 1'
    )
    assert comment_safe("a\r\nb") == "a b"
    assert comment_safe("a\n\n\nb") == "a b"


def test_operand_literal_numeric_unquoted() -> None:
    assert operand_literal("42") == "42"
    assert operand_literal("-3.5") == "-3.5"


def test_operand_literal_string_is_safe_literal() -> None:
    assert operand_literal("Active") == '"Active"'
    # A quote in the operand no longer breaks the generated code.
    assert eval(operand_literal('a"b')) == 'a"b'
