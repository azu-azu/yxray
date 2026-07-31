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


def test_formula_hint_agrees_with_what_scaffold_generates() -> None:
    # The hint and the generator are two separate code paths for the same
    # tool (docs/explain-output-anatomy.md), and they had drifted: the hint
    # said .assign() while the generator has always emitted subscript
    # assignment — deliberately, since Alteryx applies formula rows top to
    # bottom and field names are not always valid identifiers.
    hint, supported = python_hint_for("Formula")
    assert supported == "yes"
    assert ".assign(" not in hint
    assert 'df["<field>"] = <expr>' in hint
    # The missing-value rules the generator applies (see
    # docs/alteryx-pandas-differences.md 19) are visible here too.
    assert "fillna" in hint
    assert "fill_empty" in hint
    assert "np.where" in hint


def test_spatial_info_hint_agrees_with_what_scaffold_generates() -> None:
    # Same two-code-path trap as Formula (docs/explain-output-anatomy.md):
    # the generator translates CentroidObj only, so the hint must not
    # advertise the .area / .length it deliberately refuses to emit.
    hint, supported = python_hint_for("SpatialInfo")
    assert supported == "partial"
    assert "gpd.GeoSeries" in hint
    assert ".centroid" in hint
    assert "CentroidObj only" in hint
    assert ".area" not in hint
    assert ".length" not in hint


def test_distance_hint_agrees_with_what_scaffold_generates() -> None:
    # The hint used to show sjoin_nearest, which is the two-input nearest
    # form — the generator translates the single-input one (two spatial
    # fields of one record) and refuses two-input mode, so the hint must
    # not point at a shape the generator never emits.
    hint, supported = python_hint_for("Distance")
    assert supported == "partial"
    assert "sjoin_nearest" not in hint
    assert "estimate_utm_crs" in hint
    assert "routing service" in hint


def test_alteryx_formula_shares_the_formula_hint() -> None:
    assert python_hint_for("AlteryxFormula") == python_hint_for("Formula")


def test_python_hint_for_buffer_is_partial() -> None:
    hint, supported = python_hint_for("Buffer")
    assert supported == "partial"
    assert "buffer" in hint


def test_python_hint_for_directory_is_partial() -> None:
    hint, supported = python_hint_for("Directory")
    assert supported == "partial"
    assert "glob" in hint.lower()
