"""Convert selected workflow clusters to ANSI SQL-like output."""

from collections.abc import Collection

from yxray.models.types import ToolID
from yxray.models.workflow import WorkflowDoc
from yxray.sql.builder import build_ir
from yxray.sql.ir import ConversionResult
from yxray.sql.renderer import render_sql


def convert_cluster_to_sql(
    doc: WorkflowDoc,
    tool_ids: Collection[ToolID],
) -> ConversionResult:
    return render_sql(build_ir(doc, tool_ids))
