"""Alteryx FindReplace（FindAny + Append）を pandas で再現する参照実装。

yxray の scaffold が生成する simulate_find_any_append(...) 呼び出しの定義。
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
"""

from __future__ import annotations

import time

import pandas as pd

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


def simulate_find_any_append(
    targets_df: pd.DataFrame,   # 残したい元データ
    lookup_df: pd.DataFrame,    # ルックアップ表（探す値と追加列を持つ。Alteryx XML では Source）
    *,
    find_field: str,
    search_field: str,
    append_fields: list[str],
    case_sensitive: bool = True,  # Alteryx の NoCase=False（大小を区別）に対応
    replace_multiple_found: bool = True,  # Alteryx の ReplaceMultipleFound。FindAny + Append では True/False で出力差なし（golden 実測）— 判定には未使用、設定値の記録として受け取る
    log_label: str = "",  # ログ見出しの先頭に付ける識別ラベル（例: "ToolID 7"）
    verbose: bool = True,
) -> pd.DataFrame:
    """find_field に search_field 値を部分一致で探し、マッチした append_fields を付与する。

    出力は実 Alteryx の Append 出力に合わせ「元の Targets 列 + append_fields」のみ。
    検索キー列（search_field の値）と行追跡 ID は内部で使うだけで出力には残さない
    （Append モードでは検索値の列は出力に現れない — 実 Alteryx の golden 出力
    との突合で検証済み）。

    Find Replace は join ではないので、複数マッチしても出力は 1 target = 1 行。
    複数の lookup 行にマッチしたとき採用されるのは「開始位置が target 文字列中で
    最も左」のマッチの検索値の行（golden 突合で検証済み — lookup 順でも
    終了位置でもない点に注意）。開始位置が同点のときは lookup 順で先の行が
    勝つ（golden 突合で検証済み — 検索値の長さは無関係）。同じ検索値が複数の
    lookup 行にあるときは後の行が有効（辞書的上書き — golden 突合で検証済み）。
    replace_multiple_found（Alteryx の ReplaceMultipleFound）は FindAny +
    Append では True/False どちらでも出力が変わらないことが golden で実測
    されているため、判定には使わない。
    """

    start = time.perf_counter()

    if verbose:
        print(f"\n{log_label}⛳️ simulate find any append")
        print("target の文字列の中に、lookup 表の検索値が「部分文字列として」含まれるか で判定中 ...\n")

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
            f'    simulate_find_any_append(\n'
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

    # ── マッチ結果の入れ物 ─────────────────────────────────────────
    winning_lookup_id = pd.Series(pd.NA, index=targets.index, dtype="object")
    matched_needle = pd.Series(pd.NA, index=targets.index, dtype="object")
    appended = {
        field: pd.Series(pd.NA, index=targets.index, dtype="object")
        for field in append_fields
    }
    match_count = pd.Series(0, index=targets.index, dtype="int64")  # 確認用: 何行の lookup にマッチしたか
    # 採用中マッチの target 文字列内での開始位置（-1 = 未マッチ）
    best_pos = pd.Series(-1, index=targets.index, dtype="int64")

    # verbose 時だけ、各 target にマッチした検索値をすべて集める（確認表示用）。
    # lookup 表の並び順に append する（診断用の一覧で、採用値の決定とは独立）。
    matched_needles_lists: list[list[str]] | None = (
        [[] for _ in range(len(targets))] if verbose else None
    )

    # lookup を並び順にループ。itertuples の 0 番目が search_field、以降が append_fields。
    # lookup_id は重複排除前の元の行番号（lookup.index に保持）。
    append_positions = range(1, len(required_lookup_columns))
    for lookup_id, values in zip(
        lookup.index, lookup.itertuples(index=False, name=None), strict=True
    ):
        needle = values[0]
        if pd.isna(needle):
            continue
        needle = _stringify(needle)
        if not needle:
            continue

        needle_cmp = needle if case_sensitive else needle.lower()
        # str.find 1回で「マッチしたか」(pos >= 0) と「開始位置」を同時に得る。
        # str.contains + str.find の2回に分けると文字列走査が needle ごとに
        # 倍になり、データが多いとき目に見えて遅くなる。
        pos = haystack_cmp.str.find(needle_cmp).fillna(-1).astype("int64")
        contains = pos >= 0
        if not contains.any():
            continue

        # 診断用は「何行の lookup にマッチしたか」なので確定済みも含めて数える
        match_count += contains.astype("int64")
        if matched_needles_lists is not None:
            for i in contains.to_numpy().nonzero()[0]:
                matched_needles_lists[i].append(needle)

        # 採用されるのは「開始位置が target 文字列中で最も左」のマッチの行
        # （golden 実測: apple(位置0) と ppl(位置1) では apple が勝つ —
        # 終了位置で決まるなら先に終わる ppl のはずだった）。開始位置が
        # 同点のときは lookup 順で先の行を維持する（golden 実測: app/apple の
        # 入れ子は並び順を入れ替えても常に先の行が勝つ — 長さは無関係）。
        # ReplaceMultipleFound は FindAny + Append では出力に影響しないことが
        # 実測されているため判定に使わない。
        fill = contains & ((best_pos < 0) | (pos < best_pos))
        if fill.any():
            winning_lookup_id[fill] = lookup_id
            matched_needle[fill] = needle
            best_pos[fill] = pos[fill]
            for position, field in zip(
                append_positions, append_fields, strict=False
            ):
                # append 値も needle/haystack と同様に _stringify する。lookup 列が
                # NaN 混在で float64 昇格すると 123 が 123.0 になり、golden の "123"
                # と文字列比較で偽差分になるため（NaN は NA のまま残す）。
                value = values[position]
                appended[field][fill] = _stringify(value) if pd.notna(value) else pd.NA

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
        result[field] = appended[field]

    if verbose:
        # matched_needle / _lookup_row_id はデバッグにかなり有用なので、計算は
        # 残したまま、出力とは別の DataFrame にまとめて verbose 表示だけで使う
        # （戻り値の result には混ぜない）。
        needle_col = f"matched_{search_field}"
        all_col = f"all_matched_{search_field}"
        debug = pd.DataFrame(
            {
                TARGET_ROW_ID: range(len(targets_df)),
                find_field: targets[find_field].to_numpy(),
                "matched_lookup_rows": match_count.to_numpy(),
                all_col: [" | ".join(lst) for lst in matched_needles_lists],
                LOOKUP_ROW_ID: winning_lookup_id.astype("Int64").to_numpy(),
                needle_col: matched_needle.to_numpy(),
            }
        )
        for field in append_fields:
            debug[field] = appended[field].to_numpy()
        _print_summary(
            start=start,
            targets_df=targets_df,
            result=result,
            debug=debug,
            find_field=find_field,
            append_fields=append_fields,
            needle_col=needle_col,
            all_col=all_col,
        )

    return result


def _print_summary(
    *,
    start: float,
    targets_df: pd.DataFrame,
    result: pd.DataFrame,
    debug: pd.DataFrame,
    find_field: str,
    append_fields: list[str],
    needle_col: str,
    all_col: str,
) -> None:
    """処理時間・行数・複数マッチ（曖昧マッチ）の確認用サマリを出す。

    debug は出力（result）には含めない観測列（行 ID・採用 lookup 行・採用/全
    マッチ検索値）をまとめた DataFrame。ここでの表示専用で、戻り値には残さない。
    """

    elapsed = time.perf_counter() - start
    matched_rows = int((debug["matched_lookup_rows"] > 0).sum())

    print(f" 🐒 simulate_find_any_append: {elapsed:.3f} 秒")
    print(f"rows before   : {len(targets_df):,}")
    print(f"rows after    : {len(result):,}")
    print(f"matched rows  : {matched_rows:,}")

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
        all_col,              # lookup: マッチした検索値すべて（lookup 表の並び順）
        LOOKUP_ROW_ID,        # lookup: 採用された lookup 行
        needle_col,           # lookup: 採用された検索値
        *append_fields,       # lookup: 付与された値
    ]
    print(f"ambiguous rows: {len(ambiguous):,}（複数 lookup にマッチ）")
    if not ambiguous.empty:
        print("== top 10 ==")
        print(ambiguous[show_cols].head(10).to_string(index=False))
    print()


def main() -> None:
    """使い方の例（動作確認用のデモ）。

    このスクリプトは import して simulate_find_any_append() を直接呼ぶのが本来の
    使い方。ここはサンプルデータで挙動と出力を確認するためのデモで、
    `python scripts/simulate_find_any_append.py` で実行できる。
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

    result = simulate_find_any_append(
        targets_df,
        lookup_df,
        find_field="text",
        search_field="kw",
        append_fields=["label", "code"],
        replace_multiple_found=True,   # Alteryx の ReplaceMultipleFound
        case_sensitive=True,           # Alteryx の NoCase=False
    )

    print("\n-- result --")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
