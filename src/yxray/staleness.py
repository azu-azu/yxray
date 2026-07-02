"""Stale Select-field detection for Alteryx workflows.

Phase 1 scope
-------------
- Tracks only **Select-tool renames** (AlteryxSelect / Select tool_type).
- 1-hop warning: if A→B was renamed at tool T1 and a downstream tool
  references A, the warning reports "renamed to B at T1" — the chain is
  NOT followed further (B→C at T2 is not reported).
- Known non-goals: DynamicRename, Join/Union prefix renames, same-Select
  field swaps (A→B and B→A within one tool).
- Stale references are *consumed*: after a stale entry fires a warning at
  tool T, it is removed from the propagated history so downstream tools do
  not produce cascading duplicate warnings for the same original field name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yxray.config_utils import field_name, select_field_rows
from yxray.models.workflow import WorkflowDoc
from yxray.topology import build_predecessor_map, topo_order
from yxray.tool_registry import classify_tool


@dataclass(frozen=True)
class RenameRecord:
    old_name: str
    new_name: str
    renamed_at: int  # tool_id of the Select that performed the rename


@dataclass(frozen=True)
class StaleFieldWarning:
    tool_id: int        # Select tool that references the stale field
    field_name: str     # the stale field name as written in XML
    renamed_to: str     # what the field is currently called (1-hop)
    renamed_at: int     # tool_id that performed that rename
    message: str


def _is_select(tool_type: str) -> bool:
    return classify_tool(tool_type)[0] == "Select Fields"


def _get_rename(row: dict[str, Any]) -> str | None:
    return row.get("@rename") or row.get("@Rename") or None


def detect_stale_select_fields(doc: WorkflowDoc) -> list[StaleFieldWarning]:
    """Return warnings for Select fields that reference upstream-renamed columns.

    Traverses *doc* in topological order, propagating a rename history
    ({old_name: RenameRecord}) through each node.  When a Select tool
    references a field name that appears in the inherited history, a
    StaleFieldWarning is emitted and the entry is consumed (not forwarded).
    """
    order = topo_order(doc)
    node_map = {int(n.tool_id): n for n in doc.nodes}
    preds = build_predecessor_map(doc)

    # history[tool_id] = {old_name: RenameRecord} accumulated up to that tool
    history: dict[int, dict[str, RenameRecord]] = {}
    warnings: list[StaleFieldWarning] = []

    for tool_id in order:
        node = node_map.get(tool_id)
        if node is None:
            continue

        # Merge histories from all upstream predecessors
        inherited: dict[str, RenameRecord] = {}
        for p in preds.get(tool_id, []):
            inherited.update(history.get(p, {}))

        if _is_select(node.tool_type):
            # Fields consumed by stale warnings — removed from forwarded history
            consumed: set[str] = set()
            local_renames: dict[str, RenameRecord] = {}

            for row in select_field_rows(node.config):
                if not isinstance(row, dict):
                    continue
                name = field_name(row)
                if not name:
                    continue

                if name in inherited:
                    rec = inherited[name]
                    warnings.append(
                        StaleFieldWarning(
                            tool_id=tool_id,
                            field_name=name,
                            renamed_to=rec.new_name,
                            renamed_at=rec.renamed_at,
                            message=(
                                f'"{name}" was renamed to "{rec.new_name}" '
                                f"at Tool {rec.renamed_at}. "
                                f"This setting in Tool {tool_id} has no effect "
                                f"on the current schema."
                            ),
                        )
                    )
                    consumed.add(name)
                else:
                    rename_to = _get_rename(row)
                    if rename_to and rename_to != name:
                        local_renames[name] = RenameRecord(name, rename_to, tool_id)

            # Forward: inherited minus consumed, plus new renames
            forwarded = {k: v for k, v in inherited.items() if k not in consumed}
            history[tool_id] = {**forwarded, **local_renames}
        else:
            # Non-Select tools pass history through unchanged
            history[tool_id] = inherited

    return warnings
