"""Node matcher pipeline stage for alteryx_git_companion.

Public surface: match(), MatchResult

  from alteryx_git_companion.matcher import match, MatchResult
  result = match(old_nodes, new_nodes)  # list[NormalizedNode] x2 -> MatchResult
"""

from alteryx_git_companion.matcher.matcher import MatchResult, match

__all__ = ["match", "MatchResult"]
