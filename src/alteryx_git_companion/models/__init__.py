"""Public export surface for all model classes and type aliases.

All pipeline stages import from here:
    from alteryx_git_companion.models import WorkflowDoc, AlteryxNode, ToolID
    from alteryx_git_companion.models import NormalizedNode, NormalizedWorkflowDoc

Never import from sub-modules directly. This allows internal file organization
to change without breaking any callers.
"""

from alteryx_git_companion.models.diff import DiffResult, EdgeDiff, NodeDiff
from alteryx_git_companion.models.normalized import (
    NormalizedNode,
    NormalizedWorkflowDoc,
)
from alteryx_git_companion.models.types import AnchorName, ConfigHash, ToolID
from alteryx_git_companion.models.workflow import (
    AlteryxConnection,
    AlteryxNode,
    WorkflowDoc,
)

__all__ = [
    # NewType aliases
    "ToolID",
    "ConfigHash",
    "AnchorName",
    # Workflow models
    "WorkflowDoc",
    "AlteryxNode",
    "AlteryxConnection",
    # Diff models
    "DiffResult",
    "NodeDiff",
    "EdgeDiff",
    # Normalized models (Phase 3)
    "NormalizedNode",
    "NormalizedWorkflowDoc",
]
