"""Alteryx 互換の「数値を文字列にするときの表記」ヘルパーの参照実装。

    1.0     → "1"
    1.5     → "1.5"
    21000.0 → "21000"

Alteryx は数値を文字列として出力する場面で、**整数相当の値の小数点以下を
省略する**。pandas の `astype("string")` は `1.0` を `"1.0"` にするので、
Double 列に文字列プレースホルダを混ぜた列（`IF IsEmpty([Floor]) THEN "-"
ELSE [Floor] ENDIF` の結果など）をそのまま出力すると Alteryx と食い違う。

**これは「値を整数型に変える」ルールではなく、文字列化するときの表記ルール**。
適用する場所は次のとおり:

    計算中の DataFrame      … 数値型のまま保つ（変換しない）
    表示・CSV 出力の直前    … Alteryx 互換の文字列表記へ整える

## scaffold は生成しない — レビュー時に人間が挿入する

`reference_impl/` の他のヘルパーと違い、これは生成コードから呼ばれない。
どの列が「表示用の文字列」になるかは Alteryx XML だけでは決まらず、
実データの型に依存するため。自動適用は事故のもとで、判断はレビューする
人間の責任範囲（`docs/alteryx-pandas-differences.md` の16章と同じ立て付け）。

なお **Alteryx 側の挙動そのものは本リポジトリの golden 突合では未検証**。
実出力で確定したら `docs/alteryx-pandas-differences.md` 20章の該当行を
消し込むこと。

## fill_empty には組み込まない

`fill_empty()` の存在理由は **dtype を保つこと**（`np.where` が ndarray を
返して `Int64` → `float64` などに壊すのを避ける）。文字列化はその逆に
dtype を意図的に捨てる操作なので、組み込むと自分の契約と矛盾する。
実際 `IF IsNull([Amount]) THEN 0 ELSE [Amount] ENDIF` のような**数値のまま
埋める補充**まで文字列になってしまう。

2つは合成して使う。順序は「文字列化 → 補充」:

    df["Floor"] = fill_empty(to_display_string(df["Floor"]), "-")

逆順（補充 → 文字列化）にすると、数値列に `"-"` を入れた時点で object 列に
なり、`1.0` が数値のまま残るため `to_display_string` の数値判定を通らない。
"""

from __future__ import annotations

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

# Int64 へ安全にキャストできる範囲。これを超える float（1e300、inf など）は
# 変換せず素の表記のまま残す。範囲外を無条件に astype("Int64") すると
# 「cannot safely cast non-equivalent float64 to int64」で落ちる。
_INT64_BOUND = 2**63


def to_display_string(series: pd.Series) -> pd.Series:
    """数値列を Alteryx 互換の表記で string dtype へ変換する。

    整数相当の値だけ小数点以下を落とす。欠損は `<NA>` のまま残るので、
    後段の `fill_empty()` がプレースホルダで埋められる。

    **数値 dtype の列にのみ表記変換を適用する。** 文字列・日付・bool の列は
    `astype("string")` するだけで中身を触らない。これは慣習ではなく構造的な
    ガードで、次の事故を型の時点で防いでいる:

    - `"001"`（コード・ID）が `"1"` になる — 文字列列は数値判定にかけない
    - `True` / `False` が `"1"` / `"0"` になる — bool は数値 dtype 扱いなので
      明示的に除外する（Alteryx の Bool→String は "True"/"False"）
    - 日付が `"1704067200000000"`（epoch 整数）になる — 日付列も対象外

    ただし CSV を `dtype=str` で読んだ数値列は文字列列なので変換されない。
    その場合は先に `pd.to_numeric()` を通すこと。
    """
    result = series.astype("string")
    if not is_numeric_dtype(series) or is_bool_dtype(series):
        return result
    numeric = pd.to_numeric(series, errors="coerce")
    whole = (
        numeric.notna() & numeric.mod(1).eq(0) & numeric.abs().lt(_INT64_BOUND)
    )
    result.loc[whole] = numeric.loc[whole].astype("Int64").astype("string")
    return result
