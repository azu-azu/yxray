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

逆順（補充 → 文字列化）でも結果は同じになる（object 列の中の float も
セル単位で拾うため）。それでも文字列化を先に置くのは、`fill_empty()` が
dtype を保つヘルパーで、`Int64` の列に `"-"` を入れると **TypeError で
落ちる**ため。先に文字列にしておけばプレースホルダは常に入る。
"""

from __future__ import annotations

import re
from decimal import Decimal
from numbers import Real

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_complex_dtype, is_numeric_dtype

# Int64 へ安全にキャストできる範囲。これを超える float（1e300、inf など）は
# 変換せず素の表記のまま残す。範囲外を無条件に astype("Int64") すると
# 「cannot safely cast non-equivalent float64 to int64」で落ちる。
_INT64_BOUND = 2**63

# すでに文字列になっている値のうち、「正準な10進表記で小数部がゼロ」のものだけ
# 小数部を落とす（"1.0" → "1"）。列ごと pd.to_numeric() にかけるのと違い、
# 情報を捨てないのがポイント:
#
#   "001"     先頭ゼロが有意なコードかもしれないので触らない（整数部は
#             [1-9]\d* か単独の 0 のみ許可 — "001.0" も対象外）
#   "B1"      数値でないテキストは残る（to_numeric なら NaN に化ける）
#   "1.5"     小数部がゼロでないので残る
#   "1e5"     指数表記は対象外（表記を変えると別物に見えるため）
#   "-0.0"    符号付きゼロは触らない（"-0" を作らない）
#   " 1.0"    前後の空白は正準ではないので残す — Trim は呼び出し側の判断
_ZERO_FRACTION_TEXT = re.compile(r"^(-?[1-9]\d*|0)\.0+$")


def _is_real_number(value: object) -> bool:
    """セルの中身が本物の実数オブジェクトか（bool は数値扱いしない）。

    `Real` は int / float / numpy の数値スカラを含む。`Decimal` は `Real` に
    登録されていないので明示的に足す（FixedDecimal を精度優先で Decimal 化
    した列のため — `apply_select_edits` の注記を参照）。`bool` は `int` の
    サブクラスなので先に弾く。
    """
    if isinstance(value, (bool, np.bool_)):
        return False
    return isinstance(value, (Real, Decimal))


def to_display_string(series: pd.Series) -> pd.Series:
    """数値を Alteryx 互換の表記で string dtype へ変換する。

    整数相当の値だけ小数点以下を落とす。欠損は `<NA>` のまま残るので、
    後段の `fill_empty()` がプレースホルダで埋められる。

    **判定は列の dtype ではなく各セルの中身で行う。** 生成コードが作る列は
    object になりがちで（`np.where` の出力、プレースホルダを混ぜた列など）、
    列 dtype で足切りすると中身が本物の float でも変換されないため:

        pd.Series([1.0, 1.5, "001", "1.0", None], dtype="object")
        → ["1", "1.5", "001", "1", <NA>]

    数値として「入っている」セルだけが対象なので、次の事故は型の時点で
    起こらない — 運用ルールで避けるのではなく構造的に防いでいる:

    - `"001"`（ゼロ埋めコード）が `"1"` になる — 先頭ゼロのある表記は対象外
    - `True` / `False` が `"1"` / `"0"` になる — `bool` は `int` の
      サブクラスなので明示的に弾く（Alteryx の Bool→String は "True"/"False"）
    - 日付が `"1704067200000000"`（epoch 整数）に、`NaT` が int64 の最小値に
      なる — `Timestamp` は実数ではないので対象外

    **すでに文字列になっている値も拾う。** CSV を `dtype=str` で読んだ、
    前段の `np.where` で文字列化された等の理由で、値としては数値なのにセルが
    `"1.0"` になっている列は珍しくない。この場合は「正準な10進表記で小数部が
    ゼロ」の表記だけ小数部を落とす（`_ZERO_FRACTION_TEXT` を参照）:

        "1.0" → "1"      "001" → "001"     "B1"  → "B1"
        "1.5" → "1.5"    "1e5" → "1e5"     " 1.0" → " 1.0"

    列ごと `pd.to_numeric(errors="coerce")` に通すのと違い、**情報を捨てない**
    のが要点。coerce は `"B1"` のような数値でないテキストを黙って NaN にし、
    その NaN を後段の `fill_empty()` がプレースホルダで塗り潰すため、消えたことが
    出力から分からなくなる。どうしても coerce が要る場合の手順は20章。

    なお副作用として、バージョン番号のような「数値ではない `"1.0"`」も `"1"` に
    なる。表示用の変換なので許容しているが、そういう列には通さないこと。
    """
    result = series.astype("string")
    if is_numeric_dtype(series) and not (
        is_bool_dtype(series) or is_complex_dtype(series)
    ):
        # 実数の数値 dtype は全セルが実数と分かっているので、セル単位の
        # 判定を省く（100万行で3倍ほど速い）。bool と complex は
        # is_numeric_dtype が True を返すが実数ではないので下へ落とす。
        numeric = pd.to_numeric(series, errors="coerce")
    else:
        # object 経由にするのは datetime 対策。元の dtype のまま .where()
        # すると非該当セルが NaT になり、pd.to_numeric がそれを int64 の
        # 最小値として読む（さらに .abs() が桁あふれして範囲ガードも
        # すり抜ける）。object にしておけば非該当は NaN になる。
        as_object = series.astype(object)
        numeric = pd.to_numeric(
            as_object.where(as_object.map(_is_real_number)), errors="coerce"
        )
    whole = numeric.notna() & numeric.mod(1).eq(0) & numeric.abs().lt(_INT64_BOUND)
    # .to_numpy() で位置代入する — Series のまま渡すと index で整列するので、
    # フィルタや concat 後の重複 index を持つ列で ValueError になる。
    result.loc[whole] = numeric.loc[whole].astype("Int64").astype("string").to_numpy()
    # 最後に、数値オブジェクトとしては拾えなかった「文字列の "1.0"」を処理する。
    # 上で変換済みのセルは "1" になっていてこのパターンに当たらないので、
    # 二重適用にはならない。
    return result.str.replace(_ZERO_FRACTION_TEXT, r"\1", regex=True)
