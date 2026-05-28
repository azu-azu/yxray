"""Normalization pipeline stage for yxray.

Public surface: normalize()

  from yxray.normalizer import normalize
  normalized_doc = normalize(workflow_doc)  # WorkflowDoc -> NormalizedWorkflowDoc
"""

from yxray.normalizer.normalizer import normalize

__all__ = ["normalize"]
