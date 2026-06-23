"""SQL conversion intermediate representation."""

from dataclasses import dataclass
from enum import Enum

from yxray.models.types import ToolID


class SqlDialect(Enum):
    ANSI = "ansi"


@dataclass(frozen=True)
class SourceStep:
    tool_id: ToolID
    source_identifier: str | None


@dataclass(frozen=True)
class SelectField:
    name: str
    rename: str | None
    type: str | None


@dataclass(frozen=True)
class ProjectionStep:
    tool_id: ToolID
    fields: tuple[SelectField, ...]


@dataclass(frozen=True)
class FilterStep:
    tool_id: ToolID
    expression: str


@dataclass(frozen=True)
class AggregateStep:
    tool_id: ToolID
    group_by: tuple[str, ...]
    aggregates: tuple["AggregateField", ...]


@dataclass(frozen=True)
class AggregateField:
    field: str
    action: str
    output_name: str | None


@dataclass(frozen=True)
class FormulaField:
    field: str
    expression: str  # raw Alteryx expression; may not be valid SQL


@dataclass(frozen=True)
class ComputeStep:
    tool_id: ToolID
    formulas: tuple[FormulaField, ...]


@dataclass(frozen=True)
class JoinCondition:
    left_field: str
    right_field: str


@dataclass(frozen=True)
class JoinStep:
    tool_id: ToolID
    left_tool_ids: frozenset[int]
    right_tool_ids: frozenset[int]
    conditions: tuple[JoinCondition, ...]
    raw_expression: str
    join_type: str = "INNER"


@dataclass(frozen=True)
class UnsupportedStep:
    tool_id: ToolID
    tool_type: str
    reason: str


IRStep = (
    SourceStep
    | ProjectionStep
    | FilterStep
    | ComputeStep
    | AggregateStep
    | JoinStep
    | UnsupportedStep
)


@dataclass(frozen=True)
class ConversionReport:
    is_partial: bool
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ConversionResult:
    steps: tuple[IRStep, ...]
    sql: str
    report: ConversionReport
