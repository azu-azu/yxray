"""Diff engine pipeline stage for yxray.

Public surface: diff()

  from yxray.differ import diff
  result = diff(match_result, old_connections, new_connections)
"""

from __future__ import annotations

from yxray.differ.differ import diff

__all__ = ["diff"]
