"""Parser acceptance tests for Phase 2 (PARSE-01, PARSE-02, PARSE-03).

All tests use real file I/O through pytest's built-in ``tmp_path`` fixture.
No mocking — only real temporary files with byte content from tests.fixtures.

Test coverage summary:
  - Happy path: two valid files, correct WorkflowDoc structure
  - Config dict shape: @key convention for XML attributes
  - Repeated config children: list promotion for same-tag siblings
  - Empty workflow: nodes=() and connections=()
  - Dual-file independence: doc_a and doc_b are distinct, independent objects
  - Missing file: MissingFileError with populated filepath attribute
  - Malformed XML: MalformedXMLError with chained __cause__
  - Empty file: MalformedXMLError
  - Binary content: MalformedXMLError
  - Directory path: UnreadableFileError (or MalformedXMLError on some OS)
  - Fail-fast: only path_a filepath appears when path_a is missing
  - ParseError base: all errors subclass ParseError for unified CLI catch
"""

from __future__ import annotations

import pathlib

import pytest

from tests.fixtures import (
    BINARY_CONTENT,
    CHILDNODES_CONTAINER_YXMD,
    CONTAINER_YXMD,
    EMPTY_FILE,
    EMPTY_WORKFLOW_YXMD,
    MALFORMED_XML,
    MINIMAL_YXMD,
    REPEATED_FIELDS_YXMD,
    TWO_NODE_YXMD,
)
from yxray.exceptions import (
    MalformedXMLError,
    MissingFileError,
    ParseError,
    UnreadableFileError,
)
from yxray.models import AlteryxConnection, AlteryxNode, WorkflowDoc
from yxray.parser import parse

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def write_fixture(tmp_path: pathlib.Path, name: str, content: bytes) -> pathlib.Path:
    """Write *content* bytes to ``tmp_path / name`` and return the path."""
    p = tmp_path / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_parse_happy_path(tmp_path: pathlib.Path) -> None:
    """parse() on two valid files returns a tuple of two WorkflowDoc instances
    with correct field types and populated content from MINIMAL_YXMD.

    MINIMAL_YXMD has 2 nodes (ToolID=1 and ToolID=2) and 1 connection.
    """
    path_a = write_fixture(tmp_path, "workflow_a.yxmd", MINIMAL_YXMD)
    path_b = write_fixture(tmp_path, "workflow_b.yxmd", MINIMAL_YXMD)

    result = parse(path_a, path_b)

    # Returns a two-element tuple of WorkflowDoc
    assert isinstance(result, tuple)
    assert len(result) == 2
    doc_a, doc_b = result
    assert isinstance(doc_a, WorkflowDoc)
    assert isinstance(doc_b, WorkflowDoc)

    # filepath reflects the actual temp file name
    assert "workflow_a.yxmd" in doc_a.filepath

    # MINIMAL_YXMD contains two Node elements
    assert len(doc_a.nodes) == 2
    node_0 = doc_a.nodes[0]
    assert isinstance(node_0, AlteryxNode)

    # ToolID is NewType of int — isinstance check still uses int
    assert isinstance(node_0.tool_id, int)

    # x and y must be float
    assert isinstance(node_0.x, float)
    assert isinstance(node_0.y, float)

    # tool_type is a non-empty string (Plugin attribute value)
    assert isinstance(node_0.tool_type, str)
    assert len(node_0.tool_type) > 0

    # connections is a tuple
    assert isinstance(doc_a.connections, tuple)
    # MINIMAL_YXMD has exactly one connection
    assert len(doc_a.connections) == 1
    conn = doc_a.connections[0]
    assert isinstance(conn, AlteryxConnection)


def test_parse_config_dict_shape(tmp_path: pathlib.Path) -> None:
    """Config dict follows the @key convention for XML attributes and #text
    convention for non-whitespace text content.

    MINIMAL_YXMD node 1 has:
      <File RecordLimit="0">data.csv</File>
    Expected config shape: {"File": {"@RecordLimit": "0", "#text": "data.csv"}}
    """
    path = write_fixture(tmp_path, "config_test.yxmd", MINIMAL_YXMD)
    doc, _ = parse(path, path)

    node = doc.nodes[0]
    cfg = node.config

    assert isinstance(cfg, dict), "config must be a dict"

    # _element_to_dict returns Configuration's children directly (the element
    # itself is stripped; its direct children become top-level keys)
    file_entry = cfg.get("File")
    assert file_entry is not None, "Expected 'File' key in config dict"
    assert isinstance(file_entry, dict)

    # XML attribute RecordLimit="0" becomes "@RecordLimit"
    assert "@RecordLimit" in file_entry, "XML attributes must appear as @key entries"
    assert file_entry["@RecordLimit"] == "0"

    # Text content "data.csv" becomes "#text"
    assert "#text" in file_entry, "Non-whitespace text must appear as #text"
    assert file_entry["#text"] == "data.csv"


def test_parse_repeated_config_children(tmp_path: pathlib.Path) -> None:
    """Repeated same-tag children are promoted to a list in _element_to_dict.

    REPEATED_FIELDS_YXMD has three <Field> elements under <Fields>.
    Expected: config["Fields"]["Field"] is a list of length 3.
    """
    path = write_fixture(tmp_path, "repeated.yxmd", REPEATED_FIELDS_YXMD)
    doc, _ = parse(path, path)

    assert len(doc.nodes) == 1
    cfg = doc.nodes[0].config

    fields_block = cfg.get("Fields")
    assert fields_block is not None, "Expected 'Fields' key in config"
    assert isinstance(fields_block, dict)

    field_list = fields_block.get("Field")
    assert field_list is not None, "Expected 'Field' key inside Fields block"
    assert isinstance(field_list, list), "Repeated same-tag children must be a list"
    assert len(field_list) >= 2, "Must have at least 2 items when promoted to list"

    # Verify each entry has @name attribute
    for entry in field_list:
        assert isinstance(entry, dict)
        assert "@name" in entry


def test_parse_container_id(tmp_path: pathlib.Path) -> None:
    """Nodes with ToolContainerID in EngineSettings get container_id populated.

    CONTAINER_YXMD has:
      - ToolID=10: ToolContainer node (no ToolContainerID -> container_id=None)
      - ToolID=1, ToolID=2: members with ToolContainerID="10" -> container_id=10
      - ToolID=3: outside node -> container_id=None
    """
    path = write_fixture(tmp_path, "container.yxmd", CONTAINER_YXMD)
    doc, _ = parse(path, path)

    node_map = {int(n.tool_id): n for n in doc.nodes}

    # Container node itself has no ToolContainerID
    assert node_map[10].container_id is None

    # Member nodes point to their container
    assert node_map[1].container_id == 10
    assert node_map[2].container_id == 10

    # Node outside the container
    assert node_map[3].container_id is None


def test_parse_container_id_childnodes_format(tmp_path: pathlib.Path) -> None:
    """Nodes nested in a container's <ChildNodes> get container_id populated.

    Newer Alteryx Designer exports (observed at yxmdVer="2023.2") nest member
    nodes directly inside the container's own <ChildNodes> element instead of
    writing a ToolContainerID attribute on each member. CHILDNODES_CONTAINER_YXMD
    mirrors CONTAINER_YXMD's shape (container ToolID=10, members ToolID=1/2,
    outside node ToolID=3) but uses this nested form.
    """
    path = write_fixture(
        tmp_path, "childnodes_container.yxmd", CHILDNODES_CONTAINER_YXMD
    )
    doc, _ = parse(path, path)

    node_map = {int(n.tool_id): n for n in doc.nodes}

    # Container node itself is not inside another container
    assert node_map[10].container_id is None

    # Members nested in <ChildNodes> point to their container
    assert node_map[1].container_id == 10
    assert node_map[2].container_id == 10

    # Node outside the container
    assert node_map[3].container_id is None


def test_parse_empty_workflow(tmp_path: pathlib.Path) -> None:
    """Workflow with empty Nodes and Connections elements returns empty tuples."""
    path = write_fixture(tmp_path, "empty_workflow.yxmd", EMPTY_WORKFLOW_YXMD)
    doc, _ = parse(path, path)

    assert doc.nodes == ()
    assert doc.connections == ()


def test_parse_dual_file_independence(tmp_path: pathlib.Path) -> None:
    """parse() correctly populates both docs from their respective files.

    TWO_NODE_YXMD (path_a) has two nodes; MINIMAL_YXMD (path_b) also has two
    nodes but different filepaths.  The resulting doc_a and doc_b must have
    distinct filepath attributes and independent node collections.
    """
    path_a = write_fixture(tmp_path, "two_node.yxmd", TWO_NODE_YXMD)
    path_b = write_fixture(tmp_path, "minimal.yxmd", MINIMAL_YXMD)

    doc_a, doc_b = parse(path_a, path_b)

    # Filepaths differ
    assert doc_a.filepath != doc_b.filepath
    assert "two_node.yxmd" in doc_a.filepath
    assert "minimal.yxmd" in doc_b.filepath

    # Node tuples are independent objects (not the same reference)
    assert doc_a.nodes is not doc_b.nodes


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_parse_missing_file_raises(tmp_path: pathlib.Path) -> None:
    """MissingFileError raised when path_a does not exist."""
    path_a = tmp_path / "nonexistent_a.yxmd"  # intentionally not created
    path_b = write_fixture(tmp_path, "valid_b.yxmd", MINIMAL_YXMD)

    with pytest.raises(MissingFileError) as exc_info:
        parse(path_a, path_b)

    assert "nonexistent_a.yxmd" in exc_info.value.filepath
    assert exc_info.value.message  # non-empty plain-English message


def test_parse_malformed_xml_raises(tmp_path: pathlib.Path) -> None:
    """MalformedXMLError raised for a file with invalid XML; __cause__ is set."""
    path_a = write_fixture(tmp_path, "malformed.yxmd", MALFORMED_XML)
    path_b = write_fixture(tmp_path, "valid.yxmd", MINIMAL_YXMD)

    with pytest.raises(MalformedXMLError) as exc_info:
        parse(path_a, path_b)

    assert exc_info.value.filepath  # non-empty filepath
    assert exc_info.value.__cause__ is not None  # chained from lxml XMLSyntaxError


def test_parse_empty_file_raises(tmp_path: pathlib.Path) -> None:
    """MalformedXMLError raised for a zero-byte file (lxml: 'Document is empty')."""
    path_a = write_fixture(tmp_path, "empty.yxmd", EMPTY_FILE)
    path_b = write_fixture(tmp_path, "valid.yxmd", MINIMAL_YXMD)

    with pytest.raises(MalformedXMLError):
        parse(path_a, path_b)


def test_parse_binary_content_raises(tmp_path: pathlib.Path) -> None:
    """MalformedXMLError raised for a file containing binary (PNG magic bytes)."""
    path_a = write_fixture(tmp_path, "binary.yxmd", BINARY_CONTENT)
    path_b = write_fixture(tmp_path, "valid.yxmd", MINIMAL_YXMD)

    with pytest.raises(MalformedXMLError):
        parse(path_a, path_b)


def test_parse_directory_raises(tmp_path: pathlib.Path) -> None:
    """Passing a directory path raises UnreadableFileError or MalformedXMLError.

    The parser's pre-flight stage catches ``not path.is_file()`` and raises
    UnreadableFileError; on some platforms lxml itself raises first.
    """
    dir_path = tmp_path / "a_directory"
    dir_path.mkdir()
    path_b = write_fixture(tmp_path, "valid.yxmd", MINIMAL_YXMD)

    with pytest.raises((UnreadableFileError, MalformedXMLError)):
        parse(dir_path, path_b)


# ---------------------------------------------------------------------------
# Fail-fast and base-class tests
# ---------------------------------------------------------------------------


def test_parse_fail_fast_on_path_a(tmp_path: pathlib.Path) -> None:
    """parse() never reads path_b when path_a fails.

    Both paths are non-existent.  The exception's filepath must mention only
    path_a, not path_b, proving parse() terminated before checking path_b.
    """
    path_a = tmp_path / "missing.yxmd"  # does NOT exist
    path_b = tmp_path / "also_missing.yxmd"  # also does NOT exist

    with pytest.raises(MissingFileError) as exc_info:
        parse(path_a, path_b)

    # path_a must appear in the error
    assert "missing.yxmd" in exc_info.value.filepath
    # path_b must NOT appear (would indicate path_b was inspected)
    assert "also_missing.yxmd" not in exc_info.value.filepath


def test_parse_error_is_parse_error_subclass(tmp_path: pathlib.Path) -> None:
    """All raised errors subclass ParseError for unified CLI exception handling."""
    path_a = tmp_path / "nonexistent.yxmd"  # does NOT exist
    path_b = write_fixture(tmp_path, "valid.yxmd", MINIMAL_YXMD)

    with pytest.raises(ParseError):
        parse(path_a, path_b)


# ---------------------------------------------------------------------------
# Raw <Node> XML capture
# ---------------------------------------------------------------------------


def test_parse_captures_raw_node_xml(tmp_path: pathlib.Path) -> None:
    """Each parsed node keeps its original <Node> XML source, dedented so the
    opening and closing tags sit at column 0."""
    path_a = write_fixture(tmp_path, "workflow_a.yxmd", MINIMAL_YXMD)
    path_b = write_fixture(tmp_path, "workflow_b.yxmd", MINIMAL_YXMD)

    doc_a, _ = parse(path_a, path_b)

    node1 = next(n for n in doc_a.nodes if int(n.tool_id) == 1)
    assert node1.raw_xml.startswith('<Node ToolID="1">')
    assert node1.raw_xml.rstrip().endswith("</Node>")
    # Dedented: closing tag at column 0, children keep relative indentation
    lines = node1.raw_xml.splitlines()
    assert lines[-1] == "</Node>"
    assert any(line.startswith("  <GuiSettings") for line in lines)
    # Original configuration content is preserved
    assert 'File RecordLimit="0"' in node1.raw_xml
    assert "data.csv" in node1.raw_xml


def test_programmatic_node_has_empty_raw_xml() -> None:
    """AlteryxNode built without XML defaults to raw_xml == ''."""
    from yxray.models.types import ToolID

    node = AlteryxNode(tool_id=ToolID(1), tool_type="Filter", x=0.0, y=0.0)
    assert node.raw_xml == ""
