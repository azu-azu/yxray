"""Join's J output with side-aware Select settings.

Copy this file and select_edits.py into the target project and import
join_selected alongside apply_select_edits. The scaffold emits calls, not
helper definitions. Inputs must have unique string column names.

This implements field-based inner joins only. It preserves duplicate-key
multiplicity and both key columns until selection. Null matching follows
pandas.merge; compare null-key cases against Alteryx before relying on parity.
Ordinary duplicate names use Right_ prefixes. More complex naming collisions
are rejected rather than guessing Alteryx's suffix rules. Type conversion
has the same limitations as select_edits.py.
"""

from __future__ import annotations

import logging

import pandas as pd
from select_edits import SelectColumnEdit, apply_select_edits

logger = logging.getLogger(__name__)

# (input prefix, original input name, selected, output rename, target type)
JoinColumn = tuple[str, str, bool, str | None, str | None]


def join_selected(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    keys: list[tuple[str, str]],
    columns: list[JoinColumn],
    order_changed: bool = False,
) -> pd.DataFrame:
    if not keys:
        raise ValueError("Join requires at least one key pair")
    for frame in (left, right):
        if not frame.columns.is_unique or not all(
            isinstance(name, str) for name in frame.columns
        ):
            raise ValueError("Join requires unique string input column names")

    identities = [("Left_", name) for name in left.columns] + [
        ("Right_", name) for name in right.columns
    ]
    slots = {identity: index for index, identity in enumerate(identities)}
    # Integer slots cannot collide with real field names, even names already
    # containing Left_/Right_ or pandas' _x/_y suffixes.
    left_slots = {name: slots[("Left_", name)] for name in left.columns}
    right_slots = {name: slots[("Right_", name)] for name in right.columns}
    joined = pd.merge(
        left.rename(columns=left_slots),
        right.rename(columns=right_slots),
        left_on=[left_slots[lkey] for lkey, _ in keys],
        right_on=[right_slots[rkey] for _, rkey in keys],
        how="inner",
        sort=False,
    )

    edits: dict[tuple[str, str], JoinColumn] = {}
    unknown = True
    for edit in columns:
        side, name, selected, _, _ = edit
        if name == "*Unknown":
            unknown = selected
            continue
        identity = (side, name)
        if side not in ("Left_", "Right_"):
            raise ValueError("Join Select field requires an explicit input side")
        if identity in edits:
            raise ValueError("Duplicate Join Select field")
        edits[identity] = edit
        if identity not in slots:
            logger.warning("Join Select references a missing input field: %r", identity)

    kept = [
        identity
        for identity in identities
        if (edits[identity][2] if identity in edits else unknown)
    ]
    if order_changed:
        ordered = []
        unspecified = [identity for identity in kept if identity not in edits]
        for side, name, selected, _, _ in columns:
            if name == "*Unknown":
                ordered.extend(unspecified)
            elif selected and (side, name) in slots:
                ordered.append((side, name))
        # When the wildcard is omitted, unknown fields follow explicit fields.
        ordered.extend(identity for identity in unspecified if identity not in ordered)
        kept = ordered

    # Resolve the default names against the complete input schema: dropping
    # a left field does not change the identity/name of its right counterpart.
    defaults: dict[tuple[str, str], str] = {}
    used: set[str] = set(left.columns)
    for side, name in identities:
        output_name = name
        if side == "Right_":
            if output_name in used:
                output_name = "Right_" + output_name
            used.add(output_name)
        defaults[(side, name)] = output_name

    output_names = [
        edits[identity][3] or defaults[identity]
        if identity in edits else defaults[identity]
        for identity in kept
    ]
    if len(output_names) != len(set(output_names)):
        raise ValueError("Join output names collide; supply distinct renames")
    result = joined[[slots[identity] for identity in kept]].copy()
    result.columns = output_names
    conversions = [
        SelectColumnEdit(output_name, type=edits[identity][4])
        for identity, output_name in zip(kept, output_names, strict=True)
        if identity in edits and edits[identity][4]
    ]
    return apply_select_edits(result, conversions)
