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
    return ""


def first_text(config: dict[str, Any], *keys: str) -> str:
    return next((get_text(config, key) for key in keys if get_text(config, key)), "")


def field_name(field: dict[str, Any]) -> str:
    return next(
        (
            str(field[key])
            for key in ("@field", "@name", "@Field", "@Name")
            if field.get(key)
        ),
        "",
    )


def select_field_rows(config: dict[str, Any]) -> list[Any]:
    fields = config.get("SelectFields", config.get("Fields", {}))
    if not isinstance(fields, dict):
        return []
    return as_list(fields.get("SelectField", fields.get("Field", [])))
