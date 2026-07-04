"""Alteryx → Python hint engine.

Takes a WorkflowDoc and returns a topologically-sorted list of ExplainStep
objects, each describing the Alteryx tool and its nearest Python/pandas
equivalent.

Design: calls summarize() for topo-sort + descriptions, then attaches a
python_hint by looking up the raw tool_type segment from doc.nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from yxray.models.workflow import WorkflowDoc
from yxray.summarizer import summarize
from yxray.tool_registry import python_hint_for

__all__ = ["ExplainStep", "explain"]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExplainStep:
    tool_id: int
    short_type: str
    category: str  # "input" | "transform" | "output" | "unknown"
    description: str
    python_hint: str
    supported: str  # "yes", "partial", or "no"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain(doc: WorkflowDoc) -> list[ExplainStep]:
    """Return a topologically-sorted list of ExplainStep for a workflow.

    Each step carries the tool description from summarize() plus a
    python_hint string showing the nearest pandas/Python equivalent.
    """
    node_map = {int(n.tool_id): n for n in doc.nodes}
    steps = summarize(doc)
    result: list[ExplainStep] = []
    for step in steps:
        node = node_map.get(step.tool_id)
        hint, supported = python_hint_for(node.tool_type if node else "")
        result.append(
            ExplainStep(
                tool_id=step.tool_id,
                short_type=step.short_type,
                category=step.category,
                description=step.description,
                python_hint=hint,
                supported=supported,
            )
        )
    return result
