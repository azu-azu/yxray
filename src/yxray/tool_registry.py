"""Shared Alteryx tool metadata used by summaries, hints, and scaffolds."""

from __future__ import annotations

from dataclasses import dataclass

ToolCategory = str

UNSUPPORTED_PYTHON_HINT = "# TODO: no direct pandas equivalent — review manually"

# regex=False by default — write regex=True only when a pattern (| ^ .)
# is actually intended; Alteryx string matching is literal.
_FILTER_HINT = (
    "df = df[mask]\n"
    '# ~df[col].str.contains("...", regex=False, na=False)\n'
    '# df[col].isna() | (df[col] == "")'
)


@dataclass(frozen=True, slots=True)
class ToolInfo:
    display_name: str
    category: ToolCategory
    python_hint: str = UNSUPPORTED_PYTHON_HINT
    python_supported: str = "no"  # "yes", "partial", or "no"


TOOL_REGISTRY: dict[str, ToolInfo] = {
    "DbFileInput": ToolInfo(
        "Input", "input", "pd.read_csv(...) / pd.read_excel(...)", "yes"
    ),
    "InputData": ToolInfo(
        "Input", "input", "pd.read_csv(...) / pd.read_excel(...)", "yes"
    ),
    "TextInput": ToolInfo("Text Input", "input", "pd.DataFrame({...})", "yes"),
    "DynamicInput": ToolInfo(
        "Dynamic Input",
        "input",
        "# TODO: loop over files — pd.concat([pd.read_csv(f) for f in files])",
        "no",
    ),
    "DbFileOutput": ToolInfo(
        "Output", "output", "df.to_csv(...) / df.to_excel(..., index=False)", "yes"
    ),
    "OutputData": ToolInfo(
        "Output", "output", "df.to_csv(...) / df.to_excel(..., index=False)", "yes"
    ),
    "BrowseV2": ToolInfo(
        "Browse", "output", "# Browse — no output step needed in Python", "yes"
    ),
    "Browse": ToolInfo(
        "Browse", "output", "# Browse — no output step needed in Python", "yes"
    ),
    "AlteryxFilter": ToolInfo("Filter", "transform", _FILTER_HINT, "yes"),
    "Filter": ToolInfo("Filter", "transform", _FILTER_HINT, "yes"),
    "AlteryxSelect": ToolInfo(
        "Select Fields",
        "transform",
        "df = df[[...]].rename(columns={...})",
        "yes",
    ),
    "Select": ToolInfo(
        "Select Fields",
        "transform",
        "df = df[[...]].rename(columns={...})",
        "yes",
    ),
    "AlteryxFormula": ToolInfo(
        "Formula", "transform", "df = df.assign(<field>=<expr>)", "yes"
    ),
    "Formula": ToolInfo(
        "Formula", "transform", "df = df.assign(<field>=<expr>)", "yes"
    ),
    "MultiFieldFormula": ToolInfo(
        "Multi-Field Formula",
        "transform",
        "# TODO: apply same formula across columns — df.apply(..., axis=1)",
        "no",
    ),
    "AlteryxJoin": ToolInfo(
        "Join", "transform", "pd.merge(left, right, on=..., how='inner')", "yes"
    ),
    "Join": ToolInfo(
        "Join", "transform", "pd.merge(left, right, on=..., how='inner')", "yes"
    ),
    "AlteryxUnion": ToolInfo(
        "Union", "transform", "pd.concat([df1, df2], ignore_index=True)", "yes"
    ),
    "Union": ToolInfo(
        "Union", "transform", "pd.concat([df1, df2], ignore_index=True)", "yes"
    ),
    "AlteryxAppend": ToolInfo(
        "Append", "transform", "pd.concat([left, right], ignore_index=True)", "yes"
    ),
    "Append": ToolInfo(
        "Append", "transform", "pd.concat([left, right], ignore_index=True)", "yes"
    ),
    "AlteryxSummarize": ToolInfo(
        "Summarize", "transform", "df.groupby([...]).agg({...})", "yes"
    ),
    "Summarize": ToolInfo(
        "Summarize", "transform", "df.groupby([...]).agg({...})", "yes"
    ),
    "AlteryxSort": ToolInfo("Sort", "transform", "df.sort_values([...])", "yes"),
    "Sort": ToolInfo("Sort", "transform", "df.sort_values([...])", "yes"),
    "AlteryxSample": ToolInfo(
        "Sample", "transform", "df.head(n) / df.sample(n)", "yes"
    ),
    "Sample": ToolInfo("Sample", "transform", "df.head(n) / df.sample(n)", "yes"),
    "AlteryxCrossTab": ToolInfo(
        "Cross Tab",
        "transform",
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        "yes",
    ),
    "CrossTab": ToolInfo(
        "Cross Tab",
        "transform",
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        "yes",
    ),
    "AlteryxTranspose": ToolInfo(
        "Transpose",
        "transform",
        "df.melt(id_vars=[...], var_name=..., value_name=...)",
        "yes",
    ),
    "Transpose": ToolInfo(
        "Transpose",
        "transform",
        "df.melt(id_vars=[...], var_name=..., value_name=...)",
        "yes",
    ),
    "Unique": ToolInfo(
        "Unique", "transform", "df.drop_duplicates(subset=[...])", "yes"
    ),
    "RecordID": ToolInfo(
        "Record ID",
        "transform",
        "df = df.reset_index(drop=True); df['RecordID'] = df.index + 1",
        "yes",
    ),
    "CountRecords": ToolInfo("Count Records", "transform", "len(df)", "yes"),
    "DateTime": ToolInfo(
        "Date/Time", "transform", "pd.to_datetime(df[...], format=...)", "yes"
    ),
    "DataCleansing": ToolInfo(
        "Data Cleansing",
        "transform",
        "df[...].str.strip() / df[...].fillna(...)",
        "yes",
    ),
    "FindReplace": ToolInfo(
        "Find & Replace",
        "transform",
        'pd.merge(data, lookup, ..., how="left") / df[...].map(lookup)',
        "partial",
    ),
    "AppendFields": ToolInfo(
        "Append Fields",
        "transform",
        'pd.merge(targets, sources, how="cross")',
        "yes",
    ),
    "CreatePoints": ToolInfo(
        "Create Points",
        "transform",
        "gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(x, y))",
        "yes",
    ),
    "SpatialMatch": ToolInfo(
        "Spatial Match",
        "transform",
        'gpd.sjoin(targets, universe, predicate="intersects")',
        "partial",
    ),
    "GenerateRows": ToolInfo(
        "Generate Rows", "transform", "pd.DataFrame(range(...))", "yes"
    ),
    "DynamicRename": ToolInfo(
        "Dynamic Rename",
        "transform",
        "# TODO: dynamic column rename — df.rename(columns=mapper_func)",
        "no",
    ),
    "AlteryxFuzzyMatch": ToolInfo(
        "Fuzzy Match",
        "transform",
        "# TODO: fuzzy matching — consider thefuzz / rapidfuzz",
        "no",
    ),
    "Tile": ToolInfo(
        "Tile", "transform", "# TODO: quantile binning — pd.qcut(df[...], q=...)", "no"
    ),
    "Random": ToolInfo(
        "Random Sample",
        "transform",
        "# TODO: random sample — df.sample(frac=...)",
        "no",
    ),
    "RunCommand": ToolInfo(
        "Run Command",
        "transform",
        "# TODO: subprocess.run([...], check=True)",
        "no",
    ),
    "ToolContainer": ToolInfo(
        "Container",
        "unknown",
        "# Container — groups tools, no Python equivalent",
        "yes",
    ),
}

JOIN_TOOL_SEGMENTS = frozenset({"AlteryxJoin", "Join"})
APPEND_SEGMENTS = frozenset({"AlteryxAppend", "Append"})
JOIN_SEGMENTS = JOIN_TOOL_SEGMENTS | APPEND_SEGMENTS
UNION_SEGMENTS = frozenset({"AlteryxUnion", "Union"})
AGGREGATE_SEGMENTS = frozenset(
    {
        "AlteryxSummarize",
        "Summarize",
        "AlteryxCrossTab",
        "CrossTab",
        "AlteryxTranspose",
        "Transpose",
    }
)
FILTER_SEGMENTS = frozenset({"AlteryxFilter", "Filter"})
FORMULA_SEGMENTS = frozenset({"AlteryxFormula", "Formula", "MultiFieldFormula"})
SELECT_SEGMENTS = frozenset({"AlteryxSelect", "Select"})

SCAFFOLD_INPUT_SEGMENTS = frozenset({"DbFileInput", "InputData"})
SCAFFOLD_OUTPUT_SEGMENTS = frozenset({"DbFileOutput", "OutputData"})
SCAFFOLD_TEXTINPUT_SEGMENTS = frozenset({"TextInput"})
SCAFFOLD_FILTER_SEGMENTS = FILTER_SEGMENTS
SCAFFOLD_SELECT_SEGMENTS = SELECT_SEGMENTS
SCAFFOLD_FORMULA_SEGMENTS = FORMULA_SEGMENTS - {"MultiFieldFormula"}
SCAFFOLD_JOIN_SEGMENTS = JOIN_TOOL_SEGMENTS
SCAFFOLD_UNION_SEGMENTS = UNION_SEGMENTS | APPEND_SEGMENTS
SCAFFOLD_SUMMARIZE_SEGMENTS = frozenset({"AlteryxSummarize", "Summarize"})
SCAFFOLD_SORT_SEGMENTS = frozenset({"AlteryxSort", "Sort"})
SCAFFOLD_SAMPLE_SEGMENTS = frozenset({"AlteryxSample", "Sample"})
SCAFFOLD_UNIQUE_SEGMENTS = frozenset({"Unique"})
SCAFFOLD_FINDREPLACE_SEGMENTS = frozenset({"FindReplace"})
SCAFFOLD_APPENDFIELDS_SEGMENTS = frozenset({"AppendFields"})
SCAFFOLD_CREATEPOINTS_SEGMENTS = frozenset({"CreatePoints"})
SCAFFOLD_SPATIALMATCH_SEGMENTS = frozenset({"SpatialMatch"})
SCAFFOLD_BROWSE_SEGMENTS = frozenset({"Browse", "BrowseV2"})
SCAFFOLD_SPATIAL_SEGMENTS = (
    SCAFFOLD_CREATEPOINTS_SEGMENTS | SCAFFOLD_SPATIALMATCH_SEGMENTS
)


def tool_segment(tool_type: str) -> str:
    return tool_type.split(".")[-1]


def classify_tool(tool_type: str) -> tuple[str, ToolCategory]:
    """Return (display_name, category) for a plugin string."""
    segment = tool_segment(tool_type)
    if info := TOOL_REGISTRY.get(segment):
        return info.display_name, info.category
    name = segment.replace("_", " ").replace("-", " ")
    return name, "unknown"


def python_hint_for(tool_type: str) -> tuple[str, str]:
    """Return (python_hint, supported) for a plugin string.

    supported is one of "yes", "partial", or "no".
    """
    if info := TOOL_REGISTRY.get(tool_segment(tool_type)):
        return info.python_hint, info.python_supported
    return UNSUPPORTED_PYTHON_HINT, "no"
