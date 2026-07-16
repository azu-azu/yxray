"""Primitives shared by the scaffold generators.

The bottom of the package's dependency chain: per-tool generator modules
(e.g. _filter) import only from here (and from modules outside the
package), so nothing in the package can import cycle back into them.
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
