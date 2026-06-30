"""Shared Alteryx tool metadata used by summaries, hints, and scaffolds."""

from __future__ import annotations

from dataclasses import dataclass

ToolCategory = str

UNSUPPORTED_PYTHON_HINT = "# TODO: no direct pandas equivalent — review manually"


@dataclass(frozen=True, slots=True)
class ToolInfo:
    display_name: str
    category: ToolCategory
    python_hint: str = UNSUPPORTED_PYTHON_HINT
    python_supported: bool = False


TOOL_REGISTRY: dict[str, ToolInfo] = {
    "DbFileInput": ToolInfo(
        "Input", "input", "pd.read_csv(...) / pd.read_excel(...)", True
    ),
    "InputData": ToolInfo(
        "Input", "input", "pd.read_csv(...) / pd.read_excel(...)", True
    ),
    "TextInput": ToolInfo("Text Input", "input", "pd.DataFrame({...})", True),
    "DynamicInput": ToolInfo(
        "Dynamic Input",
        "input",
        "# TODO: loop over files — pd.concat([pd.read_csv(f) for f in files])",
        False,
    ),
    "DbFileOutput": ToolInfo(
        "Output", "output", "df.to_csv(...) / df.to_excel(..., index=False)", True
    ),
    "OutputData": ToolInfo(
        "Output", "output", "df.to_csv(...) / df.to_excel(..., index=False)", True
    ),
    "BrowseV2": ToolInfo(
        "Browse", "output", "# Browse — no output step needed in Python", True
    ),
    "Browse": ToolInfo(
        "Browse", "output", "# Browse — no output step needed in Python", True
    ),
    "AlteryxFilter": ToolInfo("Filter", "transform", "df = df[<condition>]", True),
    "Filter": ToolInfo("Filter", "transform", "df = df[<condition>]", True),
    "AlteryxSelect": ToolInfo(
        "Select Fields",
        "transform",
        "df = df[[...]].rename(columns={...})",
        True,
    ),
    "Select": ToolInfo(
        "Select Fields",
        "transform",
        "df = df[[...]].rename(columns={...})",
        True,
    ),
    "AlteryxFormula": ToolInfo(
        "Formula", "transform", "df = df.assign(<field>=<expr>)", True
    ),
    "Formula": ToolInfo(
        "Formula", "transform", "df = df.assign(<field>=<expr>)", True
    ),
    "MultiFieldFormula": ToolInfo(
        "Multi-Field Formula",
        "transform",
        "# TODO: apply same formula across columns — df.apply(..., axis=1)",
        False,
    ),
    "AlteryxJoin": ToolInfo(
        "Join", "transform", "pd.merge(left, right, on=..., how='inner')", True
    ),
    "Join": ToolInfo(
        "Join", "transform", "pd.merge(left, right, on=..., how='inner')", True
    ),
    "AlteryxUnion": ToolInfo(
        "Union", "transform", "pd.concat([df1, df2], ignore_index=True)", True
    ),
    "Union": ToolInfo(
        "Union", "transform", "pd.concat([df1, df2], ignore_index=True)", True
    ),
    "AlteryxAppend": ToolInfo(
        "Append", "transform", "pd.concat([left, right], ignore_index=True)", True
    ),
    "Append": ToolInfo(
        "Append", "transform", "pd.concat([left, right], ignore_index=True)", True
    ),
    "AlteryxSummarize": ToolInfo(
        "Summarize", "transform", "df.groupby([...]).agg({...})", True
    ),
    "Summarize": ToolInfo(
        "Summarize", "transform", "df.groupby([...]).agg({...})", True
    ),
    "AlteryxSort": ToolInfo("Sort", "transform", "df.sort_values([...])", True),
    "Sort": ToolInfo("Sort", "transform", "df.sort_values([...])", True),
    "AlteryxSample": ToolInfo(
        "Sample", "transform", "df.head(n) / df.sample(n)", True
    ),
    "Sample": ToolInfo("Sample", "transform", "df.head(n) / df.sample(n)", True),
    "AlteryxCrossTab": ToolInfo(
        "Cross Tab",
        "transform",
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        True,
    ),
    "CrossTab": ToolInfo(
        "Cross Tab",
        "transform",
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        True,
    ),
    "AlteryxTranspose": ToolInfo(
        "Transpose",
        "transform",
        "df.melt(id_vars=[...], var_name=..., value_name=...)",
        True,
    ),
    "Transpose": ToolInfo(
        "Transpose",
        "transform",
        "df.melt(id_vars=[...], var_name=..., value_name=...)",
        True,
    ),
    "Unique": ToolInfo("Unique", "transform", "df.drop_duplicates(subset=[...])", True),
    "RecordID": ToolInfo(
        "Record ID",
        "transform",
        "df = df.reset_index(drop=True); df['RecordID'] = df.index + 1",
        True,
    ),
    "CountRecords": ToolInfo("Count Records", "transform", "len(df)", True),
    "DateTime": ToolInfo(
        "Date/Time", "transform", "pd.to_datetime(df[...], format=...)", True
    ),
    "DataCleansing": ToolInfo(
        "Data Cleansing",
        "transform",
        "df[...].str.strip() / df[...].fillna(...)",
        True,
    ),
    "FindReplace": ToolInfo(
        "Find & Replace", "transform", "df[...].str.replace(..., ...)", True
    ),
    "GenerateRows": ToolInfo(
        "Generate Rows", "transform", "pd.DataFrame(range(...))", True
    ),
    "DynamicRename": ToolInfo(
        "Dynamic Rename",
        "transform",
        "# TODO: dynamic column rename — df.rename(columns=mapper_func)",
        False,
    ),
    "AlteryxFuzzyMatch": ToolInfo(
        "Fuzzy Match",
        "transform",
        "# TODO: fuzzy matching — consider thefuzz / rapidfuzz",
        False,
    ),
    "Tile": ToolInfo(
        "Tile", "transform", "# TODO: quantile binning — pd.qcut(df[...], q=...)", False
    ),
    "Random": ToolInfo(
        "Random Sample",
        "transform",
        "# TODO: random sample — df.sample(frac=...)",
        False,
    ),
    "RunCommand": ToolInfo(
        "Run Command",
        "transform",
        "# TODO: subprocess.run([...], check=True)",
        False,
    ),
    "ToolContainer": ToolInfo(
        "Container", "unknown", "# Container — groups tools, no Python equivalent", True
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

SCAFFOLD_INPUT_SEGMENTS = frozenset({"DbFileInput", "InputData", "TextInput"})
SCAFFOLD_OUTPUT_SEGMENTS = frozenset({"DbFileOutput", "OutputData"})
SCAFFOLD_FILTER_SEGMENTS = FILTER_SEGMENTS
SCAFFOLD_SELECT_SEGMENTS = SELECT_SEGMENTS
SCAFFOLD_FORMULA_SEGMENTS = FORMULA_SEGMENTS - {"MultiFieldFormula"}
SCAFFOLD_JOIN_SEGMENTS = JOIN_TOOL_SEGMENTS
SCAFFOLD_UNION_SEGMENTS = UNION_SEGMENTS | APPEND_SEGMENTS
SCAFFOLD_SUMMARIZE_SEGMENTS = frozenset({"AlteryxSummarize", "Summarize"})
SCAFFOLD_SORT_SEGMENTS = frozenset({"AlteryxSort", "Sort"})
SCAFFOLD_SAMPLE_SEGMENTS = frozenset({"AlteryxSample", "Sample"})
SCAFFOLD_UNIQUE_SEGMENTS = frozenset({"Unique"})


def tool_segment(tool_type: str) -> str:
    return tool_type.split(".")[-1]


def classify_tool(tool_type: str) -> tuple[str, ToolCategory]:
    """Return (display_name, category) for a plugin string."""
    segment = tool_segment(tool_type)
    if info := TOOL_REGISTRY.get(segment):
        return info.display_name, info.category
    name = segment.replace("_", " ").replace("-", " ")
    return name, "unknown"


def python_hint_for(tool_type: str) -> tuple[str, bool]:
    """Return (python_hint, supported) for a plugin string."""
    if info := TOOL_REGISTRY.get(tool_segment(tool_type)):
        return info.python_hint, info.python_supported
    return UNSUPPORTED_PYTHON_HINT, False
