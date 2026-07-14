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

## 15. `FindReplace`（FindAny モード）— 部分一致ルックアップ

Alteryx の **FindReplace ツール**には `FindWhole`（完全一致）と `FindAny`（部分一致）の2モードがある。

| モード | 挙動 | scaffold の翻訳 |
|--------|------|-----------------|
| **FindWhole** | FieldFind の値が FieldSearch に完全一致する行を結合 | source を `drop_duplicates(keep=...)` してから `pd.merge(how="left")` |
| **FindAny** | 部分一致（Source の検索値が Targets のフィールドに部分文字列として含まれる） | `simulate_find_any_append(...)` の呼び出しを生成（定義は生成しない） |

FindReplace はモードに関係なく **1 target = 1 出力行** を保証するツールで、
ルックアップキーが重複していても行は増えない。素の left join は重複キーで
行が増えるため、FindWhole でも merge の前に source 側を
`drop_duplicates(subset=[search_field], keep=...)` で重複排除する。
どの重複を残すかは `ReplaceMultipleFound` に対応させる
（True = `keep="last"` / False = `keep="first"`。FindAny ヘルパーの
last/first match と同じ対応）。

anchor と config タグの対応関係:

- `Targets`（メインストリーム）⇔ `FieldFind`
- `Source`（ルックアップテーブル）⇔ `FieldSearch`

（`e8121044` で実 Alteryx XML から確定し、`test_scaffold_findreplace_targets_source_anchors_route_correctly` で固定されている）

**含意の向きは実 Alteryx の golden 出力との突合で検証済み**: needle は
`FieldSearch`（Source/ルックアップ側）の値で、それが `FieldFind`
（Targets/メイン側）の値に部分文字列として含まれるかで判定される。
この意味論を pandas で忠実に再現した参照実装が py-tools の
`scripts/simulate_find_any_append.py`（golden 突合済み）。

### scaffold が生成するコード

FindAny + `ReplaceMode=Append` は、等価結合では意味論を再現できない
（`pd.merge` は完全一致しかできない）ため、scaffold は参照実装の関数を
呼び出す形に翻訳する:

```python
# Find Replace (FindAny) — substring lookup: each Source search value
# is matched inside the Targets find field
# NOTE: simulate_find_any_append() is not generated — provide the
# helper separately
df3 = simulate_find_any_append(
    df1,
    df2,
    find_field="key_a",
    search_field="key_b",
    append_fields=["col_a", "col_b"],
    case_sensitive=True,          # Alteryx の NoCase=False に対応
    replace_multiple_found=True,  # Alteryx の ReplaceMultipleFound
)
```

**関数定義そのものは生成 .py に埋め込まない**（Select の
`apply_select_edits` / `SelectColumnEdit` も同方針）。参照実装を
プロジェクトへコピーして使う。参照実装は以下を処理済み:

- **1 target = 1 出力行** — FindReplace は join ではないので、複数の
  source 行にマッチしても行は増えない。どの行の値を採用するかは
  `ReplaceMultipleFound` で決まる（True=last match / False=first match）
- **NaN の誤マッチ防止** — `astype(str)` だと NaN が `"nan"` になり誤マッチ
  するため、NaN は判定から除外する
- **空文字 needle の除外** — `"" in "ABC-123"` は `True` なので、空文字の
  検索値は全行マッチになる前に弾く
- **float64 昇格による表記ずれ** — NaN 混在で整数列が float64 に昇格すると
  `123` が `"123.0"` になり文字列比較がすれ違うため、整数値 float は
  `".0"` を落として文字列化する

FindAny + `ReplaceMode=Replace`（見つかった部分文字列の置換）は未対応で、
従来どおり TODO コメントにフォールバックする。

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
| FindReplace FindWhole + 重複キー source | merge 前に `drop_duplicates(keep=RMF対応)` — 素の left join だと行が増える |
| FindReplace FindAny + Append | `simulate_find_any_append(...)` の呼び出しに変換（定義は生成されない — 参照実装をコピーする） |
| FindReplace FindAny + ReplaceMultipleFound | ヘルパーの `replace_multiple_found` フラグに変換（True=last match / False=first match） |
| FindReplace の NoCase | ヘルパーの `case_sensitive` に反転して渡される（NoCase=True → case_sensitive=False） |
| 日付比較と `IsEmpty()` が同じ列に混在 | 変換前は日付比較がエラー、変換後は `IsEmpty` の `== ""` が常に False。scaffold の列名付き WARNING/NOTE を確認（`IsNull` は対象外） |

---

## 関連実装

- `src/yxray/tool_registry.py` — 各ツールの python_hint と `_FILTER_HINT`
- `src/yxray/scaffold.py` — `_gen_join`（inner のみ生成）、`_gen_union`（ByName 固定）、`_gen_filter`（複合条件のマスク分割）、`_filter_date_warning_lines`（日付比較 × `IsEmpty` の列名付き警告）
- `src/yxray/alteryx_expr.py` — `translate_filter_masks`（トップレベル AND/OR のオペランド分解）
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint
