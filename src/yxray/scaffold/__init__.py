"""Alteryx → Python scaffold generator.

Public API for the scaffold package; the implementation lives in the
private modules behind it (one module per tool domain, joined by
_registry, assembled by _assemble). External callers import from here
only — `from yxray.scaffold import scaffold` works as it always has.
"""

from yxray.scaffold._assemble import (
    ScaffoldBlock,
    node_code_snippets,
    scaffold,
    scaffold_simple,
    scaffold_simple_blocks,
)

__all__ = [
    "ScaffoldBlock",
    "node_code_snippets",
    "scaffold",
    "scaffold_simple",
    "scaffold_simple_blocks",
]
