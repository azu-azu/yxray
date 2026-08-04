"""Runtime configuration rewrites driven by a batch macro's Control Parameters.

A tool inside a batch macro can have part of its configuration replaced per
incoming record by an Action tool. The `<Configuration>` the rest of yxray
reads is only the design-time default in that case, so anything derived from
it — a file path in the scaffold, a value in the report panel — is a value
the workflow may never actually use.

This module turns the parsed `WorkflowDoc.macro_interface` into per-tool
warnings, shaped like `output_collisions.DuplicateOutputWarning` so the CLI
can merge both into the same `warnings_by_tool` map without special cases.
"""

from __future__ import annotations

from dataclasses import dataclass

from yxray.models.macro import MacroAction, MacroInterface
from yxray.models.workflow import WorkflowDoc


@dataclass(frozen=True)
class MacroOverrideWarning:
    tool_id: int
    field: str
    action_tool_id: int | None
    expression: str
    message: str


def _param_labels(interface: MacroInterface, action: MacroAction) -> str:
    """ "[#1] 出力ファイル名 (ToolID 101)" for each parameter the action uses."""
    parts: list[str] = []
    for index in action.param_indexes:
        param = interface.param(index)
        if param is None:
            parts.append(f"[#{index}] (no matching Control Parameter)")
            continue
        origin = f" (ToolID {param.tool_id})" if param.tool_id is not None else ""
        parts.append(f"[#{index}] {param.label}{origin}")
    return ", ".join(parts)


def detect_macro_overrides(doc: WorkflowDoc) -> list[MacroOverrideWarning]:
    """One warning per Action rewrite that lands on a tool present in *doc*.

    Rewrites aimed at a tool that is not in `doc.nodes` are dropped: there is
    no block to attach them to, and the usual reason is that the workflow was
    parsed with a node filter. The interface's own structural warnings
    (`doc.macro_interface.warnings`) are not returned here — they belong to
    no single tool and are reported by the caller that shows the interface.
    """
    interface = doc.macro_interface
    if not interface:
        return []
    known = {int(n.tool_id) for n in doc.nodes}

    warnings: list[MacroOverrideWarning] = []
    for action in interface.actions:
        tool_id = action.destination_tool_id
        if tool_id is None or tool_id not in known:
            continue
        field = action.destination_field or "(whole configuration)"
        by = f"Action {action.tool_id}" if action.tool_id else "an Action tool"
        params = _param_labels(interface, action)
        detail = f" from {params}" if params else ""
        warnings.append(
            MacroOverrideWarning(
                tool_id=tool_id,
                field=field,
                action_tool_id=action.tool_id,
                expression=action.expression,
                message=(
                    f'Batch macro: {by} rewrites "{field}" at runtime as'
                    f" {action.expression}{detail}. "
                    "The configuration here is only the design-time default — "
                    "parameterize this value instead of hard-coding it."
                ),
            )
        )
    return sorted(warnings, key=lambda w: (w.tool_id, w.field))
