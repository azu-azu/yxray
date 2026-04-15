from __future__ import annotations

import pathlib
from dataclasses import dataclass

from alteryx_git_companion.differ import diff
from alteryx_git_companion.matcher import match
from alteryx_git_companion.models import DiffResult, WorkflowDoc
from alteryx_git_companion.normalizer import normalize
from alteryx_git_companion.parser import parse


@dataclass(frozen=True, kw_only=True, slots=True)
class DiffRequest:
    """Input to pipeline.run(): paths to two .yxmd files to compare."""

    path_a: pathlib.Path
    path_b: pathlib.Path
    filter_ui_tools: bool = True


@dataclass(frozen=True, kw_only=True, slots=True)
class DiffResponse:
    """Output of pipeline.run(): the completed DiffResult plus parsed documents."""

    result: DiffResult
    doc_a: WorkflowDoc
    doc_b: WorkflowDoc


def run(request: DiffRequest, *, include_positions: bool = False) -> DiffResponse:
    """Execute the full diff pipeline for two .yxmd files.

    Args:
        request: DiffRequest carrying paths to both .yxmd files.
            Set ``request.filter_ui_tools=False`` to include AlteryxGuiToolkit.*
            nodes that are filtered by default.
        include_positions: When True, canvas X/Y position changes are included
            in diff detection. Default False to avoid layout noise.

    Raises:
        MissingFileError: If either path does not exist.
        UnreadableFileError: If either path exists but cannot be read.
        MalformedXMLError: If either file contains invalid XML.

    Does NOT call sys.exit(), print(), or perform any file I/O beyond
    reading the two input .yxmd files via parser.parse().
    """
    doc_a, doc_b = parse(
        request.path_a, request.path_b, filter_ui_tools=request.filter_ui_tools
    )
    norm_a = normalize(doc_a)
    norm_b = normalize(doc_b)
    match_result = match(list(norm_a.nodes), list(norm_b.nodes))
    diff_result = diff(
        match_result,
        doc_a.connections,
        doc_b.connections,
        include_positions=include_positions,
    )
    return DiffResponse(result=diff_result, doc_a=doc_a, doc_b=doc_b)
