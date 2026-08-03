"""Batch-macro interface models — Control Parameters and Action rewrites.

An Alteryx batch macro takes a value per incoming record and rewrites part
of some tool's configuration before that tool runs. Two XML blocks describe
it, and neither of them lives inside a `<Node>`:

- `<BatchMacro><ControlParams>` — the Control Parameters, in the order that
  defines the `[#1]`, `[#2]`, … indexes an Action expression refers to.
- `<Properties><RuntimeProperties><Actions>` — one Action per rewrite, with
  the expression and the `ToolID/field` it writes into.

The `<Node>` elements for the Control Parameter and Action tools carry an
empty `<Configuration/>`, so a reader that only walks nodes — which is what
yxray did before this module — cannot see any of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ControlParam:
    """One Control Parameter of a batch macro.

    `index` is what an Action expression writes as `[#N]`; it comes from the
    parameter's position in `<BatchMacro><ControlParams>`, which is the order
    Alteryx itself resolves against.
    """

    index: int
    name: str
    description: str
    tool_id: int | None = None
    """Canvas ToolID, read out of the default name "コントロールパラメーター (951)".

    None when the parameter was renamed — the link to the canvas node is lost
    with it, but the index and description still identify the parameter.
    """

    @property
    def label(self) -> str:
        """Short human label: the description, falling back to the raw name."""
        return self.description or self.name or f"[#{self.index}]"


@dataclass(frozen=True, slots=True)
class MacroAction:
    """One Action tool's runtime rewrite of another tool's configuration."""

    tool_id: int | None
    expression: str
    destination_tool_id: int | None
    destination_field: str
    param_indexes: tuple[int, ...] = ()
    """Which `[#N]` the expression refers to, in order of appearance."""


@dataclass(frozen=True, slots=True)
class MacroInterface:
    """Everything the macro interface blocks say, or an empty instance.

    A plain .yxmd has neither block, so the empty instance is the normal case
    and callers can treat it as "nothing is rewritten at runtime".
    """

    control_params: tuple[ControlParam, ...] = ()
    actions: tuple[MacroAction, ...] = ()
    warnings: tuple[str, ...] = field(default=())
    """Structural problems that made part of the interface unreadable."""

    def __bool__(self) -> bool:
        return bool(self.control_params or self.actions)

    def param(self, index: int) -> ControlParam | None:
        return next((p for p in self.control_params if p.index == index), None)

    def actions_for_tool(self, tool_id: int) -> tuple[MacroAction, ...]:
        """Actions that rewrite part of `tool_id`'s configuration."""
        return tuple(a for a in self.actions if a.destination_tool_id == tool_id)
