from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.summarizer import summarize
from yxray.topology import compute_node_layer


def node(
    tool_id: int,
    tool_type: str,
    config: dict | None = None,
    *,
    container_id: int | None = None,
) -> AlteryxNode:
    return AlteryxNode(
        tool_id=ToolID(tool_id),
        tool_type=tool_type,
        x=float(tool_id),
        y=0.0,
        config=config or {},
        container_id=container_id,
    )


def test_summarize_filter_plugin_variant_describes_condition() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(
                1,
                "AlteryxBasePluginsGui.Filter",
                {"Expression": "Field1 > 100"},
            ),
        ),
    )

    steps = summarize(doc)

    assert steps[0].short_type == "Filter"
    assert steps[0].description == "Keeps rows where Field1 > 100"


def test_summarize_filter_simple_mode_describes_condition() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(
                1,
                "AlteryxBasePluginsGui.Filter.Filter",
                {
                    "Mode": "Simple",
                    "Simple": {
                        "Operator": "=",
                        "Field": "CAPEX/OPEX",
                        "Operands": {"Operand": "CAPEX"},
                    },
                },
            ),
        ),
    )

    steps = summarize(doc)

    assert steps[0].description == 'Keeps rows where [CAPEX/OPEX] = "CAPEX"'


def test_summarize_formula_plugin_variant_describes_expression() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(
                1,
                "AlteryxBasePluginsGui.Formula.Formula",
                {"Expression": "[x] * 2"},
            ),
        ),
    )

    steps = summarize(doc)

    assert steps[0].short_type == "Formula"
    assert steps[0].description == "Calculates [x] * 2"


def test_summarize_select_plugin_variant_describes_kept_fields() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(
                1,
                "AlteryxBasePluginsGui.Select.Select",
                {
                    "Fields": {
                        "Field": [
                            {"@name": "NAME", "@selected": "True"},
                            {"@name": "DROP_ME", "@selected": "False"},
                            {"@field": "SITE_NAME", "@type": "V_WString"},
                        ],
                    },
                },
            ),
        ),
    )

    steps = summarize(doc)

    assert steps[0].short_type == "Select Fields"
    assert steps[0].description == "Keeps 2 fields: NAME, SITE_NAME (1 typed)"


def test_summarize_excludes_tool_containers() -> None:
    """ToolContainers must not appear in summarize() output.

    They have no data connections so they appear as spurious sources
    (in_degree == 0) in the topological sort, which would push real
    Input nodes away from the top of the Summary panel.
    """
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(
                10,
                "AlteryxBasePluginsGui.ToolContainer.ToolContainer",
                {"Caption": "Validate sectors"},
            ),
            node(11, "AlteryxBasePluginsGui.Filter", container_id=10),
            node(12, "AlteryxBasePluginsGui.Formula.Formula", container_id=10),
        ),
    )

    steps = summarize(doc)
    short_types = [s.short_type for s in steps]
    assert "Container" not in short_types
    assert len(steps) == 2  # only Filter and Formula


def test_compute_node_layer_orders_dependencies_and_canvas_peers() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(node(1, "InputData"), node(2, "Select"), node(3, "Select")),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Input"),
            ),
        ),
    )

    assert compute_node_layer(doc) == {1: 0, 2: 1, 3: 1}


def test_compute_node_layer_orders_a_linear_chain() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(node(1, "Select"), node(2, "Select"), node(3, "Select")),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Input"),
            ),
        ),
    )

    assert compute_node_layer(doc) == {1: 0, 2: 1, 3: 2}


def test_compute_node_layer_places_cycle_remnants_in_fallback_layer() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(node(1, "Select"), node(2, "Select"), node(3, "OutputData")),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2), dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(1), dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2), src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3), dst_anchor=AnchorName("Input"),
            ),
        ),
    )

    assert compute_node_layer(doc) == {1: 3, 2: 3, 3: 3}
