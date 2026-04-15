"""Internal noise-stripping logic for the normalizer.

Operates on deep-copied config dicts. Never mutates the source AlteryxNode.config.
"""

from __future__ import annotations

import copy
from typing import Any, cast

from alteryx_git_companion.normalizer.patterns import (
    GUID_SENTINEL,
    GUID_VALUE_KEYS,
    ISO8601_PATTERN,
    ISO8601_SENTINEL,
    TEMPFILE_PATH_PATTERN,
    TEMPFILE_SENTINEL,
)


def strip_noise(config: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copy of config with all Alteryx noise stripped.

    Does NOT mutate the input — source AlteryxNode.config is frozen at the
    dataclass attribute level and must not be modified at the dict level either.
    Recursively processes nested dicts and lists.

    Stripping order (applied per value):
      1. Key-targeted GUID replacement (if key in GUID_VALUE_KEYS)
      2. TempFile path replacement (regex on string values)
      3. ISO 8601 timestamp replacement (regex on string values)
    """
    return cast(dict[str, Any], _strip_value(copy.deepcopy(config)))


def _strip_value(value: Any) -> Any:
    """Recursively strip noise from any JSON-compatible value."""
    if isinstance(value, dict):
        return {k: _strip_dict_entry(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_value(item) for item in value]
    if isinstance(value, str):
        return _strip_string(value)
    return value


def _strip_dict_entry(key: str, value: Any) -> Any:
    """Apply key-targeted GUID stripping before general value stripping."""
    if key in GUID_VALUE_KEYS and isinstance(value, str):
        return GUID_SENTINEL
    return _strip_value(value)


def _strip_string(value: str) -> str:
    """Apply TempFile path and ISO 8601 timestamp replacements to a string."""
    value = TEMPFILE_PATH_PATTERN.sub(TEMPFILE_SENTINEL, value)
    value = ISO8601_PATTERN.sub(ISO8601_SENTINEL, value)
    return value
