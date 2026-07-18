"""CLI smoke tests for yxray.cli.

Uses CliRunner() — click 8.2+ always separates stdout and stderr streams.
- result.stdout: only typer.echo() without err=True, and --json output
- result.stderr: spinner (cleared), error messages, status summary

Invocation pattern: runner.invoke(app, ["diff", str(path_a), str(path_b)])
  The app has multiple subcommands (diff, inspect); "diff" must be explicit.

Zero subprocess imports — all tests run in-process via CliRunner.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.fixtures.cli import (
    IDENTICAL_YXMD,
    MALFORMED_XML,
    MINIMAL_YXMD_A,
    MINIMAL_YXMD_B,
    POSITION_YXMD_A,
    POSITION_YXMD_B,
    UI_TOOL_YXMD,
    UI_TOOL_YXMD_CHANGED,
)
from yxray.cli import _collect_deps, app
from yxray.manual_clusters import workflow_fingerprint
from yxray.parser import parse_one


@pytest.fixture(autouse=True)
def no_browser():
    """Prevent webbrowser.open from launching a browser during tests."""
    with patch("yxray.cli.webbrowser.open"):
        yield


runner = CliRunner()  # Click 8.2+ separates stdout/stderr by default

TWO_NODE_YXMD = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="901">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties><Configuration/></Properties>
    </Node>
    <Node ToolID="902">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Select">
        <Position x="160" y="100"/>
      </GuiSettings>
      <Properties><Configuration/></Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="901" Connection="Output"/>
      <Destination ToolID="902" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


def test_diff_identical_files_exit_code_0(tmp_path: pathlib.Path) -> None:
    """Identical files produce exit code 0 (no differences)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)

    result = runner.invoke(app, ["diff", str(path_a), str(path_b)])

    assert result.exit_code == 0


def test_diff_json_identical_files_emits_empty_json(tmp_path: pathlib.Path) -> None:
    """--json with identical files: exit code 0 AND valid empty JSON on stdout.

    Locked decision from CONTEXT.md: 'When no differences found and --json is used:
    print empty diff JSON (consistent output, no special-casing for downstream tools)'.
    """
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)

    result = runner.invoke(app, ["diff", str(path_a), str(path_b), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["added"] == []
    assert data["removed"] == []
    assert data["modified"] == []
    assert "metadata" in data  # governance metadata always present


def test_diff_different_files_exit_code_1(tmp_path: pathlib.Path) -> None:
    """Different files produce exit code 1 (differences detected)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, ["diff", str(path_a), str(path_b)])

    assert result.exit_code == 1


def test_diff_missing_file_exit_code_2(tmp_path: pathlib.Path) -> None:
    """Missing file produces exit code 2 with error message on stderr."""
    path_b = tmp_path / "b.yxmd"
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, ["diff", "nonexistent.yxmd", str(path_b)])

    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_diff_malformed_xml_exit_code_2(tmp_path: pathlib.Path) -> None:
    """Malformed XML produces exit code 2 with error message on stderr."""
    path_a = tmp_path / "bad.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MALFORMED_XML)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, ["diff", str(path_a), str(path_b)])

    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_inspect_cluster_file_embeds_manual_clusters(
    tmp_path: pathlib.Path,
) -> None:
    workflow = tmp_path / "workflow.yxmd"
    workflow.write_bytes(TWO_NODE_YXMD)
    doc = parse_one(workflow)
    cluster_file = tmp_path / "clusters.json"
    cluster_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow_fingerprint": workflow_fingerprint(doc),
                "manual_clusters": [
                    {"label": "prep", "tool_ids": [901, 902]},
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.html"

    result = runner.invoke(
        app,
        [
            "inspect",
            str(workflow),
            "--cluster-file",
            str(cluster_file),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    html = output.read_text(encoding="utf-8")
    assert '"manual_clusters": [{"label": "prep", "tool_ids": [901, 902]}]' in html


def test_inspect_no_filter_ui_tools_flag_includes_interface_nodes(
    tmp_path: pathlib.Path,
) -> None:
    """Regression: --filter-ui-tools/--no-filter-ui-tools must actually toggle.

    Previously registered as a single "--no-filter-ui-tools" name (no "/" pair),
    which click/typer never negates from its True default — the flag was a
    silent no-op and every invocation behaved as if UI tools were filtered.
    """
    workflow = tmp_path / "workflow.yxmd"
    workflow.write_bytes(UI_TOOL_YXMD)

    default_result = runner.invoke(app, ["inspect", str(workflow), "-o", str(tmp_path / "a.html")])
    unfiltered_result = runner.invoke(
        app,
        ["inspect", str(workflow), "--no-filter-ui-tools", "-o", str(tmp_path / "b.html")],
    )
    explicit_filtered_result = runner.invoke(
        app,
        ["inspect", str(workflow), "--filter-ui-tools", "-o", str(tmp_path / "c.html")],
    )

    assert "(1 nodes" in default_result.stderr
    assert "(2 nodes" in unfiltered_result.stderr
    assert "(1 nodes" in explicit_filtered_result.stderr


def test_diff_no_filter_ui_tools_flag_detects_interface_node_changes(
    tmp_path: pathlib.Path,
) -> None:
    """Regression: diff must only see the changed TextBox when unfiltered."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(UI_TOOL_YXMD)
    path_b.write_bytes(UI_TOOL_YXMD_CHANGED)

    default_result = runner.invoke(app, ["diff", str(path_a), str(path_b)])
    unfiltered_result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--no-filter-ui-tools"]
    )

    assert default_result.exit_code == 0  # only diff is inside a filtered-out TextBox
    assert unfiltered_result.exit_code == 1  # unfiltered: the TextBox change is visible


def test_cluster_backup_list_restore_commands(tmp_path: pathlib.Path) -> None:
    cluster_file = tmp_path / "clusters.json"
    cluster_file.write_text('{"version": 1}', encoding="utf-8")

    backup_result = runner.invoke(app, ["cluster", "backup", str(cluster_file)])

    assert backup_result.exit_code == 0
    backup_path = pathlib.Path(backup_result.stdout.strip())
    assert backup_path.is_file()

    cluster_file.write_text('{"version": 2}', encoding="utf-8")
    list_result = runner.invoke(app, ["cluster", "list-backups", str(cluster_file)])

    assert list_result.exit_code == 0
    assert str(backup_path) in list_result.stdout

    restore_result = runner.invoke(app, ["cluster", "restore", str(cluster_file)])

    assert restore_result.exit_code == 0
    assert cluster_file.read_text(encoding="utf-8") == '{"version": 1}'


# ---------------------------------------------------------------------------
# Output file tests
# ---------------------------------------------------------------------------


def test_diff_writes_html_report_by_default(tmp_path: pathlib.Path) -> None:
    """Default invocation writes diff_report.html to --output path."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(output)]
    )

    assert result.exit_code == 1
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_diff_html_report_contains_governance_metadata(tmp_path: pathlib.Path) -> None:
    """Generated HTML report contains governance footer with sha256 hash of file A."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(output)]
    )

    assert result.exit_code == 1
    content = output.read_text(encoding="utf-8")
    assert "governance" in content  # <details id="governance"> block present
    # sha256_a must be a full 64-char hex string embedded in the HTML
    import hashlib

    expected_sha = hashlib.sha256(path_a.read_bytes()).hexdigest()
    assert expected_sha in content, (
        "Full 64-char SHA-256 of file A must appear in HTML report"
    )


def test_diff_output_flag_writes_custom_path(tmp_path: pathlib.Path) -> None:
    """--output flag writes HTML report to the specified custom path."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    custom = tmp_path / "custom_report.html"

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(custom)]
    )

    assert result.exit_code == 1
    assert custom.exists()


def test_diff_output_flag_existing_dir_writes_default_name(
    tmp_path: pathlib.Path,
) -> None:
    """--output pointing at an existing directory writes diff_report.html inside it."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    out_dir = tmp_path / "reports"
    out_dir.mkdir()

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(out_dir)]
    )

    assert result.exit_code == 1
    assert (out_dir / "diff_report.html").exists()


def test_diff_no_file_written_on_clean_diff(tmp_path: pathlib.Path) -> None:
    """When no differences found, no output file is written (exit 0, no file)."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(IDENTICAL_YXMD)
    path_b.write_bytes(IDENTICAL_YXMD)
    output = tmp_path / "diff_report.html"

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(output)]
    )

    assert result.exit_code == 0
    assert not output.exists()


# ---------------------------------------------------------------------------
# Flag behavior tests
# ---------------------------------------------------------------------------


def test_diff_json_flag_writes_to_stdout(tmp_path: pathlib.Path) -> None:
    """--json flag writes valid JSON to stdout with required top-level keys."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)

    result = runner.invoke(app, ["diff", str(path_a), str(path_b), "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert "added" in data
    assert "removed" in data
    assert "modified" in data
    assert "metadata" in data
    assert len(data["metadata"]["sha256_a"]) == 64  # full 64-char SHA-256


def test_diff_quiet_flag_suppresses_stderr(tmp_path: pathlib.Path) -> None:
    """--quiet flag suppresses status summary; exit code still reflects diff status.

    Tests the behavioral guarantee: the 'N changes detected' summary line must not
    appear on stderr when --quiet is set. Uses substring check rather than empty-string
    assertion to avoid flakiness from Rich's TTY-detection behavior in CliRunner context
    (Rich may emit spinner artifacts depending on environment).
    """
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(MINIMAL_YXMD_A)
    path_b.write_bytes(MINIMAL_YXMD_B)
    output = tmp_path / "report.html"

    result = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--output", str(output), "--quiet"]
    )

    assert result.exit_code == 1
    # Verify behavioral guarantee: summary line is suppressed (not exact empty string,
    # which can be flaky due to Rich TTY detection in CliRunner)
    assert "changes detected" not in result.stderr


def test_diff_include_positions_detects_position_change(tmp_path: pathlib.Path) -> None:
    """--include-positions flag causes position-only changes to produce exit code 1."""
    path_a = tmp_path / "a.yxmd"
    path_b = tmp_path / "b.yxmd"
    path_a.write_bytes(POSITION_YXMD_A)
    path_b.write_bytes(POSITION_YXMD_B)

    # Without flag: position-only change → exit code 0 (positions excluded by default)
    result_no_flag = runner.invoke(app, ["diff", str(path_a), str(path_b)])
    assert result_no_flag.exit_code == 0

    # With flag: position-only change → exit code 1 (positions included)
    result_with_flag = runner.invoke(
        app, ["diff", str(path_a), str(path_b), "--include-positions"]
    )
    assert result_with_flag.exit_code == 1


def test_collect_deps_always_includes_pandas() -> None:
    assert _collect_deps("import pandas as pd\n") == ["pandas"]


def test_collect_deps_detects_geopandas_import() -> None:
    code = "import geopandas as gpd\nimport pandas as pd\n"
    assert _collect_deps(code) == ["pandas", "geopandas"]


def test_collect_deps_detects_numpy_import() -> None:
    code = "import numpy as np\nimport pandas as pd\n"
    assert _collect_deps(code) == ["pandas", "numpy"]


def test_collect_deps_detects_excel_usage() -> None:
    code = 'import pandas as pd\ndf = pd.read_excel("x.xlsx")\n'
    assert _collect_deps(code) == ["pandas", "openpyxl"]


def test_collect_deps_combines_all_detected_deps() -> None:
    code = (
        "import geopandas as gpd\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        'df.to_excel("out.xlsx")\n'
    )
    assert _collect_deps(code) == ["pandas", "geopandas", "numpy", "openpyxl"]


def test_explain_output_flag_writes_to_custom_dir(tmp_path: pathlib.Path) -> None:
    """--output flag writes the .md/.py/pyproject.toml trio into the given dir."""
    workflow = tmp_path / "wf.yxmd"
    workflow.write_bytes(MINIMAL_YXMD_A)
    out_dir = tmp_path / "custom_output"

    result = runner.invoke(app, ["explain", str(workflow), "--output", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "wf.md").exists()
    assert (out_dir / "wf.py").exists()
    assert (out_dir / "pyproject.toml").exists()


FILTER_EXPR_YXMD = b"""<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2020.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput">
        <Position x="60" y="100"/>
      </GuiSettings>
      <Properties><Configuration>
        <File>C:\\Data\\sales.csv</File>
      </Configuration></Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter">
        <Position x="160" y="100"/>
      </GuiSettings>
      <Properties><Configuration>
        <Expression>[Country] = "Japan"</Expression>
      </Configuration></Properties>
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


def test_explain_md_omits_tool_summary(tmp_path: pathlib.Path) -> None:
    """The .md report no longer emits the Tool Summary table; it goes straight
    to the Python Scaffold (warnings section aside)."""
    workflow = tmp_path / "wf.yxmd"
    workflow.write_bytes(FILTER_EXPR_YXMD)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["explain", str(workflow), "--output", str(out_dir)])

    assert result.exit_code == 0
    md = (out_dir / "wf.md").read_text(encoding="utf-8")
    assert "## Tool Summary" not in md
    assert "| ToolID | Type | Category |" not in md
    # The Python Scaffold section is still produced
    assert "## Python Scaffold" in md
    assert "    df2 = df1[df1[\"Country\"] == 'Japan']" in md


def test_explain_md_scaffold_is_indented_for_def_body(
    tmp_path: pathlib.Path,
) -> None:
    """Every .md python block is fenced and indented so it can be pasted
    directly under a def statement; XML content shares the same indent."""
    workflow = tmp_path / "wf.yxmd"
    workflow.write_bytes(FILTER_EXPR_YXMD)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["explain", str(workflow), "--output", str(out_dir)])

    assert result.exit_code == 0
    md = (out_dir / "wf.md").read_text(encoding="utf-8")
    blocks = [
        part.split("\n```", maxsplit=1)[0]
        for part in md.split("```python\n")[1:]
    ]
    assert blocks[0].startswith('    """Scaffold generated by yxray from wf.yxmd"""')
    assert any(
        "\n    df2 = df1[df1[\"Country\"] == 'Japan']" in block for block in blocks
    )
    # All fenced content (python and xml alike) is indented; only fences
    # sit at column 0
    scaffold_section = md.split("## Python Scaffold", maxsplit=1)[1]
    for line in scaffold_section.splitlines():
        if line.startswith("```") or not line:
            continue
        assert line.startswith("    ")


def test_explain_md_interleaves_node_xml_after_each_tool(
    tmp_path: pathlib.Path,
) -> None:
    """Each ToolID's python block is directly followed by its <Node> XML."""
    workflow = tmp_path / "wf.yxmd"
    workflow.write_bytes(FILTER_EXPR_YXMD)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["explain", str(workflow), "--output", str(out_dir)])

    assert result.exit_code == 0
    md = (out_dir / "wf.md").read_text(encoding="utf-8")
    # XML source blocks are present for both tools, indented like the python
    assert md.count("```xml") == 2
    assert '\n    <Node ToolID="1">' in md
    assert '\n    <Node ToolID="2">' in md
    # The Filter tool's XML block comes right after its python block
    tool2_pos = md.index("# ToolID 2: Filter")
    xml2_pos = md.index('<Node ToolID="2">')
    assert xml2_pos > tool2_pos
    between = md[tool2_pos:xml2_pos]
    assert "# ToolID" not in between[1:]  # no other tool in between
    assert "```xml" in between
    # The XML keeps the original tool configuration
    assert "[Country] = &quot;Japan&quot;" in md or '[Country] = "Japan"' in md
    # Two blank lines separate a closing xml fence from the next python block
    assert "```\n\n\n```python" in md


def test_explain_output_flag_existing_dir_writes_files(tmp_path: pathlib.Path) -> None:
    """--output pointing at an existing directory still writes all three files."""
    workflow = tmp_path / "wf.yxmd"
    workflow.write_bytes(MINIMAL_YXMD_A)
    out_dir = tmp_path / "existing"
    out_dir.mkdir()

    result = runner.invoke(app, ["explain", str(workflow), "--output", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "wf.md").exists()
    assert (out_dir / "wf.py").exists()
    assert (out_dir / "pyproject.toml").exists()
