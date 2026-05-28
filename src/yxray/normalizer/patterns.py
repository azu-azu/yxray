"""Single-source registry of all Alteryx noise-stripping patterns.

Adding a new Alteryx-generated metadata pattern requires only editing this file.
All regex patterns are compiled at import time for performance.
Phase 3 contract tests validate these patterns against fixture pairs.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# TempFile path patterns
# ---------------------------------------------------------------------------
# TempFile paths confirmed from real .yxmd files:
#   C:\Users\...\AppData\Local\Temp\Engine_3640_96bb13fd...\Engine_1952_94164fc3....yxdb
# Pattern: matches any path containing the Engine_{PID}_{hex} segment.
# Replaces the ENTIRE string value with __TEMPFILE__ (not just the segment) —
# preserves structure while eliminating version-specific path noise.
TEMPFILE_PATH_PATTERN: re.Pattern[str] = re.compile(
    r'(?:[A-Za-z]:\\|/).*?Engine_\d+_[0-9a-fA-F]+[^\'"]*',
    re.IGNORECASE,
)
TEMPFILE_SENTINEL: str = "__TEMPFILE__"

# ---------------------------------------------------------------------------
# ISO 8601 timestamp patterns
# ---------------------------------------------------------------------------
# Covers: 2024-03-15T14:30:00, 2024-03-15T14:30:00Z, 2024-03-15T14:30:00+05:30,
#         2024-03-15T14:30:00.123456Z
# Does NOT match MM/DD/YYYY (user-supplied filter dates in formula tools).
ISO8601_PATTERN: re.Pattern[str] = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
)
ISO8601_SENTINEL: str = "__TIMESTAMP__"

# ---------------------------------------------------------------------------
# GUID key targeting
# ---------------------------------------------------------------------------
# GUID stripping is KEY-TARGETED, not value-regex-based.
# Risk of regex over all UUID-shaped values: would strip user-supplied GUIDs
# in SQL queries, formula fields, or connection IDs.
# GUID_VALUE_KEYS lists dict key names (derived from @key parser convention)
# whose string values are always Alteryx-generated and safe to strip.
# Keys are added here as discovered from real .yxmd fixture inspection.
# Phase 3 tests with injected GUIDs validate that stripping works correctly.
GUID_VALUE_KEYS: frozenset[str] = frozenset(
    {
        # Known Alteryx-generated GUID fields (@-prefixed dict keys from XPath leaves).
        # Populated from fixture inspection; extend as new tool types reveal new fields.
        # Examples (add when confirmed from real files):
        #   "@GUID"           — engine-generated session identifier
        #   "CUID"            — tool-level unique identifier in some tool configs
        #   "RuntimeDataGUID" — BrowseV2 and related tools
    }
)
GUID_SENTINEL: str = "__GUID__"
