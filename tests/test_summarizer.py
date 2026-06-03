from yxray.models.types import ToolID
from yxray.models.workflow import AlteryxNode, WorkflowDoc
from yxray.summarizer import summarize


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


def test_summarize_container_describes_member_tools() -> None:
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
    container_step = next(step for step in steps if step.short_type == "Container")

    assert container_step.description == (
        "Validate sectors: contains 2 tools (Filter, Formula)"
    )
