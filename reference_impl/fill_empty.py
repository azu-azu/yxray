"""Alteryx Formula の「NULL/空文字を埋める」式のヘルパー参照実装。

yxray の scaffold が生成する `fill_empty(series, value)` 呼び出しの定義。
生成コードには埋め込まれないため、このファイルをプロジェクトへコピーして使う。

対応する Alteryx 式（scaffold が自動でこの形に落とす）:

    IF IsEmpty([col]) THEN <value> ELSE [col] ENDIF
    IIF(IsEmpty([col]), <value>, [col])

`IsNull()` 版（NULL のみ。空文字は埋めない）にヘルパーは要らない —
pandas 組み込みの `series.fillna(value)` がそのまま等価なので、scaffold は
そちらを生成する。**IsNull と IsEmpty の使い分けは Alteryx 側の記述をその
まま反映する**（どちらか一方に寄せる判断はレビューする人間の責任範囲 —
`docs/alteryx-pandas-differences.md` の 16章を参照）。

## なぜ np.where ではないのか

`np.where()` は ndarray を返すため、代入先の列は元の dtype を失う。
実測（pandas 2.3.3 / 3.0.5）:

| 元の dtype | `np.where` 後 | `mask` 後 |
|---|---|---|
| `Int64`    | `float64`          | `Int64`    |
| `string`   | `object` / `str`   | `string`   |
| `category` | `object` / `str`   | `category` |
| `datetime64` | `object`（2.x）  | `datetime64` |

欠損値補充はまさに「NULL を含む列」に対する操作なので、この差がそのまま
後段の型チェック・golden 突合に出る。条件分岐で新しい値を組み立てる
（両分岐とも別の値になる）式は今まで通り `np.where` / `np.select`。

## なぜ df.loc[mask, col] = value ではないのか

振る舞いは `Series.mask()` と完全に同一（pandas 2.3.3 / 3.0.5 の
Int64 / int64 / string / object / datetime64 / category で値・dtype とも
一致を確認）。Series を返す形にしたのは次の2点のため:

1. Alteryx Formula は既存列の上書きだけでなく**新規フィールドの作成**もできる
   （`[新列] = IF IsEmpty([既存列]) THEN ... ENDIF`）。`df.loc[mask, col]` は
   代入先の列が既に存在することを前提にするので、新規列だと使えない。
2. scaffold の生成規則「1 FormulaField = 1行の `df[...] = <式>`」を保てる。
   in-place 版だと1フィールドが2行（列の作成 + マスク代入）になり、
   Alteryx の式との1対1対応が崩れる。

対象が式（`IF IsEmpty(Trim([col])) ...`）の場合に**評価が1回で済む**のも
関数形の利点 — 素の pandas で書くと同じ式が3回出てくる。
"""

from __future__ import annotations

import pandas as pd


def fill_empty(series: pd.Series, value: object) -> pd.Series:
    """NULL または空文字の要素を value で置き換えた Series を返す。

    Alteryx の `IsEmpty()` は NULL と `""` の両方を「空」と判定する
    （空白のみの `"   "` は空ではない — `Trim()` を挟むかどうかは
    Alteryx 側の記述次第で、このヘルパーは何も足さない）。

    value には Series も渡せる（`IF IsEmpty([A]) THEN [B] ELSE [A] ENDIF`）。
    その場合は index で整列される。

    dtype は保たれる。value が列の dtype に収まらない場合（`Int64` の列に
    `"N/A"` を入れる等）は **TypeError で落ちる** — 黙って別の型になるより
    翻訳ミスとして見えた方がよい。`np.where` 版は同じ入力で
    `['1.0', '2.0', 'N/A']`（整数が float 経由で文字列化）を静かに返す。
    """
    # .eq("") は数値・日付・category 列でも例外を出さず全 False を返すので、
    # 列の型を知らないまま適用できる。nullable dtype（Int64 / string）では
    # NULL 位置の .eq("") が <NA> になるが、その位置は .isna() が True に
    # するため OR の結果は True で確定する（Kleene 論理: True | NA == True）。
    return series.mask(series.isna() | series.eq(""), value)
