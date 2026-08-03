"""lxml-based parser for Alteryx .yxmd workflow files.

Public API
----------
parse(path_a, path_b)
    Parse two .yxmd files and return a pair of WorkflowDoc instances.
    Raises a ParseError subclass (MissingFileError, UnreadableFileError,
    MalformedXMLError) on the first file that cannot be read; the second
    file is never touched if the first fails.
parse_one(path)
    Pre-flight checks then XML parse for a single path.

Internal stages (private)
--------------------------
_tree_to_workflow  Convert an lxml ElementTree to a WorkflowDoc.
_element_to_dict   Recursively convert an lxml Element to a plain dict.

This module MUST NOT call sys.exit, print, or logging, and MUST NOT
perform any file I/O beyond the etree.parse() call inside parse_one.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

from lxml import etree

from yxray.exceptions import (
    MalformedXMLError,
    MissingFileError,
    UnreadableFileError,
)
from yxray.models import (
    AlteryxConnection,
    AlteryxNode,
    AnchorName,
    ControlParam,
    MacroAction,
    MacroInterface,
    ToolID,
    WorkflowDoc,
)

__all__ = ["parse", "parse_one"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_one(path: pathlib.Path, *, filter_ui_tools: bool = True) -> WorkflowDoc:
    """Parse a single .yxmd file into a WorkflowDoc.

    Stage 1 — pre-flight:  Validates the path exists and is a regular file.
    Stage 2 — parse:       Uses lxml with ``recover=False`` for strict XML.
    Stage 3 — convert:     Delegates to ``_tree_to_workflow``.

    Parameters
    ----------
    path:
        Path to the Alteryx workflow file.
    filter_ui_tools:
        When True (default), AlteryxGuiToolkit.* nodes are omitted.

    Raises
    ------
    MissingFileError, UnreadableFileError, MalformedXMLError
    """
    # Stage 1: pre-flight
    if not path.exists():
        raise MissingFileError(
            filepath=str(path),
            message=f"File not found: {path}",
        )
    if not path.is_file():
        raise UnreadableFileError(
            filepath=str(path),
            message=f"Path is not a regular file: {path}",
        )

    # Stage 2: parse
    xml_parser: etree.XMLParser = etree.XMLParser(recover=False)
    try:
        tree: etree._ElementTree[etree._Element] = etree.parse(  # type: ignore[type-arg]
            str(path), xml_parser
        )
    except etree.XMLSyntaxError as exc:
        raise MalformedXMLError(
            filepath=str(path),
            message=f"Malformed XML in {path.name}: {exc}",
        ) from exc
    except OSError as exc:
        raise UnreadableFileError(
            filepath=str(path),
            message=f"Cannot read {path}: {exc}",
        ) from exc

    # Stage 3: convert
    return _tree_to_workflow(tree, filepath=str(path), filter_ui_tools=filter_ui_tools)


def parse(
    path_a: pathlib.Path,
    path_b: pathlib.Path,
    *,
    filter_ui_tools: bool = True,
) -> tuple[WorkflowDoc, WorkflowDoc]:
    """Parse two .yxmd files and return their WorkflowDoc representations.

    Parameters
    ----------
    path_a:
        Path to the first Alteryx workflow file.
    path_b:
        Path to the second Alteryx workflow file.
    filter_ui_tools:
        When True (default), AlteryxGuiToolkit.* nodes (app interface tools
        such as Tab, TextBox, Action) are omitted from the parsed result.
        Pass False to include all nodes.

    Returns
    -------
    tuple[WorkflowDoc, WorkflowDoc]
        A pair ``(doc_a, doc_b)`` populated with nodes and connections.

    Raises
    ------
    MissingFileError
        If either path does not exist.  ``path_a`` is checked first.
    UnreadableFileError
        If either path exists but is not a regular readable file.
    MalformedXMLError
        If either file contains invalid XML.
    """
    doc_a = parse_one(path_a, filter_ui_tools=filter_ui_tools)
    doc_b = parse_one(path_b, filter_ui_tools=filter_ui_tools)
    return doc_a, doc_b


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _node_raw_xml(elem: etree._Element) -> str:
    """Serialize a <Node> element back to XML, dedented to column 0.

    lxml keeps the original whitespace, so child lines carry the file's
    absolute indentation while the opening tag starts at column 0.
    Strip the common indent of the continuation lines so the block reads
    as a standalone snippet.
    """
    raw = etree.tostring(elem, encoding="unicode", with_tail=False).rstrip()
    lines = raw.splitlines()
    rest = [line for line in lines[1:] if line.strip()]
    if not rest:
        return raw
    indent = min(len(line) - len(line.lstrip()) for line in rest)
    if indent == 0:
        return raw
    dedented = [lines[0]] + [
        line[indent:] if line.strip() else "" for line in lines[1:]
    ]
    return "\n".join(dedented)


_TOOL_ID_IN_NAME_RE = re.compile(r"\((\d+)\)")
_PARAM_REF_RE = re.compile(r"\[#(\d+)\]")


def _element_text(parent: etree._Element | None, tag: str) -> str:
    if parent is None:
        return ""
    child = parent.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_control_params(root: etree._Element) -> tuple[list[ControlParam], list[str]]:
    """Control Parameters in the order that defines their [#N] indexes.

    <BatchMacro><ControlParams> is the block Alteryx itself resolves [#N]
    against. <Questions> describes the same parameters but is Interface-tab
    design data: it mixes in Tab elements and can appear more than once (a
    real .yxmc in this project has two such blocks, which made a naive
    reader see four parameters where there are two). So only BatchMacro is
    read here — see tools/analyze_macro_actions.py, where that was found.
    """
    warnings: list[str] = []
    blocks = root.findall(".//BatchMacro/ControlParams")
    if not blocks:
        return [], warnings
    if len(blocks) > 1:
        warnings.append(
            f"found {len(blocks)} <BatchMacro><ControlParams> blocks (expected 1);"
            " using the first — [#N] indexes may be wrong"
        )
    params: list[ControlParam] = []
    for index, elem in enumerate(blocks[0].findall("ControlParam"), start=1):
        name = _element_text(elem, "Name")
        match = _TOOL_ID_IN_NAME_RE.search(name)
        params.append(
            ControlParam(
                index=index,
                name=name,
                description=_element_text(elem, "Description"),
                tool_id=int(match.group(1)) if match else None,
            )
        )
    return params, warnings


def _parse_macro_actions(root: etree._Element) -> list[MacroAction]:
    """Action rewrites, each targeting one ToolID/field of another tool.

    The Action's own ToolID is written as a <ToolId value="..."/> child, not
    as an attribute; the attribute form is accepted too so a hand-edited file
    still reads. <Destination> is "952/File" — ToolID and field name.
    """
    actions: list[MacroAction] = []
    for elem in root.findall(".//Actions//Action"):
        expression = _element_text(elem, "Expression")
        destination = _element_text(elem, "Destination")
        if not expression and not destination:
            continue
        tool_id_elem = elem.find("ToolId")
        # Both .get() calls are typed str | None, so the trailing "" is what
        # makes this a str rather than an optional one.
        tool_id_str = (
            (tool_id_elem.get("value") if tool_id_elem is not None else None)
            or elem.get("ToolId")
            or ""
        )
        dst_id_str, _, dst_field = destination.partition("/")
        actions.append(
            MacroAction(
                tool_id=int(tool_id_str) if tool_id_str.isdigit() else None,
                expression=expression,
                destination_tool_id=int(dst_id_str) if dst_id_str.isdigit() else None,
                destination_field=dst_field,
                param_indexes=tuple(int(n) for n in _PARAM_REF_RE.findall(expression)),
            )
        )
    return actions


def _parse_macro_interface(root: etree._Element) -> MacroInterface:
    """The batch-macro interface, or an empty instance for a plain workflow."""
    params, warnings = _parse_control_params(root)
    return MacroInterface(
        control_params=tuple(params),
        actions=tuple(_parse_macro_actions(root)),
        warnings=tuple(warnings),
    )


def _parse_nodes(
    root: etree._Element,
    *,
    filter_ui_tools: bool,
) -> list[AlteryxNode]:
    """Extract AlteryxNode objects from the XML root element."""
    nodes_list: list[AlteryxNode] = []
    for node_elem in root.findall("Nodes/Node"):
        _collect_node(
            node_elem,
            parent_container_id=None,
            filter_ui_tools=filter_ui_tools,
            nodes_list=nodes_list,
        )
    return nodes_list


def _collect_node(
    node_elem: etree._Element,
    *,
    parent_container_id: int | None,
    filter_ui_tools: bool,
    nodes_list: list[AlteryxNode],
) -> None:
    """Append node_elem to nodes_list, then recurse into its <ChildNodes>.

    Container membership is serialized two ways depending on the Designer
    version that wrote the file: older exports set
    Properties/EngineSettings/@ToolContainerID on every member node; newer
    exports nest members directly inside the container's own <ChildNodes>
    element instead. Both are honored here — the explicit attribute wins
    when present, otherwise a nested node inherits its parent container's
    ToolID.
    """
    tool_id_str = node_elem.get("ToolID")
    if tool_id_str is None:
        return
    tool_id = ToolID(int(tool_id_str))

    gui: etree._Element | None = node_elem.find("GuiSettings")
    plugin: str = gui.get("Plugin", "") if gui is not None else ""

    keep = not (
        filter_ui_tools
        and plugin.startswith("AlteryxGuiToolkit.")
        and "ToolContainer" not in plugin
    )

    if keep:
        pos: etree._Element | None = gui.find("Position") if gui is not None else None
        x: float = float(pos.get("x", "0")) if pos is not None else 0.0
        y: float = float(pos.get("y", "0")) if pos is not None else 0.0
        width: float = float(pos.get("width", "0")) if pos is not None else 0.0
        height: float = float(pos.get("height", "0")) if pos is not None else 0.0

        annotation: str = _element_text(
            node_elem.find("Properties/Annotation"), "AnnotationText"
        )

        config_elem: etree._Element | None = node_elem.find("Properties/Configuration")
        config: dict[str, Any] = (
            _element_to_dict(config_elem) if config_elem is not None else {}
        )

        # ToolContainerID lives under Properties/EngineSettings (regular tools).
        props_engine: etree._Element | None = node_elem.find(
            "Properties/EngineSettings"
        )
        container_id_str = (
            props_engine.get("ToolContainerID") if props_engine is not None else None
        )
        container_id: int | None = (
            int(container_id_str)
            if container_id_str is not None
            else parent_container_id
        )

        # Macro tools place <EngineSettings Macro="..." /> directly under <Node>,
        # not inside <Properties>.  When GuiSettings/Plugin is absent, use the
        # macro filename stem as a fallback tool_type.
        if not plugin:
            node_engine: etree._Element | None = node_elem.find("EngineSettings")
            if node_engine is not None:
                macro_path = node_engine.get("Macro", "")
                if macro_path:
                    plugin = "Macro." + pathlib.Path(macro_path).stem
                    config = {**config, "@Macro": macro_path}

        nodes_list.append(
            AlteryxNode(
                tool_id=tool_id,
                tool_type=plugin,
                x=x,
                y=y,
                width=width,
                height=height,
                config=config,
                container_id=container_id,
                raw_xml=_node_raw_xml(node_elem),
                annotation=annotation,
            )
        )

    child_nodes: etree._Element | None = node_elem.find("ChildNodes")
    if child_nodes is not None:
        for child_elem in child_nodes.findall("Node"):
            _collect_node(
                child_elem,
                parent_container_id=tool_id,
                filter_ui_tools=filter_ui_tools,
                nodes_list=nodes_list,
            )


def _parse_connections(root: etree._Element) -> list[AlteryxConnection]:
    """Extract AlteryxConnection objects from the XML root element."""
    connections_list: list[AlteryxConnection] = []
    for conn_elem in root.findall("Connections/Connection"):
        origin: etree._Element | None = conn_elem.find("Origin")
        dest: etree._Element | None = conn_elem.find("Destination")
        if origin is None or dest is None:
            continue  # skip malformed connection silently

        src_tool_str = origin.get("ToolID")
        dst_tool_str = dest.get("ToolID")
        if src_tool_str is None or dst_tool_str is None:
            continue

        connections_list.append(
            AlteryxConnection(
                src_tool=ToolID(int(src_tool_str)),
                src_anchor=AnchorName(origin.get("Connection", "Output")),
                dst_tool=ToolID(int(dst_tool_str)),
                dst_anchor=AnchorName(dest.get("Connection", "Input")),
            )
        )
    return connections_list


def _tree_to_workflow(
    tree: etree._ElementTree[etree._Element],  # type: ignore[type-arg]
    filepath: str,
    *,
    filter_ui_tools: bool = True,
) -> WorkflowDoc:
    """Convert an lxml ElementTree to a WorkflowDoc.

    Parameters
    ----------
    tree:
        A fully-parsed lxml ElementTree.
    filepath:
        The original file path string, stored verbatim on WorkflowDoc.
    filter_ui_tools:
        When True (default), AlteryxGuiToolkit.* nodes are skipped so that
        app interface elements do not appear as spurious diffs.
    """
    root: etree._Element = tree.getroot()
    return WorkflowDoc(
        filepath=filepath,
        nodes=tuple(_parse_nodes(root, filter_ui_tools=filter_ui_tools)),
        connections=tuple(_parse_connections(root)),
        macro_interface=_parse_macro_interface(root),
    )


def _element_to_dict(elem: etree._Element) -> dict[str, Any]:
    """Recursively convert an lxml Element to a plain Python dict.

    Conventions
    -----------
    - XML attributes are stored with an ``@`` prefix: ``{"@key": "value"}``.
    - Non-whitespace text content is stored as ``"#text"``.
    - Child elements are keyed by tag name.  When multiple sibling elements
      share the same tag, they are promoted to a list automatically.
    """
    result: dict[str, Any] = {}

    # Attributes
    for k, v in elem.attrib.items():
        key = k if isinstance(k, str) else k.decode()
        result[f"@{key}"] = v

    # Text content
    if elem.text and elem.text.strip():
        result["#text"] = elem.text.strip()

    # Child elements
    children_by_tag: dict[str, Any] = {}
    for child in elem:
        child_dict = _element_to_dict(child)
        raw_tag = child.tag
        # lxml-stubs types tag as str | bytes; skip processing instructions (bytes)
        if not isinstance(raw_tag, str):
            continue
        tag: str = raw_tag
        if tag in children_by_tag:
            existing: Any = children_by_tag[tag]
            if isinstance(existing, list):
                existing.append(child_dict)
            else:
                children_by_tag[tag] = [existing, child_dict]
        else:
            children_by_tag[tag] = child_dict

    result.update(children_by_tag)
    return result
