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
        for value in child_values(config, key):
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                text = value.get("#text")
                if isinstance(text, str):
                    return text.strip()
    return ""


def child_values(obj: Any, key: str) -> list[Any]:
    if isinstance(obj, dict):
        values = as_list(obj[key]) if key in obj else []
        for value in obj.values():
            values.extend(child_values(value, key))
        return values
    if isinstance(obj, list):
        return [child for value in obj for child in child_values(value, key)]
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


def formula_field_summaries(config: dict[str, Any]) -> list[str]:
    ffs = config.get("FormulaFields", {})
    formulas: list[str] = []
    if not isinstance(ffs, dict):
        return formulas
    for item in as_list(ffs.get("FormulaField")):
        if not isinstance(item, dict):
            continue
        expr = (
            item.get("@expression", "")
            or item.get("@formula", "")
            or get_text(item, "Expression")
        )
        field = item.get("@field", "") or item.get("@name", "")
        if field and expr:
            formulas.append(f"{field} = {expr}")
        elif expr or field:
            formulas.append(str(expr or field))
    return formulas
