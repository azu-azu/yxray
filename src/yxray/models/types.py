"""Domain NewType aliases shared across all pipeline stages."""

from typing import NewType

ToolID = NewType("ToolID", int)
"""Opaque integer identifier for an Alteryx tool. Distinct from plain int in mypy."""

ConfigHash = NewType("ConfigHash", str)
"""SHA-256 hex digest of canonicalized tool configuration XML."""

AnchorName = NewType("AnchorName", str)
"""Alteryx connection anchor label, e.g. '1', 'True', 'False'."""
