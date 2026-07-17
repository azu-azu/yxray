"""Segment → generator dispatch table for the scaffold.

The single place in the package that imports the per-tool generator
modules; _assemble dispatches through GENERATORS by segment alone. Every
generator — Input/Output included — takes one ToolContext, so there are
no per-tool special cases left in assembly.
"""

from __future__ import annotations

from collections.abc import Callable

from yxray.scaffold._aggregate import gen_summarize
from yxray.scaffold._combine import gen_appendfields, gen_join, gen_union
from yxray.scaffold._common import GeneratedCode, ToolContext
from yxray.scaffold._filter import gen_filter
from yxray.scaffold._findreplace import gen_findreplace
from yxray.scaffold._io import gen_input, gen_output
from yxray.scaffold._select import gen_select
from yxray.scaffold._source import gen_browse, gen_text_input
from yxray.scaffold._spatial import gen_createpoints, gen_spatialmatch
from yxray.scaffold._transform import (
    gen_formula,
    gen_recordid,
    gen_sample,
    gen_sort,
    gen_unique,
)
from yxray.tool_registry import (
    SCAFFOLD_APPENDFIELDS_SEGMENTS,
    SCAFFOLD_BROWSE_SEGMENTS,
    SCAFFOLD_CREATEPOINTS_SEGMENTS,
    SCAFFOLD_FILTER_SEGMENTS,
    SCAFFOLD_FINDREPLACE_SEGMENTS,
    SCAFFOLD_FORMULA_SEGMENTS,
    SCAFFOLD_INPUT_SEGMENTS,
    SCAFFOLD_JOIN_SEGMENTS,
    SCAFFOLD_OUTPUT_SEGMENTS,
    SCAFFOLD_RECORDID_SEGMENTS,
    SCAFFOLD_SAMPLE_SEGMENTS,
    SCAFFOLD_SELECT_SEGMENTS,
    SCAFFOLD_SORT_SEGMENTS,
    SCAFFOLD_SPATIALMATCH_SEGMENTS,
    SCAFFOLD_SUMMARIZE_SEGMENTS,
    SCAFFOLD_TEXTINPUT_SEGMENTS,
    SCAFFOLD_UNION_SEGMENTS,
    SCAFFOLD_UNIQUE_SEGMENTS,
)

Generator = Callable[[ToolContext], GeneratedCode]

GENERATORS: dict[str, Generator] = {
    **dict.fromkeys(SCAFFOLD_INPUT_SEGMENTS, gen_input),
    **dict.fromkeys(SCAFFOLD_OUTPUT_SEGMENTS, gen_output),
    **dict.fromkeys(SCAFFOLD_BROWSE_SEGMENTS, gen_browse),
    **dict.fromkeys(SCAFFOLD_FILTER_SEGMENTS, gen_filter),
    **dict.fromkeys(SCAFFOLD_SELECT_SEGMENTS, gen_select),
    **dict.fromkeys(SCAFFOLD_FORMULA_SEGMENTS, gen_formula),
    **dict.fromkeys(SCAFFOLD_JOIN_SEGMENTS, gen_join),
    **dict.fromkeys(SCAFFOLD_UNION_SEGMENTS, gen_union),
    **dict.fromkeys(SCAFFOLD_SUMMARIZE_SEGMENTS, gen_summarize),
    **dict.fromkeys(SCAFFOLD_SORT_SEGMENTS, gen_sort),
    **dict.fromkeys(SCAFFOLD_SAMPLE_SEGMENTS, gen_sample),
    **dict.fromkeys(SCAFFOLD_UNIQUE_SEGMENTS, gen_unique),
    **dict.fromkeys(SCAFFOLD_RECORDID_SEGMENTS, gen_recordid),
    **dict.fromkeys(SCAFFOLD_TEXTINPUT_SEGMENTS, gen_text_input),
    **dict.fromkeys(SCAFFOLD_FINDREPLACE_SEGMENTS, gen_findreplace),
    **dict.fromkeys(SCAFFOLD_APPENDFIELDS_SEGMENTS, gen_appendfields),
    **dict.fromkeys(SCAFFOLD_CREATEPOINTS_SEGMENTS, gen_createpoints),
    **dict.fromkeys(SCAFFOLD_SPATIALMATCH_SEGMENTS, gen_spatialmatch),
}

# Segments whose scaffold snippet is self-contained enough to show as a
# single node's "python hint" (used by the inspect report's right pane).
# Excludes Input/Output (depend on file paths, which the panel already shows
# separately) and Text Input (would enumerate every data row — the panel
# shows the data).
DETAIL_HINT_SEGMENTS = (
    frozenset(GENERATORS)
    - SCAFFOLD_TEXTINPUT_SEGMENTS
    - SCAFFOLD_INPUT_SEGMENTS
    - SCAFFOLD_OUTPUT_SEGMENTS
)
