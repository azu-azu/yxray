"""Alteryx Select ツール用ヘルパーの参照実装。

yxray の scaffold が生成する apply_select_edits(df, [...]) 呼び出しの定義。
生成コードには埋め込まれないため、このファイルをプロジェクトへコピーして使う。

- *Unknown selected=False: 明示的に selected な列だけを残す
- それ以外: deselected な列を drop する（存在しない列は無視 —
  Alteryx XML は stale な列リストを持ちがちなので KeyError にしない）
- type: Alteryx の型名（V_WString / Int32 / Double / Date など）を pandas の
  dtype へ変換する。変換に失敗した値は Alteryx の Conversion Error と同様に
  null になる（errors="coerce"）。ただし pandas は黙って null 化するため、
  変換で null が増えた列は logger.warning で件数を報告する
- rename は selected な列にのみ適用する
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

_STRING_TYPES = {"String", "WString", "V_String", "V_WString"}
# pandas の nullable 整数 dtype 名は Alteryx の型名とほぼ一致する
# （Byte のみ Alteryx では符号なし 8bit なので UInt8）
_INT_DTYPES = {"Byte": "UInt8", "Int16": "Int16", "Int32": "Int32", "Int64": "Int64"}
# FixedDecimal は本来固定小数点。float64 に落とすため金額計算では誤差が出うる —
# 精度が必要な場合は decimal.Decimal 化を検討すること
_FLOAT_TYPES = {"Double", "Float", "FixedDecimal"}


@dataclass(frozen=True)
class SelectColumnEdit:
    name: str
    new_name: str | None = None
    selected: bool = True
    type: str | None = None  # Alteryx の型名。型変更のある列にのみ設定される


def _convert_series(series: pd.Series, alteryx_type: str) -> pd.Series | None:
    """series を Alteryx 型名に対応する pandas dtype へ変換する。

    未対応の型（Blob / SpatialObj など）は None を返し、呼び出し側で
    スキップ + 警告する。
    """
    if alteryx_type in _STRING_TYPES:
        return series.astype("string")
    if alteryx_type in _INT_DTYPES:
        # round(): Alteryx の Double→Int は四捨五入。小数を含む float から
        # nullable Int への astype は "cannot safely cast" で落ちるため必須
        num = pd.to_numeric(series, errors="coerce")
        return num.round().astype(_INT_DTYPES[alteryx_type])
    if alteryx_type in _FLOAT_TYPES:
        return pd.to_numeric(series, errors="coerce")
    if alteryx_type == "Bool":
        # Alteryx 準拠: 非ゼロ数値 → True。CSV 由来の "True"/"False" 文字列も拾う
        num = pd.to_numeric(series, errors="coerce")
        text = series.astype("string").str.strip().str.lower()
        result = num.ne(0).mask(num.isna())
        result = result.mask(num.isna() & text.eq("true"), True)
        result = result.mask(num.isna() & text.eq("false"), False)
        return result.astype("boolean")
    if alteryx_type == "Date":
        # Alteryx の Date は時刻部分を持たないため 00:00:00 に正規化する
        return pd.to_datetime(series, errors="coerce").dt.normalize()
    if alteryx_type == "DateTime":
        return pd.to_datetime(series, errors="coerce")
    if alteryx_type == "Time":
        # pandas に time-of-day dtype はないため timedelta で近似する
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
                "apply_select_edits: 未対応の Alteryx 型 %r（列 %r）— 変換をスキップ",
                edit.type,
                edit.name,
            )
            continue
        added_nulls = int(converted.isna().sum()) - int(df[edit.name].isna().sum())
        if added_nulls > 0:
            logger.warning(
                "apply_select_edits: 列 %r の %s 変換で %d 件が null になった"
                "（Alteryx の Conversion Error 相当）",
                edit.name,
                edit.type,
                added_nulls,
            )
        updates[edit.name] = converted
    # assign は既存列を置き換えた新しい DataFrame を返すので、呼び出し元の
    # df を変更せず、列順も保たれる
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
    # 型変換は drop の後・rename の前（edit.name は rename 前の列名のため）
    df = _apply_type_edits(df, explicit)
    rename_map = {
        c.name: c.new_name
        for c in explicit
        if c.selected and c.new_name and c.name in df.columns
    }
    return df.rename(columns=rename_map)
