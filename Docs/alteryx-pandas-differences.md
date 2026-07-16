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

**ReplaceMultipleFound（FindAny + Append）の検証状態**:

| 設定 | 採用規則 | 状態 |
|------|---------|------|
| `RMF=True` | last match（lookup 表の並び順で最後にマッチした行） | **golden 突合で検証済み** |
| `RMF=False` | first match（lookup 表の並び順で最初にマッチした行） | **推定・未検証**（下記の保留事項参照） |

以降、本章で「検証済み」と書くときは **RMF=True 側のみ**を指す。
定量的な根拠:

| 条件 | cell_diff |
|------|-----------|
| 修正前の実装 | 779 |
| RMF=True（last match）として実装 | **22** |
| RMF=False（first match）として実装 | 363 |

この突合時点で残っていた 22 セルは、**その後 verify 側の対応付け
（重複 id・行の突き合わせ）の改善で解消済み**。当時の推定どおり
helper の意味論の誤りではなく、FindReplace 翻訳側の修正は不要だった。
上表の cell_diff は突合当時の値で、「RMF=True = last match」という
結論の根拠として履歴のまま残している。

**上記の検証がカバーする範囲**: 比較対象はいずれも「RMF=True 設定の
golden」であり、`RMF=False` を Alteryx 側で設定した golden との突合ではない
（cell_diff 363 は「False 実装が True の golden に合わない」ことの確認で
あって、False 側の検証ではない）。コード・docstring では
「True=last は検証済み / False=first は推定」を書き分けること。

FindReplace はモードに関係なく **1 target = 1 出力行** を保証するツールで、
ルックアップキーが重複していても行は増えない。この行数不変の保証が、
素の left join との決定的な違いになる。

### FindWhole の翻訳 — dedup + merge（keep は類推）

素の left join は重複キーで行が増えるため、FindWhole でも merge の前に
lookup 側を `drop_duplicates(subset=[search_field], keep=...)` で重複排除する。
どの重複を残すかは `ReplaceMultipleFound` に対応させる
（True = `keep="last"` / False = `keep="first"`）。

**注意: この keep 対応は FindAny の golden 検証結果（RMF=True = last match）
からの類推で、FindWhole モード自体は実 Alteryx の golden 出力で未検証**。
golden 突合に「FindWhole + 重複キー lookup」のケースを足して確定させること。
もし逆だった場合、直すのは `scaffold.py` の
`keep = "last" if replace_multiple_found else "first"` の1行だけ。

### FindAny + Append — scaffold が生成するコード

FindAny は等価結合では意味論を再現できない（`pd.merge` は完全一致しか
できない）ため、scaffold は参照実装の関数を呼び出す形に翻訳する:

```python
# Find Replace (FindAny) — substring lookup: each Source search value
# is matched inside the Targets find field
# NOTE: simulate_find_any_append() is not generated — copy it from
# scripts/simulate_find_any_append.py
df3 = simulate_find_any_append(
    df1,
    df2,
    find_field="key_a",
    search_field="key_b",
    append_fields=["col_a", "col_b"],
    case_sensitive=True,          # Alteryx の NoCase=False に対応
    replace_multiple_found=True,  # Alteryx の ReplaceMultipleFound
    log_label="ToolID 3",         # 実行ログにどのツールか表示される
)
```

**関数定義そのものは生成 .py に埋め込まない**（Select の
`apply_select_edits` / `SelectColumnEdit` も同方針で、参照実装は
`scripts/apply_select_edits.py`）。`scripts/` の参照実装をプロジェクトへ
コピーして使う。挙動は `tests/test_reference_scripts.py` で固定されている。
参照実装は以下を処理済み:

- **出力列は「元の Targets 列 + append_fields」のみ** — 検索値
  （`FieldSearch`）の列は照合に使うだけで出力に残さない。実 Alteryx の
  golden 出力との突合（行・列・セルとも diff 0）で検証済み
  （詳細は後述「出力列と FieldFind == FieldSearch」）
- **1 target = 1 出力行** — FindReplace は join ではないので、複数の
  lookup 行にマッチしても行は増えない。どの行の値を採用するかは
  `ReplaceMultipleFound` で決まる（True=last match は検証済み /
  False=first match は推定）
- **NaN の誤マッチ防止** — `astype(str)` だと NaN が `"nan"` になり誤マッチ
  するため、NaN は判定から除外する
- **空文字 needle の除外** — `"" in "ABC-123"` は `True` なので、空文字の
  検索値は全行マッチになる前に弾く（Alteryx の実挙動との一致は未実測。
  下記の保留事項参照）
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
自動追加されるとは公式にも書かれていない）。matched_needle と `_lookup_row_id`
はデバッグに有用なので計算自体は残し、`verbose` のログ表示だけで使う。

このため、ルックアップキーで探すワークフローで XML の `FieldFind`（Targets 側）と
`FieldSearch`（Source 側）に**同じ列名**が入っても衝突しない — 検索値の列を
出力に足さないので、キー列が重複しようがないからだ。scaffold は
同名かどうかに関わらず素直に `search_field=<FieldSearch>` を渡す:

```python
# Find Replace (FindAny) — substring lookup: each Source search value
# is matched inside the Targets find field
# NOTE: simulate_find_any_append() is not generated — copy it from
# scripts/simulate_find_any_append.py
df3 = simulate_find_any_append(
    df1,
    df2,
    find_field="key",
    search_field="key",
    append_fields=["col_a", "col_b"],
    case_sensitive=True,
    replace_multiple_found=True,
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

- [ ] **FindWhole + 重複キー lookup** — `ReplaceMultipleFound=True` で本当に
  last が勝つか。現在の `drop_duplicates(keep="last")` は FindAny の golden
  結果からの類推。lookup 表に同じキーを2行（値違い）入れた FindWhole
  ワークフローで、①行数が増えないこと ②後の行が採用されること を実測する。
  確定したら `scaffold.py` の keep 行のコメント・生成コードの NOTE・
  `test_scaffold_findreplace_append_mode_left_join` の NOTE アサーションを更新
  （逆だった場合は `keep = "last" if replace_multiple_found else "first"` の
  1行を直す）
- [ ] **RMF=False（first match）** — 現在の golden 突合は RMF=True 設定の
  出力に対する比較のみ（cell_diff 363 は「False 実装が True の golden に
  合わない」ことの確認であり、False 側の検証ではない）。Alteryx 側を
  `ReplaceMultipleFound=False` に設定した golden を追加し、first match 採用を
  実測する。確定したら helper docstring の「推定」表記を更新する
- [ ] **NoCase=True（大文字小文字無視）** — golden 突合に case-insensitive の
  ケースが含まれていたか確認。なければ追加する
- [ ] **空文字の検索値** — 参照実装（`scripts/simulate_find_any_append.py`）は
  空文字 needle をスキップするが、Alteryx の実挙動（全行マッチ / 無視）は
  未実測。lookup 表に空文字行を含む golden で一致を確認する。それまでは現状の
  スキップ挙動をテストで固定し（`test_find_any_nan_and_empty_needles_do_not_match`）、
  検証時の比較基準とする
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
`_gen_spatialmatch` はアクティブジオメトリ任せの `gpd.sjoin` を生成するため、
**1ストリーム1空間列の間は列名が何であっても動く**（Target 側は Create Points
が作った点、Universe 側は `gpd.read_file(.shp)` の `geometry` が、それぞれ
自然に正しいアクティブジオメトリになる）。rename しても golden との列差分は
解決しない（golden には空間列自体が見えないため）。

rename が必要になるトリガーは **1つのストリームに空間列が複数ある場合**
（例: Universe 側にも Create Points 由来の列があり、`Target/@SpatialObj`・
`Universe/@SpatialObj` の名前参照を再現する必要が出たとき）。該当ケースが
golden 突合に現れたら、`rename_geometry("Centroid")` と config の SpatialObj
属性読み取り（`_gen_spatialmatch`）をセットで実装する。

なお Spatial Match の埋め込み SelectConfiguration（`Target_`/`Universe_`
プレフィックス付与＋列選択）も未翻訳で、`gpd.sjoin` の命名規則
（衝突列に `_left`/`_right` サフィックス、`index_right` 追加）とは一致しない。
Spatial Match 以降の golden 突合では列名の食い違いを前提にレビューすること。

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
| FindReplace FindAny + Append | `simulate_find_any_append(...)` の呼び出しに変換（定義は生成されない — `scripts/simulate_find_any_append.py` をコピー） |
| FindReplace FindAny + ReplaceMultipleFound | ヘルパーの `replace_multiple_found` フラグに変換（True=last match / False=first match） |
| FindReplace の NoCase | ヘルパーの `case_sensitive` に反転して渡される（NoCase=True → case_sensitive=False） |
| 日付比較と `IsEmpty()` が同じ列に混在 | 変換前は日付比較がエラー、変換後は `IsEmpty` の `== ""` が常に False。scaffold の列名付き WARNING/NOTE を確認（`IsNull` は対象外） |
| Create Points / Spatial Match の SpatialObj | geopandas では明示的な `geometry` 列になる（Alteryx では Map タブのみ、通常グリッド/CSV に出ない）。golden 比較前に比較側で drop — 生成コード側では消さない |

---

## 関連実装

- `scripts/simulate_find_any_append.py` — FindAny + Append の参照実装（golden 突合済み）
- `scripts/apply_select_edits.py` — Select ツールヘルパーの参照実装（drop / 型変換 / rename）
- `src/yxray/tool_registry.py` — 各ツールの python_hint と `_FILTER_HINT`
- `src/yxray/scaffold.py` — `_gen_join`（inner のみ生成）、`_gen_union`（ByName 固定）、`_gen_filter`（複合条件のマスク分割）、`_filter_date_warning_lines`（日付比較 × `IsEmpty` の列名付き警告）、`_gen_createpoints`（`geometry` 列の NOTE 付き生成）、`_gen_spatialmatch`（アクティブジオメトリ任せの `sjoin`）
- `src/yxray/alteryx_expr.py` — `translate_filter_masks`（トップレベル AND/OR のオペランド分解）
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint
