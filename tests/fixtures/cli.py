"""Minimal .yxmd XML byte fixtures for CLI end-to-end tests.

ToolIDs 901+ allocated for Phase 9. No collision with Phases 1-8 (max 815).
Write bytes to tmp_path in tests — do NOT commit .yxmd files to disk.
"""

from __future__ import annotations

# ToolID 901 — Filter tool, base expression
MINIMAL_YXMD_A: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="901">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field1 > 0</Expression>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""

# ToolID 901 — same tool, changed filter expression → produces exit code 1
MINIMAL_YXMD_B: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="901">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field1 > 100</Expression>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""

# Identical content — produces exit code 0
IDENTICAL_YXMD: bytes = MINIMAL_YXMD_A

# ToolID 902 — position differs between A and B, config is identical
# Used to test --include-positions flag
POSITION_YXMD_A: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="902">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="10" y="20"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field2 > 5</Expression>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""

POSITION_YXMD_B: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="902">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="50" y="80"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field2 > 5</Expression>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""

# Malformed XML — triggers MalformedXMLError → exit code 2
MALFORMED_XML: bytes = b"<not valid xml><<"

# ToolID 901 — Filter (data), ToolID 903 — TextBox (AlteryxGuiToolkit interface node)
# Used to regression-test the --filter-ui-tools/--no-filter-ui-tools flag pair
# (bug: previously registered as a single "--no-filter-ui-tools" name, which
# click/typer never negates — the flag was a silent no-op).
UI_TOOL_YXMD: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="901">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field1 > 0</Expression>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="903">
      <GuiSettings Plugin="AlteryxGuiToolkit.TextBox.TextBox">
        <Position x="60" y="200"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Text>note</Text>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""

# Same as UI_TOOL_YXMD but the TextBox's text differs — a change that is only
# visible when Interface nodes are NOT filtered out.
UI_TOOL_YXMD_CHANGED: bytes = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="901">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Expression>Field1 > 0</Expression>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="903">
      <GuiSettings Plugin="AlteryxGuiToolkit.TextBox.TextBox">
        <Position x="60" y="200"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Text>changed note</Text>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
</AlteryxDocument>"""
