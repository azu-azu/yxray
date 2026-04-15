"""Diff engine pipeline stage for alteryx_git_companion.

Public surface: diff()

  from alteryx_git_companion.differ import diff
  result = diff(match_result, old_connections, new_connections)
"""

from __future__ import annotations

from alteryx_git_companion.differ.differ import diff

__all__ = ["diff"]
