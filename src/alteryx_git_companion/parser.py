"""lxml-based parser for Alteryx .yxmd workflow files.

Public API
----------
parse(path_a, path_b)
    Parse two .yxmd files and return a pair of WorkflowDoc instances.
    Raises a ParseError subclass (MissingFileError, UnreadableFileError,
    MalformedXMLError) on the first file that cannot be read; the second
    file is never touched if the first fails.

Internal stages (private)
--------------------------
_parse_one       Pre-flight checks then XML parse for a single path.
_tree_to_workflow  Convert an lxml ElementTree to a WorkflowDoc.
_element_to_dict   Recursively convert an lxml Element to a plain dict.

This module MUST NOT call sys.exit, print, or logging, and MUST NOT
perform any file I/O beyond the etree.parse() call inside _parse_one.
"""

from __future__ import annotations

import pathlib
from typing import Any

from lxml import etree

from alteryx_git_companion.exceptions import (
    MalformedXMLError,
    MissingFileError,
    UnreadableFileError,
)
from alteryx_git_companion.models import (
    AlteryxConnection,
    AlteryxNode,
    AnchorName,
    ToolID,
    WorkflowDoc,
)

__all__ = ["parse"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    doc_a = _parse_one(path_a, filter_ui_tools=filter_ui_tools)
    doc_b = _parse_one(path_b, filter_ui_tools=filter_ui_tools)
    return doc_a, doc_b


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_one(path: pathlib.Path, *, filter_ui_tools: bool = True) -> WorkflowDoc:
    """Parse a single .yxmd file into a WorkflowDoc.

    Stage 1 — pre-flight:  Validates the path exists and is a regular file.
    Stage 2 — parse:       Uses lxml with ``recover=False`` for strict XML.
    Stage 3 — convert:     Delegates to ``_tree_to_workflow``.
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

    # --- Nodes ---
    nodes_list: list[AlteryxNode] = []
    for node_elem in root.findall("Nodes//Node"):
        tool_id_str = node_elem.get("ToolID")
        if tool_id_str is None:
            continue
        tool_id = ToolID(int(tool_id_str))

        gui: etree._Element | None = node_elem.find("GuiSettings")
        plugin: str = gui.get("Plugin", "") if gui is not None else ""

        if filter_ui_tools and plugin.startswith("AlteryxGuiToolkit."):
            continue

        pos: etree._Element | None = gui.find("Position") if gui is not None else None
        x: float = float(pos.get("x", "0")) if pos is not None else 0.0
        y: float = float(pos.get("y", "0")) if pos is not None else 0.0

        config_elem: etree._Element | None = node_elem.find("Properties/Configuration")
        config: dict[str, Any] = (
            _element_to_dict(config_elem) if config_elem is not None else {}
        )

        nodes_list.append(
            AlteryxNode(
                tool_id=tool_id,
                tool_type=plugin,
                x=x,
                y=y,
                config=config,
            )
        )

    # --- Connections ---
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

    return WorkflowDoc(
        filepath=filepath,
        nodes=tuple(nodes_list),
        connections=tuple(connections_list),
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
