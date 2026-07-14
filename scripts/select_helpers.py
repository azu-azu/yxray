"""Alteryx Select ツール用ヘルパーの参照実装。

yxray の scaffold が生成する apply_select_edits(df, [...]) 呼び出しの定義。
生成コードには埋め込まれないため、このファイルをプロジェクトへコピーして使う。

- *Unknown selected=False: 明示的に selected な列だけを残す
- それ以外: deselected な列を drop する（存在しない列は無視 —
  Alteryx XML は stale な列リストを持ちがちなので KeyError にしない）
- rename は selected な列にのみ適用する
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SelectColumnEdit:
    name: str
    new_name: str | None = None
    selected: bool = True


def apply_select_edits(
        df: pd.DataFrame,
        columns: list[SelectColumnEdit],
) -> pd.DataFrame:
    wildcard = next((c for c in columns if c.name == "*Unknown"), None)
    explicit = [c for c in columns if c.name != "*Unknown"]
    if wildcard is not None and not wildcard.selected:
        keep = [
            c.name for c in explicit
            if c.selected and c.name in df.columns
        ]
        df = df[keep]
    else:
        drop = {c.name for c in explicit if not c.selected} & set(df.columns)
        df = df.drop(columns=drop)
    rename_map = {
        c.name: c.new_name
        for c in explicit
        if c.selected and c.new_name and c.name in df.columns
    }
    return df.rename(columns=rename_map)
