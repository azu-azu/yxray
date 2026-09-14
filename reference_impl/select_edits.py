"""Reference implementation of the Alteryx Select tool helper.

Defines the apply_select_edits(df, [...]) call that yxray's scaffold
generates. The definition is not embedded in the generated code, so copy
this file into the target project.

- *Unknown selected=False: keep only the explicitly selected columns
- otherwise: drop the deselected columns (columns that are absent are
  ignored — Alteryx XML tends to carry a stale column list, so this must
  not raise KeyError)
- type: convert an Alteryx type name (V_WString / Int32 / Double / Date
  etc.) to a pandas dtype. Values that fail to convert become null, the
  same as an Alteryx Conversion Error (errors="coerce"). pandas nulls them
  silently, so a column whose conversion added nulls is reported through
  logger.warning with the count
- rename applies only to selected columns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

_STRING_TYPES = {"String", "WString", "V_String", "V_WString"}
# pandas' nullable integer dtype names almost match Alteryx's type names
# (only Byte differs: Alteryx's is unsigned 8-bit, so UInt8)
# The values are pinned with Literal: as a plain dict[str, str] the astype()
# call receives a str, which does not match the type stubs' overload that
# takes a dtype name as a Literal.
_IntDtypeName = Literal["UInt8", "Int16", "Int32", "Int64"]
_INT_DTYPES: dict[str, _IntDtypeName] = {
    "Byte": "UInt8",
    "Int16": "Int16",
    "Int32": "Int32",
    "Int64": "Int64",
}
# FixedDecimal is fixed-point in Alteryx. Dropping it to float64 can
# introduce error in monetary calculations — consider decimal.Decimal where
# precision matters.
_FLOAT_TYPES = {"Double", "Float", "FixedDecimal"}


@dataclass(frozen=True)
class SelectColumnEdit:
    name: str
    new_name: str | None = None
    selected: bool = True
    type: str | None = None  # Alteryx type name; set only on a column with a type change


def _convert_series(series: pd.Series, alteryx_type: str) -> pd.Series | None:
    """Convert series to the pandas dtype matching an Alteryx type name.

    Unsupported types (Blob / SpatialObj etc.) return None so the caller
    can skip them and warn.
    """
    if alteryx_type in _STRING_TYPES:
        # When the source was numeric, astype("string") uses Python's own
        # float repr (full precision, and a ".0" even on integral values).
        # Alteryx drops the fractional part of an integral value ("1.0" ->
        # "1") — to_display_string.py already implements that formatting
        # rule, but it is not called here. The reason is not the
        # don't-automate policy itself (chapter 20, "no automatic
        # application"): this is the generic type-conversion path, so
        # non-numeric types (Date/Bool etc.) come through it too, and
        # swapping it in wholesale could break those cases. Where the
        # source is known to be numeric, consider switching to
        # to_display_string(). Note that to_display_string() is itself not
        # yet verified against Alteryx golden output (see that file's
        # docstring).
        return series.astype("string")
    if alteryx_type in _INT_DTYPES:
        # round() is required: astype to a nullable Int fails with "cannot
        # safely cast" on a float carrying a fractional part.
        #
        # WARNING: the rounding MODE is not confirmed against Alteryx.
        # Series.round() is round-half-to-even (banker's rounding), so a
        # value at exactly .5 whose integer part is even rounds DOWN:
        # 0.5 -> 0 and 2.5 -> 2, where round-half-away-from-zero gives 1
        # and 3. Ties whose integer part is odd (1.5 -> 2, 3.5 -> 4)
        # agree under both modes, so they cannot tell the two apart.
        # Negative values split three ways rather than two — half-to-even
        # (-0.5 -> 0, -1.5 -> -2), half-up toward +inf via floor(x + 0.5)
        # (-0.5 -> 0, -1.5 -> -1) and half-away-from-zero (-0.5 -> -1,
        # -1.5 -> -2) all differ — so do not port the floor(x + 0.5)
        # rewrite from docs/distance-direction-pending.md here: that one is
        # sound only because a compass bearing is never negative.
        # Diff this column against golden output before trusting it; see
        # the unverified-items checklist in
        # docs/alteryx-pandas-differences.md.
        num = pd.to_numeric(series, errors="coerce")
        return num.round().astype(_INT_DTYPES[alteryx_type])
    if alteryx_type in _FLOAT_TYPES:
        return pd.to_numeric(series, errors="coerce")
    if alteryx_type == "Bool":
        # Alteryx-compatible: a non-zero number → True. Also picks up
        # "True"/"False" strings that came from a CSV.
        num = pd.to_numeric(series, errors="coerce")
        text = series.astype("string").str.strip().str.lower()
        result = num.ne(0).mask(num.isna())
        result = result.mask(num.isna() & text.eq("true"), True)
        result = result.mask(num.isna() & text.eq("false"), False)
        return result.astype("boolean")
    if alteryx_type == "Date":
        # An Alteryx Date carries no time part, so normalize to 00:00:00
        return pd.to_datetime(series, errors="coerce").dt.normalize()
    if alteryx_type == "DateTime":
        return pd.to_datetime(series, errors="coerce")
    if alteryx_type == "Time":
        # pandas has no time-of-day dtype, so approximate with timedelta
        return pd.to_timedelta(series, errors="coerce")
    return None


def _apply_type_edits(
    df: pd.DataFrame,
    edits: list[SelectColumnEdit],
) -> pd.DataFrame:
    updates: dict[str, pd.Series] = {}
    for edit in edits:
        if not edit.selected or not edit.type or edit.name not in df.columns:
            continue
        converted = _convert_series(df[edit.name], edit.type)
        if converted is None:
            logger.warning(
                "apply_select_edits: unsupported Alteryx type %r (column %r) — skipping conversion",
                edit.type,
                edit.name,
            )
            continue
        added_nulls = int(converted.isna().sum()) - int(df[edit.name].isna().sum())
        if added_nulls > 0:
            logger.warning(
                "apply_select_edits: the %s conversion of column %r nulled %d value(s)"
                " (equivalent to an Alteryx Conversion Error)",
                edit.type,
                edit.name,
                added_nulls,
            )
        updates[edit.name] = converted
    # assign returns a new DataFrame with the existing columns replaced, so
    # the caller's df is left untouched and the column order is preserved
    return df.assign(**updates) if updates else df


def apply_select_edits(
    df: pd.DataFrame,
    columns: list[SelectColumnEdit],
) -> pd.DataFrame:
    wildcard = next((c for c in columns if c.name == "*Unknown"), None)
    explicit = [c for c in columns if c.name != "*Unknown"]
    if wildcard is not None and not wildcard.selected:
        keep = [c.name for c in explicit if c.selected and c.name in df.columns]
        df = df[keep]
    else:
        drop = {c.name for c in explicit if not c.selected} & set(df.columns)
        df = df.drop(columns=drop)
    # Type conversion runs after the drop and before the rename, because
    # edit.name is the pre-rename column name
    df = _apply_type_edits(df, explicit)
    rename_map = {
        c.name: c.new_name
        for c in explicit
        if c.selected and c.new_name and c.name in df.columns
    }
    return df.rename(columns=rename_map)
