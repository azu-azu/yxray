"""Alteryx FindReplace（FindAny + Append）を pandas で再現する参照実装。

引数名の対応（一番迷うところなので最初に）:

    find_field   = haystack（探される本文 / targets 側）
    search_field = needle  （探すキーワード / lookup 側）

yxray の scaffold が生成する find_any_append(...) 呼び出しの定義。
生成コードには埋め込まれないため、このファイルをプロジェクトへコピーして使う。

Alteryx XML のアンカー名との対応（XML では lookup 表を "Source" と呼ぶが、
「元データ」と紛らわしいので本実装では lookup と呼ぶ）:

- Targets（メインストリーム） → targets_df / find_field（FieldFind）
- Source（ルックアップ表）    → lookup_df / search_field（FieldSearch）

実 Alteryx の golden 出力との突合で検証済みの意味論:

- needle = lookup 側の search_field 値が targets 側の find_field に
  部分文字列として含まれるか
- 採用規則: 開始位置が target 文字列中で最も左のマッチの検索値の行が勝つ —
  lookup 順ではない（apple(位置0) vs ppl(位置1) の判別 golden で確定。
  終了位置でもない）。開始位置が同点なら lookup 順で先の行
  （app/apple の入れ子を両方の並び順で実測 — 長さは無関係）
- 同じ検索値が複数の lookup 行にあるときは後の行が有効（辞書的上書き）
- ReplaceMultipleFound は FindAny + Append では出力に影響しない
  （複数の golden × True/False 両設定で同一出力）
- NoCase=True は大小無視でマッチ（採用規則は維持）
- 空文字・NULL の検索値は無視される
- 出力列は「元の Targets 列 + append_fields」のみ（検索値の列は含まない）

FindAny + Append の意味論は上記すべて golden 実測済みで、推定は残っていない。

── ここから下は golden ではなく、この実装が下している判断 ──────────

Alteryx の挙動そのものではなく、「翻訳結果を人間がレビューできる形に保つ」
「入力の型と実行時間を壊さない」ための設計判断。golden で確定した事実と混ぜて
読まないよう節を分けてある。

- ReplaceMultipleFound に対応する引数は置かない。無影響が確定した引数を
  残すと「効く」と誤解されるため削除した
- case_sensitive に既定値は置かない。大小を区別するかは翻訳結果を左右する
  判断なので、ライブラリ側で先取りせず呼び出し側に必ず明示させる
  （scaffold の生成コードも常に明示する）
- collect_match_diagnostics の既定は False。曖昧マッチ表は lookup 行数に
  比例したコストを毎回払うので、レビューしたいときだけ呼び出し側が True に
  する（詳細は find_any_append() の docstring）
- append_fields の Geometry（Alteryx の SpatialObj）は文字列化せず、生の
  shapely オブジェクトのまま返す。他の append 値は表示用に文字列化するが、
  str(polygon) は全座標入りの WKT を生成するため、複雑なポリゴンでは重いうえ
  SpatialObj としての型も失われる。なお「Alteryx の Append が SpatialObj を
  空間オブジェクトとして出力する」ことは golden 未実測 — ここでの根拠は
  「入力の型を壊さない」であって、Alteryx 出力との突合ではない
- 戻り値は常に pd.DataFrame（GeoDataFrame ではない）。呼び出し側で空間演算に
  使う場合は gpd.GeoDataFrame(result, geometry=..., crs=...) で包み直すこと
- ログの出力先は呼び出し側が決める（logger 引数）。既定の None は print で、
  ノートブックや `python find_any_append.py` のように logging を設定していない
  場所へこのファイルをコピーしてもそのまま読める。logger を渡すと logger.info
  へ流れ、yxray の生成スクリプト（logging.basicConfig 済み・Browse などが
  logger.warning を出す）と経路が1本にそろう。出す・出さないの判断は従来どおり
  verbose が持ち、logger はあくまで「どこへ出すか」だけを決める
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd

try:
    from shapely.geometry.base import BaseGeometry
except ModuleNotFoundError:
    # shapely は find_any_append の必須依存ではない（空間データを扱わない
    # 呼び出しがほとんど）。未インストールなら Geometry 判定は常に False
    # になるだけで、他の動作には影響しない。
    BaseGeometry = None  # type: ignore[assignment,misc]

# 元データ・ルックアップ表の行を追跡するための内部 ID 列
TARGET_ROW_ID = "_target_row_id"
LOOKUP_ROW_ID = "_lookup_row_id"


def _stringify(value: object) -> str:
    """スカラー値を文字列化する（NaN は呼び出し側で除外済みの前提）。

    列にNaNが1件でも混じると pandas が列全体を float64 に昇格させるため、
    整数IDのつもりの値が 123 ではなく 123.0 になる。この差で
    str(needle) と haystack の文字列表現が食い違い、本来一致すべき行が
    静かにマッチしなくなるので、整数値のfloatは末尾の ".0" を落とす。
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _is_geometry(value: object) -> bool:
    """value が shapely の Geometry (Point/Polygon/...) かどうか。

    isinstance のみで判定する（hasattr(value, "wkt") は使わない）。
    shapely の wkt は保存済み属性ではなく、アクセスした瞬間に Geometry を
    WKT文字列へ変換する property なので、hasattr で「存在確認」したつもりが
    実際には毎回 WKT を生成してしまい、避けたかった重い変換がここで
    そのまま起きる（isinstance は型チェックのみで中身に触れない）。
    """
    return BaseGeometry is not None and isinstance(value, BaseGeometry)


def _prepare_append_value(value: object) -> object:
    """append_fields の1値を出力用に整える。

    Geometry はそのまま返す。str(polygon) は全座標入りの WKT 文字列に
    展開されるため重く、しかも SpatialObj のつもりの値が文字列に化けて
    型を失う（呼び出し側で再度パースし直す羽目になる）。Geometry 以外は
    従来どおり _stringify する（123.0 → "123" の桁落ち防止は保つ）。
    """
    if _is_geometry(value):
        return value
    # cast は型検査を通すためだけのもの（実行時の挙動は変わらない）。
    # pd.notna は実行時なら任意の object を受け取れるが、pandas-stubs の
    # overload は Scalar 系（str/int/float/datetime…）しか受けないため、
    # object のまま渡すと「no overloads match」で型検査が落ちる。
    return _stringify(value) if pd.notna(cast(Any, value)) else pd.NA


def _make_log(logger: logging.Logger | None) -> Callable[[str], None]:
    """1行ぶんのログ出力口を作る（呼ばれるのは verbose=True のときだけ）。

    logger=None（既定）は print。このファイルはコピーして使う参照実装で、
    ノートブックや `python find_any_append.py` のように logging を設定して
    いない場所から呼ばれることが多く、そこで logger.info にすると既定の
    ルートレベル（WARNING）に落ちて何も出なくなる。

    logger を渡すと logger.info へ流す。yxray の生成スクリプトは
    logging.basicConfig 済みで logger を持ち、Browse の logger.info や CRS の
    logger.warning と同じ経路・同じフォーマットにそろう（print のままだと
    stdout と stderr にログが二分され、まとめてリダイレクトも抑制もできない）。

    見出しの前後に置いてある空行は print で読むときの間隔調整なので、
    logger 経由では落とす（空の INFO レコードを出しても意味がない）。
    """
    if logger is None:
        return print

    def log(message: str) -> None:
        text = message.strip("\n")
        if not text:
            return
        logger.info("%s", text)

    return log


def find_any_append(
    targets_df: pd.DataFrame,   # 残したい元データ
    lookup_df: pd.DataFrame,    # ルックアップ表（探す値と追加列を持つ。Alteryx XML では Source）
    *,
    find_field: str,
    search_field: str,
    append_fields: list[str],
    case_sensitive: bool,  # Alteryx の NoCase=False（大小を区別）に対応。既定値は置かず呼び出し側に必ず書かせる
    log_label: str = "",  # ログ見出しに添える識別ラベル（例: "ToolID_7"）。空なら見出しだけ出す
    logger: logging.Logger | None = None,  # ログの出力先。None は print（下記）
    verbose: bool = True,
    collect_match_diagnostics: bool = False,  # 曖昧マッチの集計。表示量ではなく計算量が変わる（下記）
) -> pd.DataFrame:
    """find_field に search_field 値を部分一致で探し、マッチした append_fields を付与する。

    使い方:
    - targets_df[find_field] が haystack（探される本文）、
      lookup_df[search_field] が needle（探すキーワード）
    - 戻り値は「元の Targets 列 + append_fields」だけを持つ新しい DataFrame。
      行数・行順は targets_df のまま（Find Replace は join ではないので、
      複数マッチしても 1 target = 1 行）。入力の DataFrame は変更しない
    - 検索キー列（search_field の値）と行追跡 ID は内部・verbose 表示専用で、
      戻り値には残さない
    - append_fields と同名の列が targets_df に既にあると ValueError。
      必要な列が無いときは KeyError

    verbose がログを出すかどうか、logger がそれをどこへ出すかを決める。
    logger=None（既定）なら print で、コピー先が logging 未設定でもそのまま
    読める。logger を渡すと logger.info へ流れ、yxray の生成スクリプトのように
    既に logger を持つ呼び出し元では他のツールのログと同じ経路にそろう
    （レベルでの抑制もリダイレクトもまとめて効くようになる）。

    collect_match_diagnostics は verbose とは別の軸で、**表示量ではなく計算量**を
    決める。「その target が何行の lookup にマッチしたか」を出すには全 needle を
    全 target に当てる必要があり、勝者を決める処理（target ごとに1回の検索）とは
    桁が違うコストになる。False にすると曖昧マッチの集計と表示だけが消え、
    戻り値は完全に同一。verbose にこの計算を暗黙に背負わせないため引数を分けた。

    ただし診断を読むのは verbose サマリだけなので、実際に集めるのは
    collect_match_diagnostics と verbose が**両方 True のとき**。verbose=False で
    集めても誰も読めない（戻り値には出ない）ため、走査ごと省く。つまり verbose は
    コストを増やす方向には効かず、減らす方向にだけ効く。

    既定は False。曖昧マッチ表は「翻訳が正しいか人間が確かめる」段階で価値が
    あるもので、毎回払うには重すぎる。コストは lookup 1行につき pandas 呼び出し
    1回なので、**targets が少なくても lookup 行数だけで決まる**: 実測で lookup
    4万行のとき targets 300行で13秒・3000行で37秒、走査を切れば0.4秒。scaffold の
    生成コードもこの既定に合わせて False を明示的に出すので、レビューしたい
    ときだけその行を True にする。

    複数の lookup 行にマッチしたときどの行が採用されるか（最も左のマッチ →
    同点なら lookup 順で先の行 → 同じ検索値なら後の行）と、NoCase・空文字・
    NULL の扱いは、golden 実測済みの仕様としてモジュール docstring に
    まとめてある。ここでは繰り返さない。
    """

    start = time.perf_counter()
    log = _make_log(logger)

    if verbose:
        # log_label は省略可なので、空のときは飾りごと落とす（"- 🍒  -" を出さない）
        label = f" - 🍒 {log_label} -" if log_label else ""
        log(f"\n🐷 [Find Replace] find any append{label}")
        log(f"    haystack: '{find_field}' ← この中を 🌲")
        log(f"    needle  : '{search_field}' ← これで探す 🪡")
        log(f"    append  : {append_fields}")
        log("    部分文字列として含まれるか 判定中 ...\n")

    # ── 入力チェック ──────────────────────────────────────────────
    if find_field not in targets_df.columns:
        raise KeyError(f"targets_df に列がありません: {find_field}")

    required_lookup_columns = [search_field, *append_fields]
    missing_lookup_columns = [
        column
        for column in required_lookup_columns
        if column not in lookup_df.columns
    ]
    if missing_lookup_columns:
        raise KeyError(
            f"lookup_df に列がありません: {missing_lookup_columns}"
        )

    # 出力に追加する列（append_fields）が targets_df に同名で既にあると、
    # 同じ列名を2つ持つことになり結果が壊れるので弾く。search_field（検索キー）
    # は出力に残さない（実 Alteryx の Append 出力に検索値の列は現れない）ため、
    # find_field == search_field でも衝突しない。
    overlap = [field for field in append_fields if field in targets_df.columns]
    if overlap:
        example = overlap[0]
        raise ValueError(
            "列名の衝突: lookup_df から付与しようとした append_fields の列 "
            f"{overlap} が targets_df 側に同名で既に存在します。"
            "2つの df で同じ列名は共存できないため、この列は追加できません。\n"
            "対処: lookup_df 側の該当列を rename して名前をずらし、"
            "append_fields も新しい名前に合わせてから呼び出してください。\n"
            f'  例: 追加列 "{example}" が Targets 側と衝突するとき\n'
            f'    find_any_append(\n'
            f'        targets_df,\n'
            f'        lookup_df.rename(columns={{"{example}": "{example}_lookup"}}),\n'
            f'        find_field="{find_field}",\n'
            f'        search_field="{search_field}",\n'
            f'        append_fields=[..., "{example}_lookup", ...],  # ← rename 後の名前\n'
            f'    )'
        )

    # ── 準備 ─────────────────────────────────────────────────────
    targets = targets_df.reset_index(drop=True)
    targets.insert(0, TARGET_ROW_ID, range(len(targets)))

    lookup = lookup_df[required_lookup_columns].reset_index(drop=True)
    # 同じ検索値が複数の lookup 行にあるときは「後の行」が有効（辞書的上書き。
    # RMF 設定に依らない — golden 実測: apple×2 は両設定とも後の行）。
    # 先に重複を排除する。行番号（_lookup_row_id）は排除前の位置を保つ。
    lookup = lookup[~lookup[search_field].duplicated(keep="last")]

    # find_field を文字列化した haystack。NaN は NaN のまま残す
    # （astype(str) だけだと NaN が "nan" になり誤マッチするため map で除外する）。
    # _stringify で整数値floatの ".0" 付与を防ぎ、needle 側と表記を揃える。
    raw_find = targets[find_field]
    haystack = raw_find.map(lambda v: _stringify(v) if pd.notna(v) else pd.NA)
    haystack_cmp = haystack if case_sensitive else haystack.str.lower()

    # ── 勝者判定と診断（独立した2つの走査）───────────────────────
    # 診断は verbose サマリの材料。勝者判定はこれを一切読まない（逆向きの依存は
    # 無い）ので、状態も更新も別の入れ物に分けてある。診断だけが lookup 行数 ×
    # target 行数の走査を必要とするので、止められるようにしてある
    # （止めても戻り値は変わらない）。
    needles = _needles(lookup, case_sensitive=case_sensitive)
    winner = _find_winner(
        haystack_cmp=haystack_cmp,
        needles=needles,
        append_fields=append_fields,
    )
    # 集めるのは「集めろと言われた」かつ「読み手が居る」ときだけ。verbose=False で
    # 集めた診断は戻り値にも出ず誰も読めないので、走査ごと省く。
    diagnostics: _Diagnostics | None = None
    if collect_match_diagnostics and verbose:
        diagnostics = _Diagnostics(
            match_count=pd.Series(0, index=targets.index, dtype="int64"),
            # 各 target にマッチした検索値をすべて集める（確認表示用）。lookup 表の
            # 並び順に append する（診断用の一覧で、採用値の決定とは独立）。
            needles_per_row=[[] for _ in range(len(targets))],
        )
        _scan_diagnostics(diagnostics, haystack_cmp=haystack_cmp, needles=needles)

    # ── 結果の組み立て（入力順のまま。matched/unmatched に分割しない）──
    # 実 Alteryx の Append 出力に合わせる: 元の Targets 列 + append_fields のみ。
    # 検索キー列（search_field / matched_needle）と行追跡 ID（_target_row_id・
    # _lookup_row_id）は内部・デバッグ専用で、出力には残さない
    # （Append モードでは検索値の列は出力に現れない — golden 突合で検証済み）。
    # appended[field] は index が 0..n-1 の object Series。Series のまま代入して
    # object dtype と pd.NA を保つ（.to_numpy() で ndarray 化すると dtype 推論で
    # str へ寄せられ、未マッチの pd.NA が nan に化ける）。
    result = targets_df.reset_index(drop=True).copy()
    for field in append_fields:
        result[field] = winner.appended[field]

    if verbose:
        # matched_needle / _lookup_row_id はデバッグにかなり有用なので、計算は
        # 残したまま、出力とは別の DataFrame にまとめて verbose 表示だけで使う
        # （戻り値の result には混ぜない）。
        # 診断を集めていないときは診断由来の列を持たない debug 表になる
        # （_log_summary はその2列の有無で曖昧マッチ節を出し分ける）。
        columns: dict[str, object] = {
            TARGET_ROW_ID: range(len(targets_df)),
            find_field: targets[find_field].to_numpy(),
        }
        if diagnostics is not None:
            columns["matched_lookup_rows"] = diagnostics.match_count.to_numpy()
            columns[_all_col(search_field)] = [
                " | ".join(lst) for lst in diagnostics.needles_per_row
            ]
        columns[LOOKUP_ROW_ID] = winner.lookup_id.astype("Int64").to_numpy()
        columns[_needle_col(search_field)] = winner.needle.to_numpy()
        debug = pd.DataFrame(columns)
        for field in append_fields:
            debug[field] = winner.appended[field].to_numpy()
        _log_summary(
            log=log,
            start=start,
            result=result,
            debug=debug,
            find_field=find_field,
            search_field=search_field,
            append_fields=append_fields,
        )

    return result


@dataclass
class _WinnerSelection:
    """採用された lookup 行だけを表す状態（本体結果の材料）。

    appended だけが戻り値 result に流れる。lookup_id / needle は verbose の
    debug 表用、best_pos は「より左のマッチが来たら上書きする」判定用の内部値。
    """

    lookup_id: pd.Series           # 採用された lookup 行番号（重複排除前の位置）
    needle: pd.Series              # 採用された検索値
    best_pos: pd.Series            # 採用中マッチの target 文字列内での開始位置（-1 = 未マッチ）
    appended: dict[str, pd.Series]  # append_fields ごとの付与値


@dataclass
class _Diagnostics:
    """verbose サマリ専用の観測値。本体結果（result）には一切流れない。

    勝者判定はこの中身を読まないので、診断を止めても採用結果は変わらない。
    読み手が verbose サマリしか居ないので、そもそも表示しないときは作られない。
    """

    match_count: pd.Series           # 何行の lookup にマッチしたか
    needles_per_row: list[list[str]]  # マッチした検索値すべて（lookup 表の並び順）


def _collect_diagnostics(
    diagnostics: _Diagnostics,
    *,
    needle: str,
    contains: pd.Series,
) -> None:
    """1 needle 分のマッチを診断側にだけ記録する。

    呼ばれるのは contains が1件以上 True のときだけ（勝者判定側の早期スキップと
    共有）。診断は本体結果にも勝者判定にも書き込まない — ここで触るのは
    diagnostics の中身だけ。
    """
    # 「何行の lookup にマッチしたか」なので、採用されなかったマッチも数える
    diagnostics.match_count += contains.astype("int64")
    for i in contains.to_numpy().nonzero()[0]:
        diagnostics.needles_per_row[i].append(needle)


@dataclass
class _Needle:
    """検索に使う lookup 1行分。lookup 表の並び順に並べて使う。"""

    lookup_id: object          # 重複排除前の元の行番号（_lookup_row_id）
    text: str                  # _stringify 済みの検索値（表示・診断用）
    cmp: str                   # 比較用（NoCase なら小文字化済み）
    appends: tuple[object, ...]  # append_fields に対応する lookup 側の生の値


def _needles(lookup: pd.DataFrame, *, case_sensitive: bool) -> list[_Needle]:
    """lookup を検索対象の needle 列に変換する（NULL・空文字はここで捨てる）。

    lookup は [search_field, *append_fields] の列を持ち、重複検索値を排除済みで、
    index に排除前の元の行番号を保っていること。戻り値は lookup の並び順。
    """
    # itertuples の 0 番目が search_field、以降が append_fields。
    # lookup の列は [search_field, *append_fields] なので、appends の長さは
    # 必ず len(append_fields) と一致する。
    needles: list[_Needle] = []
    for lookup_id, values in zip(
        lookup.index, lookup.itertuples(index=False, name=None), strict=True
    ):
        needle = values[0]
        if pd.isna(needle):
            continue
        needle = _stringify(needle)
        if not needle:
            continue
        needles.append(
            _Needle(
                lookup_id=lookup_id,
                text=needle,
                cmp=needle if case_sensitive else needle.lower(),
                appends=values[1:],
            )
        )
    return needles


def _find_winner(
    *,
    haystack_cmp: pd.Series,
    needles: list[_Needle],
    append_fields: list[str],
) -> _WinnerSelection:
    """各 target にどの lookup 行が採用されるかを決める。

    採用されるのは「開始位置が target 文字列中で最も左」のマッチの行
    （golden 実測: apple(位置0) と ppl(位置1) では apple が勝つ — 終了位置で
    決まるなら先に終わる ppl のはずだった）。開始位置が同点なら lookup 順で
    先の行が勝つ（golden 実測: app/apple の入れ子は並び順を入れ替えても常に
    先の行 — 長さは無関係）。ReplaceMultipleFound は判定に入らない
    （両設定で同一出力と実測済み。モジュール docstring 参照）。

    この2つの規則は Python の正規表現の交替（`a|b|c`）の挙動そのもの:
    エンジンは左端から位置を進めながら、各位置で選択肢を「書いた順」に試し、
    最初に成立したものを返す。そこで needle を lookup 順に並べて1本の
    パターンに連結し、target ごとに1回 search する。needle ごとに全 target を
    走査する必要がなくなり、計算量が lookup 行数に比例しなくなる。
    """
    index = haystack_cmp.index
    row_count = len(haystack_cmp)
    # target 行ごとの「採用された needle の並び順位置」（-1 = 未マッチ）
    winner_of_row: list[int] = [-1] * row_count
    best_pos: list[int] = [-1] * row_count

    if needles:
        # needle は正規表現ではなくリテラルなので必ずエスケープする
        # （"1.5" の "." が任意の1文字になってしまう）。
        pattern = re.compile("|".join(re.escape(needle.cmp) for needle in needles))
        # マッチ文字列から needle へ戻すための索引。同じ比較文字列を持つ needle が
        # 複数あるとき（NoCase で "Apple" と "apple" など）に拾うのは「先の行」:
        # 同位置マッチは lookup 順で先の行が勝つという採用規則そのもので、
        # かつ交替も先に書いた選択肢を採るため、エンジンが実際に使った選択肢と
        # 一致する。後の行で上書きしてはいけない。
        first_needle_of: dict[str, int] = {}
        for order, needle in enumerate(needles):
            first_needle_of.setdefault(needle.cmp, order)

        for row, text in enumerate(haystack_cmp.to_numpy()):
            # NULL の haystack はマッチ対象外（pd.NA / None / NaN が来る）
            if not isinstance(text, str):
                continue
            match = pattern.search(text)
            if match is None:
                continue
            winner_of_row[row] = first_needle_of[match.group(0)]
            best_pos[row] = match.start()

    # ── 採用された needle から出力用の列を組み立てる ──────────────
    lookup_ids: list[object] = [pd.NA] * row_count
    needle_texts: list[object] = [pd.NA] * row_count
    appended: dict[str, list[object]] = {
        field: [pd.NA] * row_count for field in append_fields
    }
    # append 値の _stringify は「採用された needle の分だけ」行う（従来と同じ）。
    # 同じ needle が複数 target に勝つことがあるので結果は使い回す。
    stringified: dict[int, tuple[object, ...]] = {}
    for row, order in enumerate(winner_of_row):
        if order < 0:
            continue
        needle = needles[order]
        lookup_ids[row] = needle.lookup_id
        needle_texts[row] = needle.text
        values = stringified.get(order)
        if values is None:
            # append 値も needle/haystack と同様に _stringify する。lookup 列が
            # NaN 混在で float64 昇格すると 123 が 123.0 になり、golden の "123"
            # と文字列比較で偽差分になるため（NaN は NA のまま残す）。
            # ただし Geometry（SpatialObj）は例外: _stringify は最後に str()
            # を呼ぶため、Polygon 等が全座標入りの巨大な WKT 文字列に化けて
            # 重いうえに型も失う。_prepare_append_value が Geometry だけ
            # そのまま素通しする。
            values = tuple(
                _prepare_append_value(value) for value in needle.appends
            )
            stringified[order] = values
        for field, value in zip(append_fields, values, strict=True):
            appended[field][row] = value

    return _WinnerSelection(
        lookup_id=pd.Series(lookup_ids, index=index, dtype="object"),
        needle=pd.Series(needle_texts, index=index, dtype="object"),
        best_pos=pd.Series(best_pos, index=index, dtype="int64"),
        appended={
            field: pd.Series(values, index=index, dtype="object")
            for field, values in appended.items()
        },
    )


def _scan_diagnostics(
    diagnostics: _Diagnostics,
    *,
    haystack_cmp: pd.Series,
    needles: list[_Needle],
) -> None:
    """needle ごとに全 target を走査して診断を集める（勝者判定とは独立）。

    勝者判定が needle ごとの走査を必要としなくなったので、その走査はここが
    引き取る。「何行の lookup にマッチしたか」は全 needle を見ないと出せない
    ため、この関数の計算量は lookup 行数 × target 行数のままである。
    """
    for needle in needles:
        # str.find 1回で「マッチしたか」(pos >= 0) を得る（従来と同じ計算）。
        pos = haystack_cmp.str.find(needle.cmp).fillna(-1).astype("int64")
        contains = pos >= 0
        if not contains.any():
            continue
        _collect_diagnostics(diagnostics, needle=needle.text, contains=contains)


def _needle_col(search_field: str) -> str:
    """debug 表での「採用された検索値」列名。呼び出し側と表示側で同じ名前を使う。"""
    return f"matched_{search_field}"


def _all_col(search_field: str) -> str:
    """debug 表での「マッチした検索値すべて」列名。"""
    return f"all_matched_{search_field}"


def _log_summary(
    *,
    log: Callable[[str], None],
    start: float,
    result: pd.DataFrame,
    debug: pd.DataFrame,
    find_field: str,
    search_field: str,
    append_fields: list[str],
) -> None:
    """処理時間・行数・複数マッチ（曖昧マッチ）の確認用サマリを出す。

    出力先は呼び出し側が決めた log（print か logger.info）。この関数は
    どちらに出しているかを知らない。

    debug は出力（result）には含めない観測列（行 ID・採用 lookup 行・採用/全
    マッチ検索値）をまとめた DataFrame。ここでの表示専用で、戻り値には残さない。
    診断（matched_lookup_rows / all_matched_*）を集めていないときは、debug が
    その2列を持たない。曖昧マッチ節を出せるかはこの列の有無で決まる。

    行数は before/after に分けず 1 行だけ出す。result は targets_df のコピーに
    列を足したものなので行数が変わる経路が構造的に無く、before/after を並べても
    常に同じ値になる（＝情報量ゼロ。行数不変はログではなくテストで守る:
    tests/test_reference_scripts.py）。
    """

    elapsed = time.perf_counter() - start
    # マッチ行数は診断ではなく採用結果から数える（採用 lookup 行があること＝
    # 1行以上にマッチしたこと）。診断 OFF でも同じ値が出せる。
    matched_rows = int(debug[LOOKUP_ROW_ID].notna().sum())

    log(f"runtime == {elapsed:.3f} 秒 ==")
    log(f"rows          : {len(result):,}")
    log(f"matched rows  : {matched_rows:,}")

    if "matched_lookup_rows" not in debug.columns:
        log("ambiguous rows: 未集計（collect_match_diagnostics=False）")
        log("")
        return

    # 1 target が複数 lookup 行にマッチした（＝採用値が lookup 表の並び順に依存する）
    # 行を可視化。target 側（find_field の本文）と lookup 側（採用された検索値・
    # lookup 行・append 値）の両方を並べ、どのテキストがどの値を拾ったか確認できる
    # ようにする。
    ambiguous = debug[debug["matched_lookup_rows"] > 1].sort_values(
        "matched_lookup_rows", ascending=False
    )

    show_cols = [
        TARGET_ROW_ID,        # target: 行 ID
        find_field,           # target: マッチ対象の本文
        "matched_lookup_rows",  # 何行の lookup にマッチしたか
        _all_col(search_field),     # lookup: マッチした検索値すべて（lookup 表の並び順）
        LOOKUP_ROW_ID,        # lookup: 採用された lookup 行
        _needle_col(search_field),  # lookup: 採用された検索値
        *append_fields,       # lookup: 付与された値
    ]
    log(f"ambiguous rows: {len(ambiguous):,}（複数 lookup にマッチ）")
    if not ambiguous.empty:
        log("== top 10 ==")
        log(ambiguous[show_cols].head(10).to_string(index=False))
    log("")


def main() -> None:
    """使い方の例（動作確認用のデモ）。

    このスクリプトは import して find_any_append() を直接呼ぶのが本来の
    使い方。ここはサンプルデータで挙動と出力を確認するためのデモで、
    `python reference_impl/find_any_append.py` で実行できる。
    実データは自分で DataFrame にして関数へ渡すこと。
    """
    targets_df = pd.DataFrame(
        {
            "text": [
                "東京都渋谷区 アップルストア",
                "cherry apple pie",
                "just berry",
                "nothing here",
            ],
        }
    )
    lookup_df = pd.DataFrame(
        {
            "kw":    ["東京", "渋谷", "アップル", "apple", "cherry", "berry"],
            "label": ["都", "区", "林檎", "APL", "CHR", "BRY"],
            "code":  [1, 2, 3, 4, 5, 6],
        }
    )

    result = find_any_append(
        targets_df,
        lookup_df,
        find_field="text",
        search_field="kw",
        append_fields=["label", "code"],
        case_sensitive=True,  # Alteryx の NoCase=False
        # デモなので曖昧マッチ表を見せる。生成コードは False を出す（4行の
        # サンプルでは無視できるが、実データでは lookup 行数分のコストになる）
        collect_match_diagnostics=True,
    )

    print("\n-- result --")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
