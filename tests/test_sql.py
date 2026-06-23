from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
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


def test_convert_cluster_to_sql_renders_formula_as_raw_expression() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(1),
                tool_type="InputData",
                x=0,
                y=0,
                config={"File": "orders"},
            ),
            AlteryxNode(
                tool_id=ToolID(2),
                tool_type="Formula",
                x=10,
                y=0,
                config={
                    "FormulaFields": {
                        "FormulaField": {
                            "@field": "total",
                            "@expression": "[qty] * [price]",
                        }
                    }
                },
            ),
        ),
    )
    result = convert_cluster_to_sql(doc, {ToolID(1), ToolID(2)})
    assert "<raw: [qty] * [price]> AS total" in result.sql
    assert result.report.is_partial is True
    assert result.report.warnings == ("raw Formula expression in node 2",)


def test_convert_cluster_to_sql_reports_unsupported_node() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(AlteryxNode(tool_id=ToolID(1), tool_type="Join", x=0, y=0),),
    )
    result = convert_cluster_to_sql(doc, {ToolID(1)})
    assert result.report.is_partial is True
    assert "source unknown: using placeholder 't'" in result.report.warnings
    assert any(
        "unsupported Join" in w and "missing-join-expression" in w
        for w in result.report.warnings
    )


def test_convert_cluster_to_sql_no_source_uses_placeholder_t() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(1),
                tool_type="Filter",
                x=0,
                y=0,
                config={"Expression": "x > 0"},
            ),
        ),
    )
    result = convert_cluster_to_sql(doc, {ToolID(1)})
    assert "FROM t" in result.sql
    assert result.report.is_partial is True
    assert result.report.warnings == ("source unknown: using placeholder 't'",)


def test_convert_cluster_to_sql_join_generates_cte() -> None:
    """Left branch (source + filter) and right branch (source) joined on CustomerID."""
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(1),
                tool_type="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                x=0,
                y=0,
                config={"FileName": "customers.csv"},
            ),
            AlteryxNode(
                tool_id=ToolID(2),
                tool_type="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                x=0,
                y=100,
                config={"FileName": "orders.csv"},
            ),
            AlteryxNode(
                tool_id=ToolID(3),
                tool_type="AlteryxBasePluginsGui.Filter.Filter",
                x=100,
                y=0,
                config={"Expression": "[Active] = 'Y'"},
            ),
            AlteryxNode(
                tool_id=ToolID(4),
                tool_type="AlteryxBasePluginsGui.Join.Join",
                x=200,
                y=50,
                config={"JoinExpression": "[L:CustomerID] = [R:CustomerID]"},
            ),
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(3),
                src_anchor=AnchorName("True"),
                dst_tool=ToolID(4),
                dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(4),
                dst_anchor=AnchorName("Right"),
            ),
        ),
    )
    result = convert_cluster_to_sql(doc, [ToolID(1), ToolID(2), ToolID(3), ToolID(4)])

    assert "WITH _L AS (" in result.sql
    assert "_R AS (" in result.sql
    assert "INNER JOIN _R" in result.sql
    assert "ON _L.CustomerID = _R.CustomerID" in result.sql
    assert "customers.csv" in result.sql
    assert "orders.csv" in result.sql
    assert "[Active] = 'Y'" in result.sql
    assert result.report.is_partial is False


def test_convert_cluster_to_sql_join_with_post_filter() -> None:
    """Post-join Filter node renders as WHERE on the outer query."""
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            AlteryxNode(
                tool_id=ToolID(1),
                tool_type="DbFileInput",
                x=0,
                y=0,
                config={"FileName": "left.csv"},
            ),
            AlteryxNode(
                tool_id=ToolID(2),
                tool_type="DbFileInput",
                x=0,
                y=100,
                config={"FileName": "right.csv"},
            ),
            AlteryxNode(
                tool_id=ToolID(3),
                tool_type="AlteryxBasePluginsGui.Join.Join",
                x=100,
                y=50,
                config={"JoinExpression": "[L:id] = [R:id]"},
            ),
            AlteryxNode(
                tool_id=ToolID(4),
                tool_type="Filter",
                x=200,
                y=50,
                config={"Expression": "amount > 100"},
            ),
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Left"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Right"),
            ),
            AlteryxConnection(
                src_tool=ToolID(3),
                src_anchor=AnchorName("Join"),
                dst_tool=ToolID(4),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )
    result = convert_cluster_to_sql(doc, [ToolID(1), ToolID(2), ToolID(3), ToolID(4)])

    assert "WITH _L AS (" in result.sql
    assert "ON _L.id = _R.id" in result.sql
    assert "WHERE amount > 100" in result.sql
    assert result.report.is_partial is False
