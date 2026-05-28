"""Pipeline orchestration stage for yxray.

Public surface: run(), DiffRequest, DiffResponse

  from yxray.pipeline import run, DiffRequest, DiffResponse
  response = run(DiffRequest(path_a=path_a, path_b=path_b))
"""

from __future__ import annotations

from yxray.pipeline.pipeline import DiffRequest, DiffResponse, run

__all__ = ["DiffRequest", "DiffResponse", "run"]
