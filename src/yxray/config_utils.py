"""Public helpers for parsed Alteryx configuration dictionaries."""

from __future__ import annotations

import re
from typing import Any

_NUMBER_RE = re.compile(r"-?\d+(\.\d+)?")


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


def simple_filter_condition(config: dict[str, Any]) -> tuple[str, str, str] | None:
    """Extract (field, operator, operand) from a Simple-mode Filter config.

    Simple-mode filters store the condition as structured elements under
    <Simple> (Operator / Field / Operands/Operand) instead of an
    <Expression> string.
    """
    mode = get_text(config, "Mode")
    if mode and mode.lower() != "simple":
        return None
    simple = config.get("Simple")
    if not isinstance(simple, dict):
        return None
    field = get_text(simple, "Field")
    operator = get_text(simple, "Operator")
    if not field or not operator:
        return None
    operand = get_text(simple.get("Operands"), "Operand")
    return field, operator, operand


def operand_literal(operand: str) -> str:
    """Quote a Simple-mode filter operand unless it is a numeric literal."""
    if _NUMBER_RE.fullmatch(operand):
        return operand
    return '"' + operand + '"'


_UNARY_FILTER_OPERATORS = {
    "IsNull": "is null",
    "IsNotNull": "is not null",
    "IsEmpty": "is empty",
    "IsNotEmpty": "is not empty",
}


def simple_filter_summary(config: dict[str, Any]) -> str:
    """Human-readable condition for a Simple-mode Filter, or ""."""
    cond = simple_filter_condition(config)
    if cond is None:
        return ""
    field, operator, operand = cond
    unary = _UNARY_FILTER_OPERATORS.get(operator)
    if unary:
        return f"[{field}] {unary}"
    return f"[{field}] {operator} {operand_literal(operand)}"


def field_name(field: dict[str, Any]) -> str:
    return next(
        (
            str(field[key])
            for key in ("@field", "@name", "@Field", "@Name", "field", "name")
            if field.get(key)
        ),
        "",
    )


def sort_field_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Sort rows (@field/@order dicts) from a Sort tool config.

    Workflows nest them as SortInfo/Field; rows directly under SortInfo
    are tolerated as well.
    """
    sort_info = config.get("SortInfo", {})
    if isinstance(sort_info, dict):
        rows = as_list(sort_info["Field"]) if "Field" in sort_info else [sort_info]
    elif isinstance(sort_info, list):
        rows = sort_info
    else:
        rows = []
    return [r for r in rows if isinstance(r, dict) and r.get("@field")]


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
