"""Integration tests for pipeline.run().

IMPORTANT: This file contains zero imports from sys, argparse, typer,
or alteryx_git_companion.cli — confirming pipeline is entry-point-agnostic (SC 4).
"""

from __future__ import annotations

import pathlib

import pytest

from alteryx_git_companion.exceptions import MissingFileError
from alteryx_git_companion.models import DiffResult
from alteryx_git_companion.pipeline import DiffRequest, DiffResponse, run
from tests.fixtures.pipeline import IDENTICAL_YXMD, MINIMAL_YXMD_A, MINIMAL_YXMD_B


def test_pipeline_run_returns_diff_response(tmp_path: pathlib.Path) -> None:
    """pipeline.run() with two different files returns DiffResponse(result=DiffResult).

    Verifies that the return types are correct at the response and result level.
    """
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    response = run(DiffRequest(path_a=path_a, path_b=path_b))

    assert isinstance(response, DiffResponse)
    assert isinstance(response.result, DiffResult)


def test_pipeline_run_identical_files_is_empty(tmp_path: pathlib.Path) -> None:
    """pipeline.run() with identical files produces DiffResponse with is_empty=True."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)

    response = run(DiffRequest(path_a=path_a, path_b=path_b))

    assert response.result.is_empty


def test_pipeline_run_missing_file_raises(tmp_path: pathlib.Path) -> None:
    """pipeline.run() raises MissingFileError when path_a does not exist."""
    path_a = tmp_path / "nonexistent.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_b.write_bytes(MINIMAL_YXMD_B)

    with pytest.raises(MissingFileError):
        run(DiffRequest(path_a=path_a, path_b=path_b))


def test_pipeline_run_detects_changes(tmp_path: pathlib.Path) -> None:
    """pipeline.run() with differing files produces non-empty DiffResult."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    response = run(DiffRequest(path_a=path_a, path_b=path_b))

    assert not response.result.is_empty
