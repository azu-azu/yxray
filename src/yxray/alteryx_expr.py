"""Best-effort Alteryx expression → pandas/numpy translation.

translate_expr() covers the common Alteryx expression language:
[field] references, literals, arithmetic, comparisons (including = and
<>), AND/OR/NOT, IN (...), IF/ELSEIF/ELSE/ENDIF, IIF, and frequent
string/null functions. Anything it cannot confidently translate raises
ExprTranslationError so callers can fall back to plain [field]
substitution.

Emitted code assumes `np` (numpy) and `pd` (pandas) are in scope when
the corresponding constructs appear.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from yxray.config_utils import py_str

__all__ = [
    "ExprTranslationError",
    "FilterMask",
    "FilterTranslation",
    "translate_expr",
    "translate_filter_masks",
]


class ExprTranslationError(ValueError):
    """Raised when an expression cannot be confidently translated."""


# ── Tokenizer ──────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<comment>//[^\n]*|/\*.*?\*/)
    | (?P<num>\d+(?:\.\d+)?)
    | (?P<str>'[^']*'|"[^"]*")
    | (?P<field>\[[^\]]+\])
    | (?P<ident>[^\W\d]\w*)
    | (?P<op><=|>=|!=|<>|==|=|<|>|\+|-|\*|/|%|!)
    | (?P<lparen>\()
    | (?P<rparen>\))
    | (?P<comma>,)
    """,
    re.VERBOSE | re.DOTALL,
)

_KEYWORDS = frozenset(
    {"if", "then", "elseif", "else", "endif", "and", "or", "not", "in"}
)

_COMPARE_OPS = {
    "=": "==",
    "==": "==",
    "!=": "!=",
    "<>": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
}


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    # Source offsets, so operand fragments can be reconstructed for the
    # comments translate_filter_masks emits.
    start: int = 0
    end: int = 0


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise ExprTranslationError(f"unexpected character {expr[pos]!r}")
        start = pos
        pos = m.end()
        kind = m.lastgroup or ""
        if kind in ("ws", "comment"):
            continue
        tokens.append(_Token(kind, m.group(), start, pos))
    tokens.append(_Token("end", "", len(expr), len(expr)))
    return tokens


# ── Emission precedence (Python's, so parentheses land correctly) ──────────
# Comparisons bind *looser* than & and | in Python, so a comparison used
# as a boolean operand must be parenthesized.

_DATEOFFSET_UNITS = frozenset(
    {"years", "months", "days", "hours", "minutes", "seconds"}
)

_CMP = 1
_OR = 2
_AND = 3
_ADD = 4
_MUL = 5
_UNARY = 6
_ATOM = 10

_Emitted = tuple[str, int]  # (code, python precedence of its top operator)


def _paren(emitted: _Emitted, min_prec: int) -> str:
    code, prec = emitted
    return code if prec >= min_prec else f"({code})"


def _series(emitted: _Emitted) -> str:
    """Operand of a method call (attribute access binds tightest)."""
    return _paren(emitted, _ATOM)


def _join_or(left: _Emitted, right: _Emitted) -> _Emitted:
    return f"{_paren(left, _OR)} | {_paren(right, _AND)}", _OR


def _join_and(left: _Emitted, right: _Emitted) -> _Emitted:
    return f"{_paren(left, _AND)} & {_paren(right, _ADD)}", _AND


def _check_args(name: str, args: list[_Emitted], count: int) -> None:
    if len(args) < count:
        raise ExprTranslationError(f"{name} expects {count} argument(s)")


def _emit_iif(args: list[_Emitted]) -> str:
    _check_args("IIF", args, 3)
    return f"np.where({args[0][0]}, {args[1][0]}, {args[2][0]})"


def _emit_datetimeadd(args: list[_Emitted]) -> str:
    _check_args("DateTimeAdd", args, 3)
    dt = args[0][0]
    amount = args[1][0]
    unit_raw = args[2][0].strip("'\"")
    unit_lower = unit_raw.lower()
    pandas_unit = unit_lower if unit_lower in _DATEOFFSET_UNITS else unit_raw
    return f"{dt} + pd.DateOffset({pandas_unit}={amount})"


def _emit_isempty(args: list[_Emitted]) -> str:
    _check_args("IsEmpty", args, 1)
    return f'({_series(args[0])}.isna() | ({args[0][0]} == ""))'


def _emit_substring(args: list[_Emitted]) -> str:
    # Alteryx Substring is 0-indexed: Substring("DENVER", 2, 3) == "NVE"
    _check_args("Substring", args, 2)
    s = _series(args[0])
    start = _paren(args[1], _ADD)
    if len(args) >= 3:
        length = _paren(args[2], _ADD)
        return f"{s}.str[{start}:{start}+{length}]"
    return f"{s}.str[{start}:]"


def _emit_right(args: list[_Emitted]) -> str:
    # The unary minus must bind to the whole length expression:
    # Right([f], 1+1) as .str[-1 + 1:] is .str[0:] — the full string.
    _check_args("Right", args, 2)
    length = _paren(args[1], _ATOM)
    return f"{_series(args[0])}.str[-{length}:]"


def _emit_tostring(args: list[_Emitted]) -> str:
    # .astype("string") keeps missing values as <NA> instead of the
    # literal string "nan" that .astype(str) would produce.
    _check_args("ToString", args, 1)
    if len(args) > 1:
        # Alteryx format arguments (decimal places, separators) have no
        # astype equivalent; fall back so the reviewer ports it manually.
        raise ExprTranslationError("ToString with format arguments")
    return f'{_series(args[0])}.astype("string")'


def _str_method(name: str, template: str, argc: int) -> Callable[..., str]:
    def emit(args: list[_Emitted]) -> str:
        _check_args(name, args, argc)
        extra = [a[0] for a in args[1:argc]]
        return f"{_series(args[0])}{template.format(*extra)}"

    return emit


_FUNCTIONS: dict[str, Callable[[list[_Emitted]], str]] = {
    "iif": _emit_iif,
    "isnull": _str_method("IsNull", ".isna()", 1),
    "isempty": _emit_isempty,
    "null": lambda args: "np.nan",
    # Alteryx Contains is a literal (non-regex) case-insensitive substring
    # match, so regex=False — pandas would otherwise treat "." or "+" in the
    # target as regex and silently return wrong matches.
    "contains": _str_method(
        "Contains", ".str.contains({}, case=False, regex=False, na=False)", 2
    ),
    "startswith": _str_method("StartsWith", ".str.startswith({})", 2),
    "endswith": _str_method("EndsWith", ".str.endswith({})", 2),
    "trim": _str_method("Trim", ".str.strip()", 1),
    "trimleft": _str_method("TrimLeft", ".str.lstrip()", 1),
    "trimright": _str_method("TrimRight", ".str.rstrip()", 1),
    "uppercase": _str_method("Uppercase", ".str.upper()", 1),
    "lowercase": _str_method("Lowercase", ".str.lower()", 1),
    "length": _str_method("Length", ".str.len()", 1),
    "replace": _str_method("Replace", ".str.replace({}, {}, regex=False)", 3),
    "left": _str_method("Left", ".str[:{}]", 2),
    "right": _emit_right,
    "substring": _emit_substring,
    "tostring": _emit_tostring,
    "tonumber": lambda args: (
        f'pd.to_numeric({args[0][0]}, errors="coerce")'
        if args
        else _raise("ToNumber expects 1 argument")
    ),
    "abs": lambda args: (
        f"abs({args[0][0]})" if args else _raise("Abs expects 1 argument")
    ),
    "datetimenow": lambda args: "pd.Timestamp.now()",
    "datetimetoday": lambda args: "pd.Timestamp.today().normalize()",
    "datetimeadd": _emit_datetimeadd,
    "todate": lambda args: (
        f"pd.to_datetime({args[0][0]})" if args else _raise("ToDate expects 1 argument")
    ),
}


def _raise(message: str) -> str:
    raise ExprTranslationError(message)


# ── Parser ─────────────────────────────────────────────────────────────────

# One top-level boolean operand: its emitted code plus the [start, stop)
# token-index range it was parsed from (for source-fragment reconstruction).
_Operand = tuple[_Emitted, int, int]


def _fold_operands(
    operands: list[_Operand],
    join: Callable[[_Emitted, _Emitted], _Emitted],
) -> _Operand:
    emitted, start, stop = operands[0]
    for right, _, right_stop in operands[1:]:
        emitted = join(emitted, right)
        stop = right_stop
    return emitted, start, stop


class _Parser:
    def __init__(self, tokens: list[_Token], df_var: str) -> None:
        self.tokens = tokens
        self.pos = 0
        self.df_var = df_var

    def peek(self) -> _Token:
        return self.tokens[self.pos]

    def advance(self) -> _Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def keyword(self) -> str | None:
        token = self.peek()
        if token.kind == "ident" and token.value.lower() in _KEYWORDS:
            return token.value.lower()
        return None

    def expect_keyword(self, name: str) -> None:
        if self.keyword() != name:
            raise ExprTranslationError(f"expected {name.upper()}")
        self.advance()

    def expect_kind(self, kind: str) -> None:
        if self.peek().kind != kind:
            raise ExprTranslationError(f"expected {kind}")
        self.advance()

    def parse(self) -> str:
        code, _ = self.expr()
        if self.peek().kind != "end":
            raise ExprTranslationError("unexpected trailing tokens")
        return code

    def expr(self) -> _Emitted:
        if self.keyword() == "if":
            return self.if_expr()
        return self.or_expr()

    def _operand_span(self, parse: Callable[[], _Emitted]) -> _Operand:
        start = self.pos
        emitted = parse()
        return emitted, start, self.pos

    def top_level_operands(self) -> tuple[list[_Operand], str]:
        """Operands of the top-level AND/OR chain, plus the joiner (& or |).

        Splits one level only: `A OR (B AND C)` yields two operands, and a
        top-level AND chain interrupted by OR folds back into a single OR
        operand (`A AND B OR C` yields two). IF expressions and single
        conditions come back as one operand.
        """
        if self.keyword() == "if":
            return [self._operand_span(self.if_expr)], "&"
        operands = [self._operand_span(self.not_expr)]
        while self.keyword() == "and":
            self.advance()
            operands.append(self._operand_span(self.not_expr))
        if self.keyword() != "or":
            return operands, "&"
        operands = [_fold_operands(operands, _join_and)]
        while self.keyword() == "or":
            self.advance()
            operands.append(self._operand_span(self.and_expr))
        return operands, "|"

    def if_expr(self) -> _Emitted:
        self.expect_keyword("if")
        conditions = [self.expr()[0]]
        self.expect_keyword("then")
        values = [self.expr()[0]]
        while self.keyword() == "elseif":
            self.advance()
            conditions.append(self.expr()[0])
            self.expect_keyword("then")
            values.append(self.expr()[0])
        default = "np.nan"
        if self.keyword() == "else":
            self.advance()
            default = self.expr()[0]
        self.expect_keyword("endif")
        if len(conditions) == 1:
            return f"np.where({conditions[0]}, {values[0]}, {default})", _ATOM
        conds = ", ".join(conditions)
        vals = ", ".join(values)
        return f"np.select([{conds}], [{vals}], default={default})", _ATOM

    def or_expr(self) -> _Emitted:
        emitted = self.and_expr()
        while self.keyword() == "or":
            self.advance()
            emitted = _join_or(emitted, self.and_expr())
        return emitted

    def and_expr(self) -> _Emitted:
        emitted = self.not_expr()
        while self.keyword() == "and":
            self.advance()
            emitted = _join_and(emitted, self.not_expr())
        return emitted

    def not_expr(self) -> _Emitted:
        if self.keyword() == "not":
            self.advance()
            operand = self.not_expr()
            return f"~{_paren(operand, _UNARY)}", _UNARY
        token = self.peek()
        if token.kind == "op" and token.value == "!":
            self.advance()
            operand = self.not_expr()
            return f"~{_paren(operand, _UNARY)}", _UNARY
        return self.comparison()

    def comparison(self) -> _Emitted:
        emitted = self.additive()
        if self.keyword() == "in":
            self.advance()
            items = self.paren_list()
            return f"{_series(emitted)}.isin([{', '.join(items)}])", _ATOM
        token = self.peek()
        if token.kind == "op" and token.value in _COMPARE_OPS:
            op = _COMPARE_OPS[token.value]
            self.advance()
            right = self.additive()
            code = f"{_paren(emitted, _ADD)} {op} {_paren(right, _ADD)}"
            return code, _CMP
        return emitted

    def paren_list(self) -> list[str]:
        self.expect_kind("lparen")
        items = [self.expr()[0]]
        while self.peek().kind == "comma":
            self.advance()
            items.append(self.expr()[0])
        self.expect_kind("rparen")
        return items

    def additive(self) -> _Emitted:
        emitted = self.multiplicative()
        while self.peek().kind == "op" and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.multiplicative()
            emitted = (
                f"{_paren(emitted, _ADD)} {op} {_paren(right, _MUL)}",
                _ADD,
            )
        return emitted

    def multiplicative(self) -> _Emitted:
        emitted = self.unary()
        while self.peek().kind == "op" and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.unary()
            emitted = (
                f"{_paren(emitted, _MUL)} {op} {_paren(right, _UNARY)}",
                _MUL,
            )
        return emitted

    def unary(self) -> _Emitted:
        token = self.peek()
        if token.kind == "op" and token.value in ("-", "+"):
            self.advance()
            operand = self.unary()
            return f"{token.value}{_paren(operand, _UNARY)}", _UNARY
        return self.primary()

    def primary(self) -> _Emitted:
        token = self.peek()
        if token.kind == "num":
            self.advance()
            return token.value, _ATOM
        if token.kind == "str":
            self.advance()
            return repr(token.value[1:-1]), _ATOM
        if token.kind == "field":
            self.advance()
            name = token.value[1:-1]
            return f"{self.df_var}[{py_str(name)}]", _ATOM
        if token.kind == "lparen":
            self.advance()
            inner = self.expr()
            self.expect_kind("rparen")
            return f"({inner[0]})", _ATOM
        if token.kind == "ident":
            if self.keyword() == "if":
                return self.if_expr()
            if self.keyword() is not None:
                raise ExprTranslationError(f"unexpected keyword {token.value}")
            return self.func_call()
        raise ExprTranslationError(f"unexpected token {token.value!r}")

    def func_call(self) -> _Emitted:
        name = self.advance().value
        if self.peek().kind != "lparen":
            raise ExprTranslationError(f"unexpected identifier {name!r}")
        self.advance()
        args: list[_Emitted] = []
        if self.peek().kind != "rparen":
            args.append(self.expr())
            while self.peek().kind == "comma":
                self.advance()
                args.append(self.expr())
        self.expect_kind("rparen")
        if emitter := _FUNCTIONS.get(name.lower()):
            return emitter(args), _ATOM
        # Unknown function: keep it verbatim so the reviewer sees what to port.
        arg_codes = ", ".join(a[0] for a in args)
        return f"{name}({arg_codes})", _ATOM


def translate_expr(expr: str, df_var: str) -> str:
    """Translate an Alteryx expression into pandas/numpy code.

    Raises ExprTranslationError when the expression uses syntax this
    translator does not understand.
    """
    tokens = _tokenize(expr)
    if tokens[0].kind == "end":
        raise ExprTranslationError("empty expression")
    return _Parser(tokens, df_var).parse()


# ── Filter mask splitting ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FilterMask:
    """One top-level boolean operand of a Filter expression.

    code is the translated pandas expression; fragment is the operand's
    original Alteryx source (comments dropped, whitespace collapsed to
    single spaces so it is safe inside a one-line ``#`` comment).
    """

    code: str
    fragment: str


@dataclass(frozen=True, slots=True)
class FilterTranslation:
    """Result of translate_filter_masks().

    combined is the whole expression as one pandas expression — identical
    to translate_expr() output. masks/joiner carry the same expression
    split at the top-level AND/OR chain (one level only); a single mask
    means the expression has no top-level chain to split.
    """

    combined: str
    masks: tuple[FilterMask, ...]
    joiner: str  # "&" or "|" ("&" when there is only one mask)


def _fragment(tokens: list[_Token], start: int, stop: int) -> str:
    """Reconstruct an operand's source from its tokens.

    Token values are taken verbatim; inter-token gaps (whitespace and
    comments — the tokenizer guarantees nothing else sits between tokens)
    collapse to a single space. Newlines inside string literals are then
    collapsed too, so the result never breaks a ``#`` comment line.
    """
    parts: list[str] = []
    prev_end = -1
    for token in tokens[start:stop]:
        if prev_end >= 0 and token.start > prev_end:
            parts.append(" ")
        parts.append(token.value)
        prev_end = token.end
    return " ".join("".join(parts).split())


def translate_filter_masks(expr: str, df_var: str) -> FilterTranslation:
    """Translate a Filter expression, split at the top-level AND/OR chain.

    Raises ExprTranslationError under exactly the same conditions as
    translate_expr(); combined always matches translate_expr() output.
    """
    tokens = _tokenize(expr)
    if tokens[0].kind == "end":
        raise ExprTranslationError("empty expression")
    parser = _Parser(tokens, df_var)
    operands, joiner = parser.top_level_operands()
    if parser.peek().kind != "end":
        raise ExprTranslationError("unexpected trailing tokens")
    join = _join_and if joiner == "&" else _join_or
    combined, _, _ = _fold_operands(operands, join)
    masks = tuple(
        FilterMask(code=emitted[0], fragment=_fragment(tokens, start, stop))
        for emitted, start, stop in operands
    )
    return FilterTranslation(combined=combined[0], masks=masks, joiner=joiner)
