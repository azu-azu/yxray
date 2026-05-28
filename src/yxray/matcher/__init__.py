"""Node matcher pipeline stage for yxray.

Public surface: match(), MatchResult

  from yxray.matcher import match, MatchResult
  result = match(old_nodes, new_nodes)  # list[NormalizedNode] x2 -> MatchResult
"""

from yxray.matcher.matcher import MatchResult, match

__all__ = ["match", "MatchResult"]
