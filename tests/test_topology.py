from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.topology import topo_order


def node(tool_id: int, tool_type: str = "AlteryxFilter.AlteryxFilter") -> AlteryxNode:
    return AlteryxNode(tool_id=ToolID(tool_id), tool_type=tool_type, x=0.0, y=0.0)


def conn(src: int, dst: int) -> AlteryxConnection:
    return AlteryxConnection(
        src_tool=ToolID(src),
        src_anchor=AnchorName("Output"),
        dst_tool=ToolID(dst),
        dst_anchor=AnchorName("Input"),
    )


def test_topo_order_prefers_ascending_tool_id_over_readiness() -> None:
    # Branch A: 1 -> 2 -> 3 -> 8 (long chain)
    # Branch B: 4 -> 8 (short branch, joins at the end)
    # Both 1 and 4 are ready immediately; the lower tool_id should be
    # exhausted along its chain before jumping to the other branch.
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(node(1), node(2), node(3), node(4), node(8)),
        connections=(
            conn(1, 2),
            conn(2, 3),
            conn(3, 8),
            conn(4, 8),
        ),
    )

    assert topo_order(doc) == [1, 2, 3, 4, 8]


def test_topo_order_unaffected_by_xml_document_order() -> None:
    # Same graph as above, but nodes appear out of tool_id order in the
    # source document (e.g. after a copy/paste in Alteryx).
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(node(4), node(1), node(2), node(3), node(8)),
        connections=(
            conn(1, 2),
            conn(2, 3),
            conn(3, 8),
            conn(4, 8),
        ),
    )

    assert topo_order(doc) == [1, 2, 3, 4, 8]


def test_topo_order_excludes_containers_and_keeps_cycle_fallback() -> None:
    doc = WorkflowDoc(
        filepath="workflow.yxmd",
        nodes=(
            node(1),
            node(2, tool_type="AlteryxGuiToolkit.ToolContainer.ToolContainer"),
            node(3),
        ),
        connections=(conn(1, 3),),
    )

    assert topo_order(doc) == [1, 3]
