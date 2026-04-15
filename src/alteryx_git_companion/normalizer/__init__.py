"""Normalization pipeline stage for alteryx_git_companion.

Public surface: normalize()

  from alteryx_git_companion.normalizer import normalize
  normalized_doc = normalize(workflow_doc)  # WorkflowDoc -> NormalizedWorkflowDoc
"""

from alteryx_git_companion.normalizer.normalizer import normalize

__all__ = ["normalize"]
