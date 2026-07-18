# Alteryx → pandas 変換時の暗黙デフォルトの差異

Alteryx は業務ユーザー向けにデフォルトがおおらかに設定されたツール、pandas はプログラマ向けに明示しない限り何も忖度しないライブラリ。
変換時の事故は構文の対応（`and` → `&` など）より、この**暗黙のデフォルトの差**に集中する。

---

## 1. `Contains` — 大文字小文字の扱い

| | 挙動 |
|---|---|
| **Alteryx** `Contains(col, "shop")` | 大文字小文字を区別しない（`"SHOP"` にもマッチ） |
| **pandas** `df[col].str.contains("shop")` | 大文字小文字を区別する（デフォルト `case=True`） |

忠実に移植するなら `case=False` を明示する。

```python
# Alteryx: Contains([col], "shop")
df[col].str.contains("shop", case=False, na=False)
```

---

## 2. `Contains` — 正規表現の解釈

| | 挙動 |
|---|---|
| **Alteryx** `Contains(col, "ta.ro")` | `"ta.ro"` をリテラル文字列として検索。`.` に特殊な意味なし |
| **pandas** `df[col].str.contains("ta.ro")` | デフォルトで正規表現として解釈。`.` は「任意の1文字」になる |

移植時は `re.escape()` でエスケープするか、`regex=False` を指定する。

```python
import re

# Alteryx: Contains([col], "ta.ro")
df[col].str.contains(re.escape("ta.ro"), na=False)
# または
df[col].str.contains("ta.ro", regex=False, na=False)
```

`na=False` も合わせて指定することで、NULL セルを `False` として扱う（Alteryx の挙動に近い）。

---

## 3. `IsEmpty()` — NULL と空文字の統合判定

| | 挙動 |
|---|---|
| **Alteryx** `IsEmpty([col])` | NULL と `""` の両方を「空」と判定する |
| **pandas** | NULL 判定（`isna()`）と空文字判定（`== ""`）が別々 |

pandas では2条件を `|` で組み合わせる必要がある。

```python
# Alteryx: IsEmpty([col])
df[col].isna() | (df[col] == "")
```

---

## 4. 空白のみの文字列（`"   "`）は「空ではない」

**Alteryx・pandas ともに共通**の挙動で、スペースのみのセルは「中身あり」として扱われる。
これも空とみなしたい場合は、両方とも `strip()` してから判定する。

```python
# Alteryx: IsEmpty(Trim([col]))
df[col].str.strip().isna() | (df[col].str.strip() == "")
```

---

## 5. 論理演算子と比較演算子

| 用途 | Alteryx | pandas |
|------|---------|--------|
| 論理 AND | `and` | `&` |
| 論理 OR | `or` | `\|` |
| 論理 NOT | `!` | `~` |
| 等値比較 | `=` | `==` |

pandas の boolean Series 演算では演算子の優先順位の都合で、**各条件を `()` で囲む必要がある**。

```python
# Alteryx: [A] = "x" AND [B] > 0
(df["A"] == "x") & (df["B"] > 0)
```

### 優先順位トラップ: `~`・`&`・`|` の混在

`~`（NOT）> `&`（AND）> `|`（OR）の順に優先されるため、OR を含む複合 NOT 条件で意図しない評価になりやすい。

```python
# 次の式は見た目と評価が異なる
~A & ~B & ~C & D | E
# 実際の評価: (~A & ~B & ~C & D) | E
# → OR の右辺 E では A/B/C の NOT チェックが適用されない
```

scaffold が `|` を含む複合条件を生成した場合、括弧の有無を必ず確認する。
意図を明示するなら:

```python
# 全件に NOT 条件を適用し、その上で OR 分岐させる場合
(~A & ~B & ~C) & (D | E)
```

---

## 6. Join の3出力（L / J / R）

Alteryx の Join ツールは出力アンカーが3本ある。

| アンカー | 意味 | pandas 相当 |
|---------|------|-------------|
| **J**（Join） | 両方にマッチした行 | `pd.merge(..., how='inner')` |
| **L**（Left only） | 左入力にしかない行（非マッチ） | `how='left'` + 非マッチ行の抽出 |
| **R**（Right only） | 右入力にしかない行（非マッチ） | `how='right'` + 非マッチ行の抽出 |

scaffold は J（inner）のみ生成する。L・R の出力を後続ツールに接続している場合は `indicator=True` で自前抽出が必要。

```python
merged = pd.merge(df_left, df_right, on="key", how="outer", indicator=True)
df_J = merged[merged["_merge"] == "both"].drop(columns="_merge")
df_L = merged[merged["_merge"] == "left_only"].drop(columns="_merge")
df_R = merged[merged["_merge"] == "right_only"].drop(columns="_merge")
```

---

## 7. Filter の2出力（T / F）

Alteryx Filter も出力アンカーが2本（True / False）ある。
scaffold は True 側のみ生成し、False 側（条件を満たさない行）は暗黙に捨てる。
False 側の行を後続で使っている場合は `~mask` で明示的に取り出す。

```python
mask = df["col"] > 0
df_true  = df[mask]
df_false = df[~mask]
```

---

## 8. Union の ByName vs ByPosition

Alteryx Union は2つのモードを持つ。

| モード | 挙動 |
|--------|------|
| **ByName**（デフォルト） | 列名で揃えて結合 → `pd.concat` 相当 |
| **ByPosition** | 列名を無視して位置で揃えて結合 → pandas に対応なし |

ByPosition の場合、一方の DataFrame の列名をもう一方に合わせてから `concat` する必要がある。

```python
# ByPosition: df_b の列名を df_a に合わせる
df_b.columns = df_a.columns
pd.concat([df_a, df_b], ignore_index=True)
```

---

## 9. Sort — NULL の位置

| | NULL / NaN の位置（デフォルト） |
|---|---|
| **Alteryx** | 先頭（昇順・降順とも） |
| **pandas** `sort_values` | 末尾（`na_position='last'`） |

Alteryx の挙動に合わせるなら `na_position='first'` を指定する。

```python
# Alteryx デフォルトに合わせる
df.sort_values("col", ascending=True, na_position="first")
```

---

## 10. Summarize（groupby）— NULL グループの扱い

| | NULL を含むグループ |
|---|---|
| **Alteryx** Summarize | NULL 値のグループも集計に含める |
| **pandas** `groupby` | NaN グループをデフォルトで除外する |

pandas で Alteryx の挙動に合わせるには `dropna=False` を指定する。

```python
# Alteryx Summarize の挙動に合わせる
df.groupby("col", dropna=False).agg({"val": "sum"})
```

---

## 11. DataCleansing — ヘッダー名のトリム

Alteryx の DataCleansing ツールはデータ値のクレンジング（空白除去、NULL 置換など）に加え、**列名自体のリネーム**機能を持つ。"Rename Fields" オプションで列名の前後空白を一括除去できる。

DynamicRename ツールを使う場合は `TrimWhitespace([Name])` のような式で全列名を動的に変換する。

pandas 相当：

```python
# 列名の前後空白を一括除去（DataCleansing / DynamicRename の "Rename Fields" 相当）
df.columns = df.columns.str.strip()
```

値のクレンジング（セル内の空白除去）は列名とは別操作になる。

```python
# 値の前後空白除去（DataCleansing の値クレンジング相当）
df["col"] = df["col"].str.strip()
```

---

## 12. `Substring` — 0-indexed（SQL の 1-indexed とは異なる）

| | 挙動 |
|---|---|
| **Alteryx** `Substring(col, start, length)` | `start` は **0-indexed**（最初の文字が位置 0） |
| **SQL** `SUBSTRING(col, start, length)` | `start` は 1-indexed（最初の文字が位置 1） |
| **pandas** `df[col].str[start:start+length]` | 0-indexed（Python スライスと同じ） |

Alteryx が 0-indexed であることの確認例：`Substring("DENVER", 2, 3)` → `"NVE"`（位置 2 から3文字）。もし 1-indexed なら `"ENV"` になるはず。

```python
# Alteryx: Substring([col], 5, 2)  →  位置5から2文字
df[col].str[5:5+2]   # = [5:7]

# Alteryx: Substring([col], 3)  →  位置3から末尾まで
df[col].str[3:]
```

SQL（1-indexed）から移植した変換式に `-1` 補正を入れると、全出力が1文字ずれてエラーなく誤動作するため注意。

エッジケース：`start` が式の評価で**負**になった場合、Python のスライスは「末尾から数える」意味に化けるため、Alteryx と挙動が分岐する。生成コードの start が負になり得る式はレビューで確認する。

---

## 13. `DateTimeAdd` — 日時加減算

| | 挙動 |
|---|---|
| **Alteryx** `DateTimeAdd(dt, n, "unit")` | 日時フィールドに整数 `n` を `unit` 単位で加算（負数で減算） |
| **pandas** | `pd.DateOffset` を使って同等の演算を行う |

```python
# Alteryx: DateTimeAdd(DateTimeToday(), -2, "months")
pd.Timestamp.today().normalize() + pd.DateOffset(months=-2)

# Alteryx: DateTimeAdd([date_col], 7, "days")
df["date_col"] + pd.DateOffset(days=7)
```

対応する unit 文字列：`"years"` / `"months"` / `"days"` / `"hours"` / `"minutes"` / `"seconds"`

---

## 14. `ToDate` — 文字列から日付型への変換

| | 挙動 |
|---|---|
| **Alteryx** `ToDate(val)` | 文字列や数値を日付型に変換 |
| **pandas** | `pd.to_datetime(val)` |

```python
# Alteryx: ToDate("2024-01-01")
pd.to_datetime("2024-01-01")
```

---

## 15. `FindReplace` — モード別の翻訳と部分一致ルックアップ

Alteryx の **FindReplace ツール**の挙動は `FindMode`（探し方）×
`ReplaceMode`（結果の使い方）の組み合わせで決まる。scaffold の翻訳も
この2軸で分岐する。

| FindMode | ReplaceMode | scaffold の翻訳 |
|----------|-------------|-----------------|
| **FindWhole**（完全一致） | Append | lookup 表を `drop_duplicates(keep=...)` してから `pd.merge(how="left")` |
| **FindWhole**（完全一致） | Replace | `ReplaceFoundField` を使う Replace 分岐で翻訳 |
| **FindAny**（部分一致） | Append | `simulate_find_any_append(...)` の呼び出しを生成（定義は生成しない） |
| **FindAny**（部分一致） | Replace | **未対応** — TODO コメント + 入力パススルー（`df_out = df_in`）にフォールバック |

### 設定タグの読み方 — ReplaceMode が主判定

`ReplaceMode` によって、参照される設定タグが切り替わる:

- `ReplaceMode=Append` → **`ReplaceAppendFields`** に指定された列を付与する
- `ReplaceMode=Replace` → **`ReplaceFoundField`** の値で、見つかった文字列を置き換える

**注意: XML には非選択モード側の設定値も保持されることがある**（GUI で
モードを切り替えても古いタグが残る）。したがって `ReplaceFoundField` タグが
存在するだけで Replace 処理へ入ってはならず、必ず `ReplaceMode` を主判定と
する。scaffold の Replace 分岐は `replace_mode == "Replace"` を条件に含める
ことで、分岐の評価順序に依存しない安全性を持たせている
（`test_scaffold_findreplace_stale_replace_found_field_is_ignored` で固定）。

anchor と config タグの対応関係:

- `Targets`（メインストリーム）⇔ `FieldFind` ⇔ helper の `targets_df`
- `Source`（ルックアップテーブル）⇔ `FieldSearch` ⇔ helper の `lookup_df`

（`e8121044` で実 Alteryx XML から確定し、`test_scaffold_findreplace_targets_source_anchors_route_correctly` で固定されている）

**用語の使い分け**: `Source` は Alteryx XML のアンカー名だが、一般的な
プログラミングの語感では source = 元データに読めて `Targets`（こちらが
元データ）と紛らわしいため、Python 側（helper の引数名・本ドキュメントの
説明文）では **lookup（ルックアップ表）** と呼ぶ。`Source` は XML・アンカー
そのものを指す文脈にだけ使う。

### 検証済みの意味論（golden 突合）

**含意の向き**: needle は `FieldSearch`（Source/ルックアップ側）の値で、
それが `FieldFind`（Targets/メイン側）の値に部分文字列として含まれるかで
判定される。実 Alteryx の golden 出力との突合で検証済み。

**採用規則と ReplaceMultipleFound の検証状態（統一モデル）**:

| 観点 | 規則 | 状態 |
|------|------|------|
| 重複する検索値 | 同じ検索値（FindWhole では同じキー）が複数の lookup 行にあるときは**後の行**が有効（辞書的上書き）。RMF 設定に依らない | **golden 突合で検証済み**（FindAny: apple×2 → 両設定とも後の行 / FindWhole: 同キー3行 → 両設定とも最後の行） |
| 採用マッチ（FindAny） | **開始位置が target 文字列中で最も左のマッチ**の検索値の行 — lookup 順ではなく、**RMF 設定にも依らない**。開始位置が同点なら lookup 順で**先の行**（検索値の長さは無関係） | **golden 突合で検証済み**（5行データ、apple/ppl による開始 vs 終了位置の判別、入れ子 app/apple の両並び順、RMF 両設定） |
| `ReplaceMultipleFound` | **Append モードでは FindAny・FindWhole とも True/False で出力差なし**（4種の golden × 両設定すべて同一）。Replace モード専用の設定である可能性が高い | **golden 突合で検証済み**（Replace モードでの意味は未実測 — 保留事項の Replace 項参照） |

FindWhole は完全一致でセル全体がマッチするため、「重複する検索値は後の行が
有効」の規則がそのまま重複キーに適用される — 検証済みの `keep="last"`
（RMF=True）はこのモデルと整合する。

初回の RMF=True（当時の解釈: lookup 順 last match）検証時の定量的な根拠:

| 条件 | cell_diff |
|------|-----------|
| 修正前の実装 | 779 |
| RMF=True（last match）として実装 | **22** |
| RMF=False（first match）として実装 | 363 |

この突合時点で残っていた 22 セルは、**その後 verify 側の対応付け
（重複 id・行の突き合わせ）の改善で解消済み**。当時の推定どおり
helper の意味論の誤りではなく、FindReplace 翻訳側の修正は不要だった。
上表の cell_diff は突合当時の値で、履歴のまま残している。

**その後の再解釈**: 後日の5行 golden（下記）により、検索値が異なる場合の
採用は「lookup 順で最後」ではなく **text 内の出現位置**で決まると判明し、
当時の「RMF=True = lookup 順 last」という解釈は覆った。位置ベースの新実装で
同じ実データ golden を再突合して diff 0 を確認済みで、そのデータでは新旧
どちらの規則でも同じ結果になっていた（統一モデルと過去 golden は矛盾しない）。

**採用規則（FindAny）の実測**: 5行の targets × apple/berry/cherry の
lookup（この並び順）を `ReplaceMultipleFound=False` と `True` の**両設定**で
実行した golden により、採用規則は「lookup 順で最初にマッチした行」でも
「最後」でもなく、**target 文字列中で最も左に現れた検索値**であることが
確定した。判別に効いた行:

| text | lookup 順 first なら | lookup 順 last なら | 実測（RMF=True / False とも同一） |
|------|---------------------|--------------------|------|
| cherry apple pie | A1（apple） | C3（cherry） | **C3** — text 先頭の cherry |
| berry cherry jam | B2（berry） | C3（cherry） | **B2** — text 先頭の berry |
| apple berry cherry mix | A1（apple） | C3（cherry） | **A1** — text 先頭の apple |

3行を同時に説明できるのは「text 内の出現位置が最も左」の規則だけ。さらに
**RMF=True でも出力が完全に同一**だったことから、この位置ベースの規則は
RMF 設定に依らないことも確定した（lookup 順 last なら3行とも C3 になる
はず）。この5行は `test_find_any_golden_leftmost_match_for_both_rmf_settings`
として両設定分を固定している。

**同位置タイ・重複・NoCase・空文字の実測**（いずれも RMF=True / False の
両設定で実行し、すべて同一出力）:

- **重複する検索値**（lookup: apple→X, apple→Y、target "apple pie"）:
  **Y（後の行）** — 辞書的上書き。RMF=False でも先の行には戻らない
  （`test_find_any_duplicate_needle_last_row_wins_regardless_of_rmf` で固定）
- **入れ子の検索値**（lookup: app→SHORT, apple→LONG、target "apple pie"）:
  **SHORT**。並び順を逆（apple→LONG, app→SHORT）にすると **LONG** — つまり
  勝敗を決めているのは検索値の長さではなく **lookup 順で先の行**
  （`test_find_any_same_start_earlier_lookup_row_wins`・
  `test_find_any_same_start_tie_reversed_order` で固定）
- **開始位置 vs 終了位置の判別**（lookup: apple→LONG, ppl→MID、target
  "apple pie" — ppl は後(位置1)から始まって先(位置4)に終わる）: **LONG** —
  採用を決めるのは**開始位置**で、終了位置モデル（先に完了するマッチ）なら
  MID になるはずだった（`test_find_any_leftmost_start_beats_earliest_end`
  で固定）
- **NoCase=True**: 大小無視でマッチし、採用規則も維持（"Cherry APPLE pie"
  → C3、"BERRY cherry jam" → B2、"Apple only" → A1）。生成コードの
  `case_sensitive=False` と一致
- **空文字・NULL の検索値**: 無視される（lookup に空文字行・NULL 行を
  入れても、どの target にもその label が付かない）。参照実装のスキップ
  挙動と一致（`test_find_any_nan_and_empty_needles_do_not_match` で固定）

FindReplace はモードに関係なく **1 target = 1 出力行** を保証するツールで、
ルックアップキーが重複していても行は増えない。この行数不変の保証が、
素の left join との決定的な違いになる。

### FindWhole の翻訳 — dedup + merge

素の left join は重複キーで行が増えるため、FindWhole でも merge の前に
lookup 側を `drop_duplicates(subset=[search_field], keep="last")` で重複排除
する。**残すのは常に最後の重複行**で、`ReplaceMultipleFound` には依らない。

**検証状態**: 同じキーを3行（append 値はそれぞれ別の値）入れた FindWhole
ワークフローを **RMF=True / False の両設定**で実行し、どちらも最後の行が
採用されることを golden 突合で確認済み（RMF=True 側は行・列・セルとも
diff 0、RMF=False 側も出力同一）。統一モデル（重複する検索値は後の行が
有効 = 辞書的上書き、RMF は Append モードでは出力に影響しない）の予測
どおりで、FindAny の重複検索値実測（apple×2 → 後の行）とも整合する。
かつて生成していた「keep は ReplaceMultipleFound に対応（False = first)」
という翻訳は実測で否定された。

**別名キー（FieldFind ≠ FieldSearch）の出力列 — FindAny と非対称**:
FindWhole では、**検索キー列（FieldSearch）が Append 対象に選択されていなくても
自動で出力に残る**（golden で実測 — 別名キーのワークフローで、Append に
チェックしていない FieldSearch 列が出力に現れた）。`pd.merge` は
`left_on`/`right_on` が別名のとき `right_on` の列をそのまま出力に残すので、
現在の翻訳がそのまま実 Alteryx と一致する（追加の drop は不要、入れては
いけない）。FindAny（検索値の列は出力に現れない）とは逆の挙動なので、
モード間の類推で「修正」しないこと。同名キーのときは `on=` になりキー列は
1本で、この非対称は表面化しない。

### FindAny + Append — scaffold が生成するコード

FindAny は等価結合では意味論を再現できない（`pd.merge` は完全一致しか
できない）ため、scaffold は参照実装の関数を呼び出す形に翻訳する:

```python
# Find Replace (FindAny) — substring lookup: each Source search value
# is matched inside the Targets find field
# NOTE: simulate_find_any_append() is not generated — copy it from
# reference_impl/simulate_find_any_append.py
df3 = simulate_find_any_append(
    df1,
    df2,
    find_field="key_a",
    search_field="key_b",
    append_fields=["col_a", "col_b"],
    case_sensitive=True,   # Alteryx の NoCase=False に対応
    log_label="ToolID 3",  # 実行ログにどのツールか表示される
)
```

`ReplaceMultipleFound` は生成コードに**出力しない**: Append モードでは
出力に影響しないことが golden で実測済みで、引数として出すと意味がある
ように見えてしまうため。helper 側の `replace_multiple_found` 引数は互換の
ため念のため残してあるが、判定には使われない。

**関数定義そのものは生成 .py に埋め込まない**（Select の
`apply_select_edits` / `SelectColumnEdit` も同方針で、参照実装は
`reference_impl/apply_select_edits.py`）。`reference_impl/` の参照実装をプロジェクトへ
コピーして使う。挙動は `tests/test_reference_scripts.py` で固定されている。
参照実装は以下を処理済み:

- **出力列は「元の Targets 列 + append_fields」のみ** — 検索値
  （`FieldSearch`）の列は照合に使うだけで出力に残さない。実 Alteryx の
  golden 出力との突合（行・列・セルとも diff 0）で検証済み
  （詳細は後述「出力列と FieldFind == FieldSearch」）
- **1 target = 1 出力行** — FindReplace は join ではないので、複数の
  lookup 行にマッチしても行は増えない。採用されるのは開始位置が最も左の
  マッチの検索値の行（同点は lookup 順で先の行。RMF に依らず・golden 検証済み）。
  同じ検索値の重複行は後の行が有効（辞書的上書き・golden 検証済み）
- **NaN の誤マッチ防止** — `astype(str)` だと NaN が `"nan"` になり誤マッチ
  するため、NaN は判定から除外する
- **空文字 needle の除外** — `"" in "ABC-123"` は `True` なので、空文字の
  検索値は全行マッチになる前に弾く（実 Alteryx も空文字・NULL の検索値を
  無視することを golden で実測済み）
- **float64 昇格による表記ずれ** — NaN 混在で整数列が float64 に昇格すると
  `123` が `"123.0"` になり文字列比較がすれ違うため、整数値 float は
  `".0"` を落として文字列化する

FindAny + `ReplaceMode=Replace`（見つかった部分文字列の置換）は未対応。
silent skip ではなく、**未対応の組み合わせ（FindMode / ReplaceMode の両方）を
明記した TODO コメント + 入力パススルー**を生成する:

```python
# TODO: Find Replace — FindMode='FindAny', ReplaceMode='Replace'
# is not translated; input passed through unchanged
df3 = df1
```

「翻訳できません」と「翻訳し忘れました」をレビューする人間が区別できるように
するための措置。

### 出力列と FieldFind == FieldSearch（同名キー）

参照実装の出力は **「元の Targets 列 + append_fields」のみ**。検索キー
（`FieldSearch` / matched_needle）は照合に使うだけで出力には残さない。
**実 Alteryx の Append 出力でも検索値の列は現れない**ことは、golden 出力との
突合（同名キー・別名キーの両ケースで行・列・セルとも diff 0）で検証済み
（Append モードは「追加するフィールドを選択する」もので、検索値の列が
自動追加されるとは公式にも書かれていない）。**これは FindAny の挙動**で、
FindWhole は逆に検索キー列が自動で出力に残る（前述「FindWhole の翻訳」の
別名キーの項参照）。matched_needle と `_lookup_row_id`
はデバッグに有用なので計算自体は残し、`verbose` のログ表示だけで使う。

このため、ルックアップキーで探すワークフローで XML の `FieldFind`（Targets 側）と
`FieldSearch`（Source 側）に**同じ列名**が入っても衝突しない — 検索値の列を
出力に足さないので、キー列が重複しようがないからだ。scaffold は
同名かどうかに関わらず素直に `search_field=<FieldSearch>` を渡す:

```python
# Find Replace (FindAny) — substring lookup: each Source search value
# is matched inside the Targets find field
# NOTE: simulate_find_any_append() is not generated — copy it from
# reference_impl/simulate_find_any_append.py
df3 = simulate_find_any_append(
    df1,
    df2,
    find_field="key",
    search_field="key",
    append_fields=["col_a", "col_b"],
    case_sensitive=True,
    log_label="ToolID 3",
)
```

役割分担は次のとおり:

- **scaffold** — Alteryx XML を読む側。FindMode / ReplaceMode の判定・
  設定タグの読み取りが責務。出力に検索値の列を足さない設計になったので、
  同名キー用の一時 rename → drop は生成しない
- **helper 単体** — **Alteryx XML を解釈しない**。整形済みの DataFrame と
  引数だけを受け取る。**append_fields** の列が Targets 側に同名で既にあると
  （2つの df で同名列は共存できないため）黙って上書きせず `ValueError` で
  止め、rename の対処方法をエラーメッセージで案内する。`search_field` は
  出力に足さないので衝突チェックの対象外

### 未検証・保留事項（golden で確定したら消し込む）

実 Alteryx の golden 出力との突合で確定していない項目の一覧。
**このチェックリストが正本**であり、ロードマップ等の他ドキュメントは
本節を参照する（重複管理しない）。確定したら該当行を消し、関係する
コード側の NOTE・テストも合わせて更新する。

以降の項目は**コード変更のタスクではなく、実 Alteryx で仕様を確定するための
チェックリスト**である。翻訳の実装が未完成という意味ではない。

- [ ] **FindWhole + Replace / FindAny + Replace の実挙動** — Replace モード時の
  `ReplaceFoundField` の適用のされ方（部分置換の範囲・複数マッチ時の挙動）は
  未実測。Replace モードのワークフローを golden 突合に足してから対応範囲を
  広げる

### 設計上の保留（golden 検証とは別軸の判断）

以下は仕様の問題ではなく設計判断であり、上記の golden 検証が済んでから
着手する（仕様が動いている間に API を変えない）:

- **append 値の型保持** — 現在の参照実装は golden CSV 比較のしやすさを優先し、
  append 値を `_stringify` で文字列化している（`123` → `"123"`、型は失われる）。
  将来的には helper は元の型を保持し、比較処理側でのみ正規化する形へ分離する
- **デバッグ列の分離**（対応済み）— 戻り値は「元の Targets 列 + append_fields」
  のみにし、`_target_row_id`・`_lookup_row_id`・matched_needle は出力に混ぜず、
  `verbose` 時に別 DataFrame へまとめてログ表示だけで使う形に分離済み。
  もし将来デバッグ列を戻り値でも受け取りたくなったら `include_debug_columns`
  フラグ等で明示的に切り替える
- **helper API の整理** — 上記の型保持を含む API 変更は、未検証・保留事項の
  消し込みが進んでから一括で判断する

---

## 16. Filter 複合条件のマスク分割と、レビュー時の `fillna("")` 整理

Expression モードの Filter でトップレベルが AND/OR 連鎖の場合、scaffold は条件を
`cond_1`, `cond_2`, … の名前付きマスクに分割して出力する（オペランド3個以上、
または2個で1行版が88桁を超えるとき）。各マスクには元の Alteryx 式フラグメントが
コメントで添えられる。

```python
# !Contains([Status], "drop")
cond_1 = ~df1["Status"].str.contains('drop', case=False, regex=False, na=False)
# !IsEmpty([Status])
cond_2 = ~(df1["Status"].isna() | (df1["Status"] == ""))

df2 = df1[cond_1 & cond_2]
```

これは同じ式の「見せ方」の変更であり、変換そのものは変えていない。

### レビュー時に人間が整理してよいパターン: `fillna("")` による NULL/空文字の一本化

文字列列だと分かっているなら、レビューで次のように書き換えると読みやすくなる。

```python
status = df1["Status"].fillna("")
is_drop = status.str.contains("drop", case=False, regex=False)
is_empty = status.eq("")

df2 = df1[~is_drop & ~is_empty]
```

**scaffold はこの形を生成しない。** 理由:

1. `fillna("")` は文字列列でしか成立しない型依存の書き換えで、翻訳ツールは列の型を
   知らないまま適用することになる。
2. Alteryx 側で `IsNull()` と `IsEmpty()` を使い分けているワークフローでは、その
   区別自体が作者の意図かもしれない。翻訳機が勝手に潰すのは忠実な翻訳に反する。
3. 「構文ごとの忠実な翻訳 + review translation コメントで人間がレビュー」が scaffold
   の方針。一本化してよいかの判断はレビューする人間の責任範囲。

意味のある名前（`is_drop` など）を付けて否定 `~` を結合行に残すのも同じくレビュー時の
整理。`is_drop = ~(...)` のような「名前と中身が逆」の定義は事故のもとなので、semantic
名を使うならマスクは肯定形で定義する。

---

## 17. 日付比較と `IsEmpty()` が同じ列に混在する場合の落とし穴

CSV 由来の列は pandas 上ではすべて文字列（object/str dtype）で読み込まれる。
同じ列が Filter 式の中で「日付として比較」されつつ「`IsEmpty()` で空判定」も
されている場合、変換前・変換後のどちらのタイミングでも問題が起きる。

| タイミング | 挙動 |
|---|---|
| 変換前（文字列のまま）で日付比較 | `[date_col] >= ToDate(...)` は文字列 vs Timestamp の比較になり実行時エラー |
| 変換後（`pd.to_datetime(..., errors="coerce")`） | `IsEmpty` の `== ""` 側が常に `False` になり無意味化（エラーにはならず黙って死ぬ） |

実測（pandas 3.0.3）:

```python
# 変換前に日付比較すると即エラー
pd.Series(["2024-01-01", ""]) >= pd.Timestamp("2024-01-01")
# TypeError: '<=' not supported between instances of 'Timestamp' and 'str'

# 変換後は IsEmpty の == "" が常に False（NaT は isna() 側だけが拾う）
conv = pd.to_datetime(pd.Series(["2024-01-01", "", "2023-05-05"]), errors="coerce")
conv == ""   # → [False, False, False]
```

つまり: WARNING を無視すれば即クラッシュ、WARNING に従って変換すれば別の条件が
黙って死ぬ。どちらのタイミングでも気づきにくい。

### scaffold の対応

同じ列が日付比較と `IsEmpty()` の両方に使われている場合、scaffold は列名を
名指しした WARNING/NOTE を追加で生成する。

```python
# WARNING: column "date_col" is compared as a date in cond_2 — convert first:
# df["date_col"] = pd.to_datetime(df["date_col"], errors="coerce")
# NOTE: after conversion, IsEmpty's == "" check on "date_col" always
# evaluates False — isna() alone is enough (it also catches NaT).
```

日付比較の相手が別の列（`[date_col] >= [other_date_col]` のような列同士の比較）
の場合、`other_date_col` 側は「日付として扱われている」と断定はできないため、
`(mask-level heuristic)` と明記した緩い警告になる。

### `IsNull()` は対象外

`IsNull([col])` は `.isna()` のみに翻訳されるため、日付変換後も NaT を正しく
拾い続け、意味は壊れない。この WARNING/NOTE が付くのは `IsEmpty()` のみ。

---

## 18. 空間ツール — SpatialObj は「見えない列」

Create Points は Longitude/Latitude から SpatialObj 型の `Centroid` フィールドを
出力ストリームに追加する。下流の Spatial Match はこのフィールドを
`<Target SpatialObj="Centroid"/>` のように**名前で**参照するので、ストリーム上に
実在するデータ列である。

ただし SpatialObj は通常の文字列・数値列と扱いが違い、Designer の Results
グリッドには表示されない（Browse では追加の **Map タブ**に描画される）。
golden CSV にも空間列は現れない。一方 geopandas は空間オブジェクトを明示的な
DataFrame 列（デフォルト名 `geometry`）として保持するため、生成コードを
実行すると「golden にない列が増えた」ように見える。

```text
Alteryx の内部ストリーム              pandas（GeoDataFrame）
├─ EL_ID                              ├─ EL_ID
├─ Longitude                          ├─ Longitude
├─ Latitude                           ├─ Latitude
└─ Centroid ← SpatialObj型。          └─ geometry ← 明示的な列として
    グリッド/CSV に出ない                  常に見える
```

### golden 比較時の扱い

`geometry` は作業列ではなくツール本体の出力（Alteryx の `Centroid` 相当）なので、
**生成コード側で削除してはいけない** — 下流の Spatial Match（`gpd.sjoin`）が
アクティブジオメトリとして使う。除外するのは比較処理側:

```python
actual = pd.DataFrame(gdf.drop(columns=gdf.geometry.name))
```

scaffold が生成する Create Points コードには、この旨の NOTE コメントが付く
（「golden CSV には現れない列なので比較側で drop せよ」）。

### 未検証（golden で確定したら消し込む）

- [ ] **Alteryx が SpatialObj を CSV 出力するときの挙動** — 列ごと書かないのか、
  空文字/文字列化で書くのか未実測。比較スクリプトが golden 側の列集合を
  どう想定すべきかに効く。Results グリッドに表示されないことは実測済み。

### 設計上の保留 — `rename_geometry("Centroid")` は条件付き保留

現在の生成コードは列名を geopandas デフォルトの `geometry` のままにしている。
`gen_spatialmatch` はアクティブジオメトリ任せの `gpd.sjoin` を生成するため、
**1ストリーム1空間列の間は列名が何であっても動く**（Target 側は Create Points
が作った点、Universe 側は `gpd.read_file(.shp)` の `geometry` が、それぞれ
自然に正しいアクティブジオメトリになる）。rename しても golden との列差分は
解決しない（golden には空間列自体が見えないため）。

rename が必要になるトリガーは **1つのストリームに空間列が複数ある場合**
（例: Universe 側にも Create Points 由来の列があり、`Target/@SpatialObj`・
`Universe/@SpatialObj` の名前参照を再現する必要が出たとき）。該当ケースが
golden 突合に現れたら、`rename_geometry("Centroid")` と config の SpatialObj
属性読み取り（`gen_spatialmatch`）をセットで実装する。

### 埋め込み SelectConfiguration — 逸脱警告まで実装、本翻訳は golden 待ち

Spatial Match の埋め込み SelectConfiguration（`Target_`/`Universe_`
プレフィックス付与＋列選択）に対して、`gen_spatialmatch` は現在ここまで行う:

1. **`index_right` の drop** — `gpd.sjoin` の人工列で Alteryx 出力に対応物が
   ないため、生成コード側で無条件に `.drop(columns=["index_right"])` する。
2. **逸脱時の WARNING コメント** — Matched 出力の埋め込み Select が
   デフォルト状態（全 selected・rename/type なし）から逸脱している場合のみ、
   逸脱内容（deselected / renamed / type changed）を列挙する。
   デフォルト構成なら何も出さない。

実行可能な `SelectColumnEdit` への翻訳は**意図的に保留**している。埋め込み
Select の `field` は入力プレフィックス込みの作業名（`Target_ID`）だが、
`gpd.sjoin` の出力列は生の名前＋衝突時 `_left`/`_right` サフィックスで、
名前が一致しない。`apply_select_edits` は存在しない列を黙って無視する設計
（stale XML 対策）なので、XML の名前で edit を機械生成すると **silent no-op**
になる — 「出したのに効かない」は「出さない」より悪い。名前対応が golden
突合で確定したら、Join の SelectConfiguration（同型・同じく未翻訳）と
共通ヘルパー化して実装する。

Spatial Match 以降の golden 突合では列名の食い違い（プレフィックス vs
サフィックス）を前提にレビューすること。

### CRS — 空間読み込み直後に WGS84 へ正規化（実装済み）

Alteryx は SpatialObj を**常に WGS84** で保持し、投影付きファイルは入力時に
変換する。一方 geopandas では `.prj` サイドカーの無い `.shp` が CRS None の
まま読まれ、Create Points 側（scaffold が `crs="EPSG:4326"` を付与）と
`gpd.sjoin` した時点で CRS mismatch の UserWarning が出る（警告のまま
生座標で計算は走る — 実体が経緯度なら結果は合うが保証がない）。

scaffold はこの不変条件を読み込み側で写す: 空間ファイルの読み込み直後に
「CRS None なら `set_crs("EPSG:4326")`（WGS84 とみなす）、付いていれば
`to_crs("EPSG:4326")`（Alteryx の入力時変換の再現）」を生成する。
以降の空間ツールは混在 CRS を見ない前提でよい。
CRS None 分岐は「4326 と仮定した」ことを `logger.warning` で実行ログに残す
（元データが別座標系だった場合に結果が静かに狂う仮定のため）。
設計全体は [spatial-crs-design.md](spatial-crs-design.md) を参照。

### Shapefile のサイドカー — .dbf が無いと属性列が静かに消える（ガード実装済み）

.shp の属性列（MESHCODE 等）は本体ではなく**同名の .dbf サイドカー**に
入っている。Alteryx も GeoPandas も、.shp を1個指定すれば同フォルダの
同名サイドカーを自動で読むので、一式が揃っていれば挙動差はない。

差が出るのは欠落時の挙動である。GDAL は .dbf を任意扱いで、無くても
**エラーを出さず geometry 1列だけで開く**。さらに scaffold が Alteryx
パリティのために出す `SHAPE_RESTORE_SHX=YES` は .shp 単体すら黙って
開けてしまう。「.shp だけ別フォルダにコピーした」状態でも警告ゼロで
`gpd.sjoin` まで到達し、universe 側の属性列が結果に乗らない — という
事故が実際に起きた。

scaffold は .shp 読み込みの直前に .dbf 存在チェック
（欠落時 `FileNotFoundError`、`.dbf`/`.DBF` 両対応）を生成する。
調査の経緯・検証表・採用しなかった対案は
[shapefile-sidecar-anatomy.md](shapefile-sidecar-anatomy.md) を参照。

---

## まとめ: 変換レビューのチェックポイント

| Alteryx の挙動 | 移植時に確認すること |
|----------------|----------------------|
| `Contains(col, val)` | `case=False`、`re.escape()` または `regex=False`、`na=False` |
| `IsEmpty(col)` | `isna() \| (== "")` の両建て |
| `and` / `or` / `!` / `=` | `&` / `\|` / `~` / `==` への置換、各条件を `()` で囲む |
| `|` を含む複合 NOT 条件 | `~` > `&` > `\|` の優先順位に注意。OR 右辺で NOT が外れていないか確認 |
| 空白のみのセルを空扱いにしたい | `str.strip()` を前置 |
| Join の L / R 出力を使っている | `how='outer', indicator=True` で分岐 |
| Filter の F 出力を使っている | `~mask` で明示抽出 |
| Union が ByPosition モード | 列名を揃えてから `concat` |
| Sort に NULL が含まれる | `na_position='first'` |
| Summarize に NULL グループがある | `groupby(..., dropna=False)` |
| DataCleansing の "Rename Fields" | `df.columns = df.columns.str.strip()` |
| `Substring(col, start, length)` | 0-indexed。`str[start:start+length]`（`-1` 補正は不要） |
| `DateTimeAdd(dt, n, "unit")` | `dt + pd.DateOffset(unit=n)` |
| `ToDate(val)` | `pd.to_datetime(val)` |
| FindReplace FindWhole + 重複キー lookup | merge 前に `drop_duplicates(keep=RMF対応)` — 素の left join だと行が増える |
| FindReplace FindAny + Append | `simulate_find_any_append(...)` の呼び出しに変換（定義は生成されない — `reference_impl/simulate_find_any_append.py` をコピー） |
| FindReplace の ReplaceMultipleFound | 読まない・生成コードに出さない — Append モードでは出力に影響しないことが golden 実測で確定（出すと意味があるように見えるため） |
| 空間ファイル読み込み（.shp 等） | 読み込み直後に WGS84 へ正規化（CRS None は warning 付き `set_crs`、その他は `to_crs`）— scaffold が自動生成。`.prj` 欠落 .shp × Create Points の sjoin で出る CRS mismatch 警告の恒久対策 |
| .shp の属性列が geometry しか無い | 同名 `.dbf` サイドカーが同フォルダに無い（GDAL は無音で geometry のみ開く）。scaffold 生成の存在チェックが `FileNotFoundError` で検知 — ファイル一式を揃える |
| FindReplace の NoCase | ヘルパーの `case_sensitive` に反転して渡される（NoCase=True → case_sensitive=False） |
| 日付比較と `IsEmpty()` が同じ列に混在 | 変換前は日付比較がエラー、変換後は `IsEmpty` の `== ""` が常に False。scaffold の列名付き WARNING/NOTE を確認（`IsNull` は対象外） |
| Create Points / Spatial Match の SpatialObj | geopandas では明示的な `geometry` 列になる（Alteryx では Map タブのみ、通常グリッド/CSV に出ない）。golden 比較前に比較側で drop — 生成コード側では消さない |
| Spatial Match の出力列 | `index_right`（sjoin の人工列）は生成コードが drop 済み。埋め込み Select の逸脱（deselected / rename / type）は WARNING コメントで列挙のみ — 列名の食い違い（XML は `Target_`/`Universe_` プレフィックス、sjoin は `_left`/`_right` サフィックス）を前提に手動で整合させる |

---

## 関連実装

- `reference_impl/simulate_find_any_append.py` — FindAny + Append の参照実装（golden 突合済み）
- `reference_impl/apply_select_edits.py` — Select ツールヘルパーの参照実装（drop / 型変換 / rename）
- `src/yxray/tool_registry.py` — 各ツールの python_hint と `_FILTER_HINT`
- `src/yxray/scaffold/` — 領域ごとの生成モジュール(構成は `docs/scaffold-architecture.md`)。`_combine.py` の `gen_join`（inner のみ生成）/ `gen_union`（ByName 固定）、`_filter.py` の `gen_filter`（複合条件のマスク分割）/ `_filter_date_warning_lines`（日付比較 × `IsEmpty` の列名付き警告）、`_spatial.py` の `gen_createpoints`（`geometry` 列の NOTE 付き生成）/ `gen_spatialmatch`（アクティブジオメトリ任せの `sjoin` + `index_right` drop + 埋め込み Select 逸脱の WARNING）
- `src/yxray/alteryx_expr.py` — `translate_filter_masks`（トップレベル AND/OR のオペランド分解）
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint
