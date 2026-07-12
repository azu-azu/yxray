"""Primitives shared by the scaffold generators.

Kept in a dependency-free module so per-tool generator modules (e.g.
scaffold_filter) and the scaffold driver can both import them without a
circular import.
"""

from __future__ import annotations

import re

__all__ = ["FIELD_RE", "frame_name"]

# [field] notation in Alteryx expressions.
FIELD_RE = re.compile(r"\[([^\]]+)\]")


def frame_name(
    names: dict[int, str],
    tool_id: int | None,
    fallback: str = "df_?",
) -> str:
    """Frame variable for a source tool, or a placeholder when unresolved."""
    if tool_id is None:
        return fallback
    return names.get(tool_id, fallback)
