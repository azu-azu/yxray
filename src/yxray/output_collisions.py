"""Duplicate output-path detection for Alteryx workflows."""

from __future__ import annotations

from dataclasses import dataclass

from yxray.config_utils import first_text
from yxray.models.workflow import WorkflowDoc
from yxray.tool_registry import SCAFFOLD_OUTPUT_SEGMENTS, tool_segment


@dataclass(frozen=True)
class DuplicateOutputWarning:
    tool_id: int
    path: str
    other_tool_ids: tuple[int, ...]
    message: str


def detect_duplicate_outputs(doc: WorkflowDoc) -> list[DuplicateOutputWarning]:
    """Return a warning for every Output tool whose resolved file path is
    also written by another Output tool in the same workflow.

    Two Output tools sharing a static path most often happens when the
    underlying file is meant to differ at runtime (e.g. an Action tool
    overwrites it via a Control Parameter) but the Configuration still shows
    the same default. yxray does not model Action-driven path overrides, so
    scaffold() would otherwise silently emit two blocks that clobber each
    other's output file when run as one script.
    """
    by_path: dict[str, list[int]] = {}
    for node in doc.nodes:
        if tool_segment(node.tool_type) not in SCAFFOLD_OUTPUT_SEGMENTS:
            continue
        path = first_text(node.config, "File", "FileName")
        if not path:
            continue
        by_path.setdefault(path, []).append(int(node.tool_id))

    warnings: list[DuplicateOutputWarning] = []
    for path, ids in by_path.items():
        if len(ids) < 2:
            continue
        sorted_ids = sorted(ids)
        for tool_id in sorted_ids:
            others = tuple(t for t in sorted_ids if t != tool_id)
            other_list = ", ".join(f"Tool {t}" for t in others)
            warnings.append(
                DuplicateOutputWarning(
                    tool_id=tool_id,
                    path=path,
                    other_tool_ids=others,
                    message=(
                        f'Output path "{path}" is also written by {other_list}. '
                        "Running both in one script overwrites this file — "
                        "if the real path differs at runtime (e.g. an Action "
                        "tool overrides it), parameterize it instead."
                    ),
                )
            )
    return warnings
