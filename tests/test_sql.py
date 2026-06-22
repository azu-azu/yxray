from yxray.models.types import ToolID
from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.sql import convert_cluster_to_sql


def test_convert_cluster_to_sql_orders_nodes_and_renders_projection_filter() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(2),
                tool_type="Filter",
                x=20,
                y=0,
                config={"Expression": "x > 1"},
            ),
            AlteryxNode(
                tool_id=ToolID(1),
                tool_type="InputData",
                x=10,
                y=0,
                config={"File": "orders"},
            ),
            AlteryxNode(
                tool_id=ToolID(3),
                tool_type="Select",
                x=30,
                y=0,
                config={"Fields": {"Field": {"@name": "x"}}},
            ),
        ),
    )
    result = convert_cluster_to_sql(doc, {ToolID(3), ToolID(2), ToolID(1)})
    assert result.sql == "SELECT\n  x\nFROM orders\nWHERE x > 1;"
    assert result.report.is_partial is False


def test_convert_cluster_to_sql_reports_unsupported_and_unresolved_source() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(AlteryxNode(tool_id=ToolID(1), tool_type="Join", x=0, y=0),),
    )
    result = convert_cluster_to_sql(doc, {ToolID(1)})
    assert result.report.is_partial is True
    assert result.report.warnings == ("unresolved source", "unsupported Join (node 1)")
