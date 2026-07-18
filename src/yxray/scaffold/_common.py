"""Primitives shared by the scaffold generators.

The bottom of the package's dependency chain: per-tool generator modules
(e.g. _filter) import only from here (and from modules outside the
package), so nothing in the package can import cycle back into them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from yxray.config_utils import py_str

__all__ = [
    "FIELD_RE",
    "GeneratedCode",
    "PathStyle",
    "Requirement",
    "ToolContext",
    "anchor_src",
    "fallback_field_substitute",
    "frame_name",
]

# [field] notation in Alteryx expressions.
FIELD_RE = re.compile(r"\[([^\]]+)\]")


def fallback_field_substitute(expr: str, df_var: str) -> str:
    """[field] -> df_var["field"], leaving the rest of expr untouched.

    Used when an Alteryx expression can't be confidently translated: it
    resolves field references but keeps any Alteryx-only syntax (function
    names, operators) verbatim, so the result looks like Python but is not
    necessarily runnable — callers must flag it (e.g. with a TODO), not
    just emit it.
    """
    return FIELD_RE.sub(lambda m: f'{df_var}[{py_str(m.group(1))}]', expr)


def frame_name(
    names: dict[int, str],
    tool_id: int | None,
    fallback: str = "df_?",
) -> str:
    """Frame variable for a source tool, or a placeholder when unresolved."""
    if tool_id is None:
        return fallback
    return names.get(tool_id, fallback)


def anchor_src(
    anchors: dict[str, int],
    preds: list[int],
    names: tuple[str, ...],
    index: int,
) -> int | None:
    """Src tool for a named input anchor, falling back to predecessor order."""
    for name in names:
        if name in anchors:
            return anchors[name]
    return preds[index] if len(preds) > index else None


class Requirement(Enum):
    """An import a generated block needs beyond pandas (always imported).

    Identifiers, not import statements: assembly owns the spelling
    ("import numpy as np", ...) so generators never write import lines
    and there is no string vocabulary to keep in sync.
    """

    NUMPY = auto()
    GEOPANDAS = auto()
    LOGGING = auto()
    PATHLIB = auto()


@dataclass(frozen=True)
class GeneratedCode:
    """One tool's generated code plus the imports it relies on.

    Generators declare requirements at the point of emission; assembly
    unions them into header/preamble imports. This replaces re-deriving
    imports by scanning the emitted strings, which silently broke
    whenever a generator's output vocabulary changed.
    """

    code: str
    requirements: frozenset[Requirement] = frozenset()


@dataclass(frozen=True)
class PathStyle:
    """How Input/Output tools render a file path, and whether the .shx note
    is emitted inline.

    Two instances exist (see _io): the project style used by scaffold()
    references shared INPUTS/OUTPUTS dicts and puts the .shx workaround in
    the preamble; the inline style used by the .md scaffold writes raw path
    literals and prepends the .shx note to the block itself. The callables
    take (tool_id, path) so each style can use whichever it needs.
    """

    input_expr: Callable[[int, str | None], str]
    output_expr: Callable[[int, str | None], str]
    inline_shx_note: bool


@dataclass(frozen=True)
class ToolContext:
    """Everything a per-tool generator needs, in one argument.

    Uniform across every generator (Input/Output included), so the registry
    can dispatch on segment alone and the assembly loop carries no per-tool
    special cases. `paths` is only consulted by the Input/Output generators.
    """

    tool_id: int
    segment: str
    config: dict[str, Any]
    preds: list[int]
    anchors: dict[str, int]
    names: dict[int, str]
    paths: PathStyle

    @property
    def df_out(self) -> str:
        """This tool's output frame variable (df<tool_id>)."""
        return self.names[self.tool_id]

    @property
    def df_in(self) -> str:
        """Frame of the first predecessor — the input for single-input tools."""
        src = self.preds[0] if self.preds else None
        return frame_name(self.names, src)
