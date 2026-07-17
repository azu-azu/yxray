import pytest

from yxray.tool_registry import classify_tool, python_hint_for


def test_classify_tool_falls_back_to_unknown_for_unregistered_type() -> None:
    display_name, category = classify_tool("SomeBrandNewTool")
    assert category == "unknown"
    assert display_name == "SomeBrandNewTool"


@pytest.mark.parametrize(
    ("plugin", "expected_name", "expected_category"),
    [
        (
            "AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula",
            "Multi-Row Formula",
            "transform",
        ),
        ("AlteryxBasePluginsGui.Directory.Directory", "Directory", "input"),
        (
            "AlteryxSpatialPluginsGui.SpatialInfo.SpatialInfo",
            "Spatial Info",
            "transform",
        ),
        (
            "AlteryxSpatialPluginsGui.PolySplit.PolySplit",
            "Poly Split",
            "transform",
        ),
        ("AlteryxSpatialPluginsGui.Distance.Distance", "Distance", "transform"),
        ("AlteryxSpatialPluginsGui.Buffer.Buffer", "Buffer", "transform"),
    ],
)
def test_classify_tool_recognizes_new_registry_entries(
    plugin: str, expected_name: str, expected_category: str
) -> None:
    display_name, category = classify_tool(plugin)
    assert display_name == expected_name
    assert category == expected_category


def test_python_hint_for_multi_row_formula_is_unsupported_but_specific() -> None:
    hint, supported = python_hint_for("MultiRowFormula")
    assert supported == "no"
    assert "Row-N" in hint or "shift" in hint


def test_python_hint_for_buffer_is_partial() -> None:
    hint, supported = python_hint_for("Buffer")
    assert supported == "partial"
    assert "buffer" in hint


def test_python_hint_for_directory_is_partial() -> None:
    hint, supported = python_hint_for("Directory")
    assert supported == "partial"
    assert "glob" in hint.lower()
