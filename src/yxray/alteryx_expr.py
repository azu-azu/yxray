"""Best-effort Alteryx expression → pandas/numpy translation.

translate_expr() covers the common Alteryx expression language:
[field] references, literals, arithmetic, comparisons (including = and
<>), AND/OR/NOT, IN (...), IF/ELSEIF/ELSE/ENDIF, IIF, and frequent
string/null functions. Anything it cannot confidently translate raises
ExprTranslationError so callers can fall back to plain [field]
substitution.

Emitted code assumes `np` (numpy) and `pd` (pandas) are in scope when
the corresponding constructs appear; translations report whether they
actually emitted numpy (ExprTranslation.uses_numpy /
FilterTranslation.uses_numpy) so callers can emit the import only when
needed. The flag is set at the emission sites themselves — adding a new
np.* emission and keeping the flag correct happen in this file.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from yxray.config_utils import py_str

__all__ = [
    "ExprTranslation",
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


# The IsNull/IsEmpty emitters above, run backwards: is `condition` exactly
# "test `kept` for missing"? Reconstructing the emitter output and comparing
# strings keeps the two definitions honest — if an emitter changes, this
# stops matching, which costs the peephole and not correctness (the np.where
# path is still a valid translation).
def _missing_test(condition: str, kept: _Emitted) -> str | None:
    """ "isnull" / "isempty" when `condition` tests `kept`, else None."""
    series = _series(kept)
    if condition == f"{series}.isna()":
        return "isnull"
    if condition == f'({series}.isna() | ({kept[0]} == ""))':
        return "isempty"
    return None


def _fill_code(test: str, kept: _Emitted, value: str) -> tuple[str, bool]:
    """(code, needs_fill_empty) filling `kept`'s missing rows with `value`."""
    if test == "isnull":
        return f"{_series(kept)}.fillna({value})", False
    # No pandas built-in covers NULL-or-empty, so this one needs the
    # reference_impl helper; the generator emits a NOTE pointing at it.
    return f"fill_empty({_series(kept)}, {value})", True


def _missing_fill(
    condition: str, then_branch: _Emitted, else_branch: _Emitted
) -> tuple[str, bool] | None:
    """A two-branch IF that is a missing-value fill → fill code.

    Returns (code, needs_fill_empty), or None when the IF is not a fill.
    np.where would be a correct translation too, but it returns an ndarray
    and so drops the column's dtype (Int64 → float64, string/category →
    object) — exactly on the columns a missing-value fill targets.
    .fillna()/fill_empty() keep it.

    Both directions count, since Alteryx authors write the test either way
    round and mean the same thing:

        IF IsNull([c]) THEN v ELSE [c] ENDIF    # ELSE keeps the value
        IF !IsNull([c]) THEN [c] ELSE v ENDIF   # THEN keeps it
    """
    if test := _missing_test(condition, else_branch):
        return _fill_code(test, else_branch, then_branch[0])
    # `~` is how not_expr/`!` emit a negated condition; strip it and the
    # branches swap roles. A `~` in front of anything else fails the test
    # match below, so this stays a fill-only shortcut.
    if condition.startswith("~") and (
        test := _missing_test(condition[1:], then_branch)
    ):
        return _fill_code(test, then_branch, else_branch[0])
    return None


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


# _FUNCTIONS entries whose emitted code contains np.* — kept adjacent to
# the table so adding a numpy-emitting function updates both together.
_NUMPY_FUNCTIONS = frozenset({"iif", "null"})


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
        # Whether any emission so far contains np.* (IF/IIF → np.where /
        # np.select / np.nan, Null() → np.nan).
        self.uses_numpy = False
        # Whether any emission so far calls fill_empty() — the one emitted
        # name that is not pandas/numpy, so callers must point at
        # reference_impl/fill_empty.py.
        self.uses_fill_empty = False

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
        branches = [self.expr()]
        while self.keyword() == "elseif":
            self.advance()
            conditions.append(self.expr()[0])
            self.expect_keyword("then")
            branches.append(self.expr())
        else_emitted: _Emitted | None = None
        if self.keyword() == "else":
            self.advance()
            else_emitted = self.expr()
        self.expect_keyword("endif")
        values = [branch[0] for branch in branches]
        # A single test where one branch hands back the tested column is a
        # missing-value fill, not a branch — dtype-preserving pandas exists
        # for it, so no np.* is emitted on that path.
        if (
            len(conditions) == 1
            and else_emitted is not None
            and (fill := _missing_fill(conditions[0], branches[0], else_emitted))
        ):
            code, needs_fill_empty = fill
            self.uses_fill_empty = self.uses_fill_empty or needs_fill_empty
            return code, _ATOM
        # np.where / np.select from here (np.nan as default when no ELSE).
        self.uses_numpy = True
        default = "np.nan" if else_emitted is None else else_emitted[0]
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
            # IIF(IsNull([c]), v, [c]) is the IF form written as a call, so
            # the same fill peephole applies — checked before _emit_iif so
            # the np.where emitter (and its numpy flag) is never reached.
            if (
                name.lower() == "iif"
                and len(args) >= 3
                and (fill := _missing_fill(args[0][0], args[1], args[2]))
            ):
                code, needs_fill_empty = fill
                self.uses_fill_empty = self.uses_fill_empty or needs_fill_empty
                return code, _ATOM
            if name.lower() in _NUMPY_FUNCTIONS:
                self.uses_numpy = True
            return emitter(args), _ATOM
        # Unknown function: keep it verbatim so the reviewer sees what to port.
        arg_codes = ", ".join(a[0] for a in args)
        return f"{name}({arg_codes})", _ATOM


@dataclass(frozen=True, slots=True)
class ExprTranslation:
    """Result of translate_expr(): the code plus what it relies on.

    uses_numpy is True when the emitted code contains np.* — tracked at
    the emission sites, not re-derived from the string — so callers can
    emit `import numpy as np` exactly when needed. uses_fill_empty is the
    same idea for the one emitted name that is neither pandas nor numpy:
    callers point the reader at reference_impl/fill_empty.py.
    """

    code: str
    uses_numpy: bool
    uses_fill_empty: bool = False


def translate_expr(expr: str, df_var: str) -> ExprTranslation:
    """Translate an Alteryx expression into pandas/numpy code.

    Raises ExprTranslationError when the expression uses syntax this
    translator does not understand.
    """
    tokens = _tokenize(expr)
    if tokens[0].kind == "end":
        raise ExprTranslationError("empty expression")
    parser = _Parser(tokens, df_var)
    return ExprTranslation(
        code=parser.parse(),
        uses_numpy=parser.uses_numpy,
        uses_fill_empty=parser.uses_fill_empty,
    )


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
    means the expression has no top-level chain to split. uses_numpy /
    uses_fill_empty carry what the translation emitted (see
    ExprTranslation).
    """

    combined: str
    masks: tuple[FilterMask, ...]
    joiner: str  # "&" or "|" ("&" when there is only one mask)
    uses_numpy: bool
    uses_fill_empty: bool = False


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
    return FilterTranslation(
        combined=combined[0],
        masks=masks,
        joiner=joiner,
        uses_numpy=parser.uses_numpy,
        uses_fill_empty=parser.uses_fill_empty,
    )
