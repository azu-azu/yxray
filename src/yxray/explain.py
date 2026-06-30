"""Alteryx → Python hint engine.

Takes a WorkflowDoc and returns a topologically-sorted list of ExplainStep
objects, each describing the Alteryx tool and its nearest Python/pandas
equivalent.

Design: calls summarize() for topo-sort + descriptions, then attaches a
python_hint by looking up the raw tool_type segment from doc.nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yxray.models.workflow import WorkflowDoc
from yxray.summarizer import summarize

__all__ = ["ExplainStep", "explain"]

# ---------------------------------------------------------------------------
# Python hint registry
# segment (last dot-segment of tool_type) → (hint, is_supported)
# ---------------------------------------------------------------------------

_HINTS: dict[str, tuple[str, bool]] = {
    # Input
    "DbFileInput": ("pd.read_csv(...) / pd.read_excel(...)", True),
    "InputData": ("pd.read_csv(...) / pd.read_excel(...)", True),
    "TextInput": ("pd.DataFrame({...})", True),
    "DynamicInput": (
        "# TODO: loop over files — pd.concat([pd.read_csv(f) for f in files])",
        False,
    ),
    # Output
    "DbFileOutput": ("df.to_csv(...) / df.to_excel(..., index=False)", True),
    "OutputData": ("df.to_csv(...) / df.to_excel(..., index=False)", True),
    "BrowseV2": ("# Browse — no output step needed in Python", True),
    "Browse": ("# Browse — no output step needed in Python", True),
    # Core transforms
    "AlteryxFilter": ("df = df[<condition>]", True),
    "Filter": ("df = df[<condition>]", True),
    "AlteryxSelect": ("df = df[[...]].rename(columns={...})", True),
    "Select": ("df = df[[...]].rename(columns={...})", True),
    "AlteryxFormula": ("df = df.assign(<field>=<expr>)", True),
    "Formula": ("df = df.assign(<field>=<expr>)", True),
    "AlteryxJoin": ("pd.merge(left, right, on=..., how='inner')", True),
    "Join": ("pd.merge(left, right, on=..., how='inner')", True),
    "AlteryxUnion": ("pd.concat([df1, df2], ignore_index=True)", True),
    "Union": ("pd.concat([df1, df2], ignore_index=True)", True),
    "AlteryxAppend": ("pd.concat([left, right], ignore_index=True)", True),
    "Append": ("pd.concat([left, right], ignore_index=True)", True),
    "AlteryxSummarize": ("df.groupby([...]).agg({...})", True),
    "Summarize": ("df.groupby([...]).agg({...})", True),
    "AlteryxSort": ("df.sort_values([...])", True),
    "Sort": ("df.sort_values([...])", True),
    "AlteryxSample": ("df.head(n) / df.sample(n)", True),
    "Sample": ("df.head(n) / df.sample(n)", True),
    "AlteryxCrossTab": (
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        True,
    ),
    "CrossTab": (
        "df.pivot_table(index=..., columns=..., values=..., aggfunc=...)",
        True,
    ),
    "AlteryxTranspose": (
        "df.melt(id_vars=[...], var_name=..., value_name=...)",
        True,
    ),
    "Transpose": ("df.melt(id_vars=[...], var_name=..., value_name=...)", True),
    "Unique": ("df.drop_duplicates(subset=[...])", True),
    "RecordID": (
        "df = df.reset_index(drop=True); df['RecordID'] = df.index + 1",
        True,
    ),
    "CountRecords": ("len(df)", True),
    "DateTime": ("pd.to_datetime(df[...], format=...)", True),
    "DataCleansing": ("df[...].str.strip() / df[...].fillna(...)", True),
    "FindReplace": ("df[...].str.replace(..., ...)", True),
    "GenerateRows": ("pd.DataFrame(range(...))", True),
    "ToolContainer": ("# Container — groups tools, no Python equivalent", True),
    # Harder — partial / unsupported
    "MultiFieldFormula": (
        "# TODO: apply same formula across columns — df.apply(..., axis=1)",
        False,
    ),
    "DynamicRename": (
        "# TODO: dynamic column rename — df.rename(columns=mapper_func)",
        False,
    ),
    "AlteryxFuzzyMatch": (
        "# TODO: fuzzy matching — consider thefuzz / rapidfuzz",
        False,
    ),
    "Tile": ("# TODO: quantile binning — pd.qcut(df[...], q=...)", False),
    "Random": ("# TODO: random sample — df.sample(frac=...)", False),
    "RunCommand": ("# TODO: subprocess.run([...], check=True)", False),
}

_UNSUPPORTED_HINT = "# TODO: no direct pandas equivalent — review manually"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExplainStep:
    tool_id: int
    short_type: str
    category: str  # "input" | "transform" | "output" | "unknown"
    description: str
    python_hint: str
    supported: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "short_type": self.short_type,
            "category": self.category,
            "description": self.description,
            "python_hint": self.python_hint,
            "supported": self.supported,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain(doc: WorkflowDoc) -> list[ExplainStep]:
    """Return a topologically-sorted list of ExplainStep for a workflow.

    Each step carries the tool description from summarize() plus a
    python_hint string showing the nearest pandas/Python equivalent.
    """
    node_map = {n.tool_id: n for n in doc.nodes}
    steps = summarize(doc)
    result: list[ExplainStep] = []
    for step in steps:
        node = node_map.get(step.tool_id)  # type: ignore[call-overload]
        segment = node.tool_type.split(".")[-1] if node else ""
        hint, supported = _HINTS.get(segment, (_UNSUPPORTED_HINT, False))
        result.append(
            ExplainStep(
                tool_id=step.tool_id,
                short_type=step.short_type,
                category=step.category,
                description=step.description,
                python_hint=hint,
                supported=supported,
            )
        )
    return result
