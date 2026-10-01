"""Discrimination tables and minimality search for Select's Double->Int conversion.

Source of truth for the figures quoted in chapter 23 of
docs/alteryx-pandas-differences.md. Those figures were hand-transcribed from
throwaway scripts three times and were wrong three times (a reversed claim
about which candidates agree on positives, a pool described as 91 points while
the code used a gappy 65, and the set count that followed from it). This script
exists so the numbers come from code that can be re-run instead of from prose.

The open question it serves: `apply_select_edits()` in
reference_impl/select_edits.py reaches a nullable Int dtype via
`Series.round()` (half-to-even), but what Alteryx does is unverified on two
counts -- whether it rounds to nearest at all rather than truncating /
flooring / ceiling, and if it rounds, which tie-break it uses. Until golden
output settles it, all seven candidates below stay in play, and the question is
which input values can tell them apart.

Usage:
    python3 tools/double_to_int_candidates.py              # full report
    python3 tools/double_to_int_candidates.py --check      # assertions only
    python3 tools/double_to_int_candidates.py --markdown   # doc-ready tables

What it does (mechanical, no judgement):
    - prints the 7 candidates x 8 recommended golden values table
    - prints the 7 candidates x 4 minimal-example values table
    - searches every 1-, 2-, 3- and 4-value subset of the pool and reports how
      many separate all 7 candidates, establishing the minimum
    - asserts the conclusions chapter 23 states, so changing CANDIDATES makes
      the stale figures fail loudly instead of leaving the doc quietly wrong
    - cross-checks its own half-to-even column against what
      apply_select_edits() actually produces, so the analysis cannot drift
      from the implementation it describes

What it does not do:
    - it does not rewrite the docs. Chapter 23 is maintained by hand; this
      script is what you re-run to confirm the numbers in it (--markdown
      prints paste-ready tables)
    - it does not say what Alteryx does. That needs golden output from a real
      Alteryx run; this only says which values would reveal it
    - it does not touch the implementation. half-to-even stays until golden
      output decides
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from itertools import combinations
from math import ceil, copysign, floor
from math import trunc as _trunc

# The candidate set. Keys are the names chapter 23 uses. Adding or removing an
# entry here invalidates the DOCUMENTED_* figures below, which is the point:
# the assertions will fail and point at the doc that needs updating.
#
# Each is implemented in the standard library only, so this script runs without
# pandas. All seven were verified to agree with independent implementations
# (pandas Series.round, numpy floor/ceil/trunc, decimal's ROUND_HALF_UP /
# ROUND_HALF_DOWN / ROUND_HALF_EVEN) across the whole pool.
CANDIDATES: dict[str, Callable[[float], int]] = {
    # nearest, differing only in how a .5 tie is broken
    "half-to-even": lambda v: int(round(v)),
    "ties → +∞": lambda v: int(floor(v + 0.5)),
    "half-away": lambda v: int(copysign(floor(abs(v) + 0.5), v)),
    "half-to-zero": lambda v: int(copysign(ceil(abs(v) - 0.5), v)),
    # directed, never looking at the nearest integer at all
    "trunc": lambda v: int(_trunc(v)),
    "floor": lambda v: int(floor(v)),
    "ceil": lambda v: int(ceil(v)),
}

# What apply_select_edits() does today. Not a claim about Alteryx.
CURRENT_IMPLEMENTATION = "half-to-even"

# The set recommended for golden comparison. Deliberately redundant rather than
# minimal: it spans sign, tie/non-tie and integer-part parity, so a mismatch
# localizes the cause instead of only reporting "not half-to-even".
RECOMMENDED_GOLDEN_VALUES: tuple[float, ...] = (
    -2.5,
    -1.5,
    -0.7,
    -0.5,
    0.5,
    0.7,
    1.5,
    2.5,
)

# One minimal separating set, quoted in chapter 23 as an example. Not unique --
# the search below counts how many exist.
MINIMAL_EXAMPLE_VALUES: tuple[float, ...] = (-1.5, -0.7, 0.5, 0.7)

# Built from integer tenths rather than a float accumulator so the endpoints are
# exact and the count is obvious: range(-45, 46) is 91 values, -4.5 .. 4.5.
# Every x.5 tie in range is exactly representable as a double, so tie behavior
# is not at the mercy of representation error.
SEARCH_POOL: tuple[float, ...] = tuple(i / 10 for i in range(-45, 46))

MAX_SUBSET_SIZE = 4

# Figures quoted in docs/alteryx-pandas-differences.md chapter 23. Asserted
# below -- if a candidate is added or removed, or the pool changes, these stop
# matching and the doc gets fixed with the code instead of drifting from it.
DOCUMENTED_CANDIDATE_COUNT = 7
DOCUMENTED_POOL_SIZE = 91
DOCUMENTED_MINIMUM_SUBSET_SIZE = 4
DOCUMENTED_SEPARATING_SETS_AT_MINIMUM = 6336


def outputs(values: Sequence[float]) -> dict[str, tuple[int, ...]]:
    """Each candidate's output row over values."""
    return {name: tuple(fn(v) for v in values) for name, fn in CANDIDATES.items()}


def separates_all(values: Sequence[float]) -> bool:
    """True when every candidate produces a distinct row over values."""
    return len(set(outputs(values).values())) == len(CANDIDATES)


def _pair_masks(pool: Sequence[float]) -> tuple[list[int], int]:
    """For each pool value, a bitmask of which candidate PAIRS it separates.

    A value set separates all candidates exactly when every pair of candidates
    differs on at least one of its values, so the search reduces to covering
    all C(n, 2) pairs. ORing a few ints is much cheaper than rebuilding and
    comparing output rows for all 2.6M four-value subsets.
    """
    fns = list(CANDIDATES.values())
    pairs = list(combinations(range(len(fns)), 2))
    masks = []
    for v in pool:
        got = [fn(v) for fn in fns]
        mask = 0
        for bit, (i, j) in enumerate(pairs):
            if got[i] != got[j]:
                mask |= 1 << bit
        masks.append(mask)
    return masks, (1 << len(pairs)) - 1


def minimality_search(
    pool: Sequence[float], max_k: int = MAX_SUBSET_SIZE
) -> dict[int, tuple[int, tuple[float, ...] | None]]:
    """For k in 1..max_k, count the k-subsets of pool that separate all candidates.

    Returns {k: (count, first_example_or_None)}. Stops early once a k yields
    any separating set, since that k is the minimum.
    """
    masks, full = _pair_masks(pool)
    indices = range(len(pool))
    results: dict[int, tuple[int, tuple[float, ...] | None]] = {}
    for k in range(1, max_k + 1):
        count = 0
        first: tuple[float, ...] | None = None
        for combo in combinations(indices, k):
            covered = 0
            for i in combo:
                covered |= masks[i]
            if covered == full:
                count += 1
                if first is None:
                    first = tuple(pool[i] for i in combo)
        results[k] = (count, first)
        if count:
            break
    return results


def _fmt(values: Iterable[float]) -> list[str]:
    return [f"{v:g}" for v in values]


def render_table(
    values: Sequence[float], markdown: bool = False, transpose: bool = False
) -> str:
    """The candidates-by-values table, as plain text or markdown.

    Both orientations exist because chapter 23 uses both: its seven-candidate
    table puts the inputs down the side (transpose=True), its minimal-set table
    puts the candidates down the side. --markdown is meant to be paste-ready for
    either, so it has to match. The bold markers in chapter 23's table are
    editorial emphasis on the cells that discriminate and are added by hand;
    this prints the data only.
    """
    rows = outputs(values)
    if transpose:
        head = ["入力" if markdown else "input", *rows.keys()]
        body = [
            [f"{v:g}", *[str(row[i]) for row in rows.values()]]
            for i, v in enumerate(values)
        ]
    else:
        head = ["方式" if markdown else "candidate", *_fmt(values)]
        body = [[name, *[str(n) for n in row]] for name, row in rows.items()]
    if markdown:
        sep = ["---"] * len(head)
        return "\n".join(
            "| " + " | ".join(r) + " |" for r in [head, sep, *body]
        )
    width = max(len(r[0]) for r in [head, *body])
    cells = max(len(c) for r in [head, *body] for c in r[1:]) + 2
    return "\n".join(
        r[0].ljust(width) + "".join(c.rjust(cells) for c in r[1:])
        for r in [head, *body]
    )


def check_against_implementation() -> str:
    """Confirm the half-to-even column matches apply_select_edits() for real.

    Keeps this analysis honest about the code it describes: if someone changes
    the conversion in reference_impl/select_edits.py, the column this script
    labels as the current implementation stops matching and says so.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import importlib

    import pandas as pd

    mod = importlib.import_module("reference_impl.select_edits")
    frame = pd.DataFrame({"v": list(RECOMMENDED_GOLDEN_VALUES)})
    converted = mod.apply_select_edits(
        frame, [mod.SelectColumnEdit("v", type="Int32")]
    )["v"]
    got = [int(n) for n in converted]
    expected = list(outputs(RECOMMENDED_GOLDEN_VALUES)[CURRENT_IMPLEMENTATION])
    if got != expected:
        raise AssertionError(
            "apply_select_edits() no longer matches "
            f"{CURRENT_IMPLEMENTATION}: got {got}, expected {expected}. "
            "Either the implementation changed (update CURRENT_IMPLEMENTATION "
            "and chapter 23) or this script's candidate is wrong."
        )
    return f"apply_select_edits() == {CURRENT_IMPLEMENTATION}: {got}"


def assert_documented_figures() -> list[str]:
    """Assert every conclusion chapter 23 states. Raises on the first failure."""
    notes = []

    assert len(CANDIDATES) == DOCUMENTED_CANDIDATE_COUNT, (
        f"CANDIDATES has {len(CANDIDATES)} entries but chapter 23 and the "
        f"DOCUMENTED_* figures assume {DOCUMENTED_CANDIDATE_COUNT}. Re-run this "
        "script and update both."
    )
    notes.append(f"candidates: {len(CANDIDATES)}")

    assert len(SEARCH_POOL) == DOCUMENTED_POOL_SIZE, (
        f"pool is {len(SEARCH_POOL)} values, chapter 23 says "
        f"{DOCUMENTED_POOL_SIZE}"
    )
    assert SEARCH_POOL[0] == -4.5 and SEARCH_POOL[-1] == 4.5, (
        "chapter 23 describes the pool as -4.5..4.5; it is "
        f"{SEARCH_POOL[0]}..{SEARCH_POOL[-1]}"
    )
    notes.append(f"pool: {len(SEARCH_POOL)} values, {SEARCH_POOL[0]}..{SEARCH_POOL[-1]}")

    assert separates_all(RECOMMENDED_GOLDEN_VALUES), (
        "the recommended golden set no longer separates all candidates"
    )
    notes.append(
        f"recommended {len(RECOMMENDED_GOLDEN_VALUES)}-value set separates all "
        f"{len(CANDIDATES)}"
    )

    assert separates_all(MINIMAL_EXAMPLE_VALUES), (
        "the minimal example set no longer separates all candidates"
    )
    assert len(MINIMAL_EXAMPLE_VALUES) == DOCUMENTED_MINIMUM_SUBSET_SIZE, (
        "the minimal example is no longer the documented minimum size"
    )
    notes.append(
        f"minimal example {', '.join(_fmt(MINIMAL_EXAMPLE_VALUES))} separates "
        f"all {len(CANDIDATES)}"
    )

    results = minimality_search(SEARCH_POOL)
    found = sorted(k for k, (count, _) in results.items() if count)
    assert found, f"no subset up to size {MAX_SUBSET_SIZE} separates all candidates"
    minimum = found[0]
    assert minimum == DOCUMENTED_MINIMUM_SUBSET_SIZE, (
        f"minimum separating subset size is {minimum}, chapter 23 says "
        f"{DOCUMENTED_MINIMUM_SUBSET_SIZE}"
    )
    for k in range(1, minimum):
        assert results[k][0] == 0, (
            f"a {k}-value subset separates all candidates, so the documented "
            f"minimum of {DOCUMENTED_MINIMUM_SUBSET_SIZE} is wrong"
        )
    count = results[minimum][0]
    assert count == DOCUMENTED_SEPARATING_SETS_AT_MINIMUM, (
        f"{count} separating sets of size {minimum}, chapter 23 says "
        f"{DOCUMENTED_SEPARATING_SETS_AT_MINIMUM}"
    )
    notes.append(f"minimum subset size: {minimum} ({count} such sets)")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the assertions only, print one line per conclusion",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="print the tables as markdown, ready to paste into chapter 23",
    )
    args = parser.parse_args()

    if args.check:
        for note in assert_documented_figures():
            print(f"OK  {note}")
        print(f"OK  {check_against_implementation()}")
        return 0

    md = args.markdown
    print(f"Recommended golden set ({len(RECOMMENDED_GOLDEN_VALUES)} values)")
    print(render_table(RECOMMENDED_GOLDEN_VALUES, markdown=md, transpose=True))
    print()
    print(f"Minimal separating example ({len(MINIMAL_EXAMPLE_VALUES)} values)")
    print(render_table(MINIMAL_EXAMPLE_VALUES, markdown=md))
    print()
    print(
        f"Minimality search over {len(SEARCH_POOL)} values "
        f"({SEARCH_POOL[0]}..{SEARCH_POOL[-1]} step 0.1)"
    )
    for k, (count, example) in sorted(minimality_search(SEARCH_POOL).items()):
        tail = f"  e.g. {', '.join(_fmt(example))}" if example else ""
        print(f"  k={k}: {count} separating sets{tail}")
    print()
    for note in assert_documented_figures():
        print(f"OK  {note}")
    print(f"OK  {check_against_implementation()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # piped into head/less; nothing wrong, just stop quietly
        raise SystemExit(0) from None
