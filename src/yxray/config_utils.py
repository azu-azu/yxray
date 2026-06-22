"""Public helpers for parsed Alteryx configuration dictionaries."""

from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def get_text(obj: Any, key: str) -> str:
    if not isinstance(obj, dict):
        return ""
    value = obj.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("#text", ""))
    if isinstance(value, list) and value:
        first = value[0]
        return str(first.get("#text", "")) if isinstance(first, dict) else ""
    return ""


def first_text(config: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if value := get_text(config, key):
            return value
        for value in _child_values(config, key):
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                text = value.get("#text")
                if isinstance(text, str):
                    return text.strip()
    return ""


def _child_values(obj: Any, key: str) -> list[Any]:
    if isinstance(obj, dict):
        values = as_list(obj[key]) if key in obj else []
        for value in obj.values():
            values.extend(_child_values(value, key))
        return values
    if isinstance(obj, list):
        return [child for value in obj for child in _child_values(value, key)]
    return []


def field_name(field: dict[str, Any]) -> str:
    return next(
        (
            str(field[key])
            for key in ("@field", "@name", "@Field", "@Name", "field", "name")
            if field.get(key)
        ),
        "",
    )


def select_field_rows(config: dict[str, Any]) -> list[Any]:
    fields = config.get("SelectFields", config.get("Fields", {}))
    if not isinstance(fields, dict):
        return []
    return as_list(fields.get("SelectField", fields.get("Field", [])))
