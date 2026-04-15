"""Pipeline orchestration stage for alteryx_git_companion.

Public surface: run(), DiffRequest, DiffResponse

  from alteryx_git_companion.pipeline import run, DiffRequest, DiffResponse
  response = run(DiffRequest(path_a=path_a, path_b=path_b))
"""

from __future__ import annotations

from alteryx_git_companion.pipeline.pipeline import DiffRequest, DiffResponse, run

__all__ = ["DiffRequest", "DiffResponse", "run"]
