"""Synthetic .yxmd XML byte-string constants for parser tests.

Each constant is a valid (or intentionally invalid) Alteryx workflow XML
document encoded as UTF-8 bytes.  Tests write these bytes to temporary
files via ``tmp_path`` fixtures so that the parser operates on real file
I/O paths.

No project-internal imports — safe to load before the package is fully
initialised.
"""

from __future__ import annotations

__all__ = [
    "MINIMAL_YXMD",
    "TWO_NODE_YXMD",
    "EMPTY_WORKFLOW_YXMD",
    "REPEATED_FIELDS_YXMD",
    "CONTAINER_YXMD",
    "CHILDNODES_CONTAINER_YXMD",
    "MALFORMED_XML",
    "EMPTY_FILE",
    "BINARY_CONTENT",
]

# ---------------------------------------------------------------------------
# Valid fixtures
# ---------------------------------------------------------------------------

# MINIMAL_YXMD: one tool (DbFileInput, ToolID=1) connected to a second tool
# (Select, ToolID=2).  Includes GuiSettings/Position for x/y, and a simple
# Configuration with a File element containing an XML attribute and text
# content — exercises the @key and #text conventions in _element_to_dict.
MINIMAL_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2022.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput">
        <Position x="54" y="54"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <File RecordLimit="0">data.csv</File>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">
        <Position x="162" y="54"/>
      </GuiSettings>
      <Properties>
        <Configuration/>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="Output"/>
      <Destination ToolID="2" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""

# TWO_NODE_YXMD: two tools with distinct tool types, positions, and configs.
# One connection from tool 1 to tool 2.  Used for the dual-parse independence
# test so that doc_a and doc_b are distinguishable by filepath.
TWO_NODE_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2022.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput">
        <Position x="100" y="200"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <File RecordLimit="100">input.csv</File>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxFilter.AlteryxFilter">
        <Position x="300" y="200"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field1 > 0</Expression>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="Output"/>
      <Destination ToolID="2" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""

# EMPTY_WORKFLOW_YXMD: valid AlteryxDocument root with empty Nodes and
# Connections elements.  The parser must return WorkflowDoc with nodes=()
# and connections=().
EMPTY_WORKFLOW_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2022.1">
  <Nodes/>
  <Connections/>
</AlteryxDocument>
"""

# REPEATED_FIELDS_YXMD: one tool whose Configuration contains a Fields element
# with three Field children sharing the same tag.  Verifies list promotion in
# _element_to_dict: {"Fields": {"Field": [{"@name": "id"}, ...]}}
REPEATED_FIELDS_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2022.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">
        <Position x="54" y="54"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Fields>
            <Field name="id" type="Int32" size="4"/>
            <Field name="value" type="Double" size="8"/>
            <Field name="label" type="String" size="256"/>
          </Fields>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>
"""

# CONTAINER_YXMD: one ToolContainer (ToolID=10, Caption="My Container") containing
# two member nodes (ToolID=1 and ToolID=2 with ToolContainerID="10"), plus one
# node outside the container (ToolID=3).  Verifies that parser.py extracts
# ToolContainerID from Properties/EngineSettings and stores it as container_id.
CONTAINER_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2022.1">
  <Nodes>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxBasePluginsGui.ToolContainer.ToolContainer">
        <Position x="200" y="54"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Caption>My Container</Caption>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter">
        <Position x="216" y="108"/>
      </GuiSettings>
      <Properties>
        <Configuration><Expression>[x] > 0</Expression></Configuration>
        <EngineSettings ToolContainerID="10"/>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula">
        <Position x="378" y="108"/>
      </GuiSettings>
      <Properties>
        <Configuration><Expression>[x] * 2</Expression></Configuration>
        <EngineSettings ToolContainerID="10"/>
      </Properties>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">
        <Position x="540" y="108"/>
      </GuiSettings>
      <Properties>
        <Configuration><File>out.csv</File></Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="True"/>
      <Destination ToolID="2" Connection="Input"/>
    </Connection>
    <Connection>
      <Origin ToolID="2" Connection="Output"/>
      <Destination ToolID="3" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""

# CHILDNODES_CONTAINER_YXMD: same shape as CONTAINER_YXMD (container ToolID=10
# with members ToolID=1/2, plus an outside node ToolID=3) but member nodes are
# nested inside the container's own <ChildNodes> element instead of carrying
# a ToolContainerID attribute — the format newer Alteryx Designer versions
# (observed at yxmdVer="2023.2") write. Verifies that parser.py assigns
# container_id from XML nesting, not just the EngineSettings attribute.
CHILDNODES_CONTAINER_YXMD: bytes = b"""\
<?xml version="1.0" encoding="utf-8"?>
<AlteryxDocument yxmdVer="2023.2">
  <Nodes>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer">
        <Position x="200" y="54"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Caption>My Container</Caption>
        </Configuration>
      </Properties>
      <ChildNodes>
        <Node ToolID="1">
          <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter">
            <Position x="216" y="108"/>
          </GuiSettings>
          <Properties>
            <Configuration><Expression>[x] > 0</Expression></Configuration>
          </Properties>
        </Node>
        <Node ToolID="2">
          <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula">
            <Position x="378" y="108"/>
          </GuiSettings>
          <Properties>
            <Configuration><Expression>[x] * 2</Expression></Configuration>
          </Properties>
        </Node>
      </ChildNodes>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">
        <Position x="540" y="108"/>
      </GuiSettings>
      <Properties>
        <Configuration><File>out.csv</File></Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="True"/>
      <Destination ToolID="2" Connection="Input"/>
    </Connection>
    <Connection>
      <Origin ToolID="2" Connection="Output"/>
      <Destination ToolID="3" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""

# ---------------------------------------------------------------------------
# Invalid / error-triggering fixtures
# ---------------------------------------------------------------------------

# MALFORMED_XML: bytes that are NOT well-formed XML.  The closing tag does not
# match the open tag.  lxml will raise XMLSyntaxError (recover=False).
MALFORMED_XML: bytes = b"<AlteryxDocument><Nodes></AlteryxDocument>"

# EMPTY_FILE: zero bytes.  lxml reports "Document is empty" as XMLSyntaxError.
EMPTY_FILE: bytes = b""

# BINARY_CONTENT: PNG magic bytes.  Not XML at all; triggers XMLSyntaxError.
BINARY_CONTENT: bytes = b"\x89PNG\r\n\x1a\n"
