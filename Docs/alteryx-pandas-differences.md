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
| **FindWhole** | FieldFind の値が FieldSearch に完全一致する行を結合 | `pd.merge(how="left")` |
| **FindAny** | 部分一致（含意の向きは未検証。下記参照） | `pd.merge(how="left")`（※意味論的差異あり） |

FindAny は本来「部分一致（substring）ジョイン」だが、ID ベースのジョインでは実質的に完全一致と同等になる場合が多い。scaffold は `pd.merge` に変換し、NOTEコメントで意味論の確認を促す。

**含意の向き（どちらの値がどちらに含まれるか）は repo 内では未検証**。確認できているのは anchor と config タグの対応関係だけ。

- `Targets`（メインストリーム）⇔ `FieldFind`
- `Source`（ルックアップテーブル）⇔ `FieldSearch`

（`e8121044` で実 Alteryx XML から確定し、`test_scaffold_findreplace_targets_source_anchors_route_correctly` で固定されている）

一般的な Find & Replace 系ツールの UI 挙動（ルックアップ側が「探す値」を供給し、メイン側フィールドの中を検索する）に従うなら、含意は「FieldSearch（ルックアップ側）の値が FieldFind（メイン側）に含まれる」になるはずだが、**この向き自体は実 Alteryx の出力で確認したものではない**。以下のコード例はこの推定に従っているが、Alteryx 実測で向きが反転する可能性があるため鵜呑みにしないこと。

`ReplaceMultipleFound="False"` のとき（最初のマッチのみ保持）は、右側 DataFrame を先に `drop_duplicates()` してから merge する。

```python
# FindAny + ReplaceMultipleFound=False の例
_LOOKUP_12 = df_replace[["key_b", "col_a", "col_b"]].drop_duplicates("key_b")
df = pd.merge(
    df,
    _LOOKUP_12,
    left_on="key_a",
    right_on="key_b",
    how="left",
)
```

### NOTE コメントを見て手動で substring join を書く場合の注意

`pd.merge` は等価結合しかできないため、FindAny の部分一致を忠実に再現するには
`search_value in find_value` のような contains 判定を自前で書くことになる（`find_value`
は `FieldFind` の値＝Targets/メイン側、`search_value` は `FieldSearch` の値＝Source/
ルックアップ側。Alteryx の anchor 名 "Source" はルックアップ側を指すため、ここで
「メイン側」の意味で "source" を使うと `scaffold.py` の anchor 名と衝突して誤読を招く）。
上述の通りこの向き（needle=search_value）は推定であり未検証。素朴な実装だと、向きに
かかわらず以下の2点で誤マッチしやすい。

- **NaN は `str(nan)` で `"nan"` という文字列になる** — 相手側に偶然 `"nan"` という
  値があると誤マッチする。`pd.isna()` で事前に弾く。
- **空文字はすべての文字列に含まれる** — `"" in "ABC-123"` は `True`。needle 側
  （下記の例では `search_value`）が空文字だと全行にマッチしてしまう。空文字を
  マッチ対象から除外するか、Alteryx の実挙動（全件マッチ/無視）を確認したうえで
  扱いを決める。

```python
def is_find_any_match(find_value: object, search_value: object) -> bool:
    if pd.isna(find_value) or pd.isna(search_value):
        return False
    needle = str(search_value)
    if not needle:
        return False  # 空文字の扱いはAlteryx実測で確認
    return needle in str(find_value)
```

複数マッチ時に出力行が何行になるか（`ReplaceMultipleFound=True` と `ReplaceMode=Append`
の組み合わせ）は Alteryx 側の実測でしか確定できないため、scaffold はそこまで踏み込まず
`pd.merge(how="left")` + NOTE コメントに留めている。

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
| FindReplace FindAny + Append | `pd.merge(how="left")` に変換。部分一致の意味論は要確認 |
| FindReplace FindAny + ReplaceMultipleFound=False | 右側を `drop_duplicates()` してから merge |
| FindReplace FindAny を自前で substring join 実装する場合 | `pd.isna()` で NaN 除外、空文字 needle は全件マッチしうるので要ガード。含意の向き自体も未検証 |

---

## 関連実装

- `src/yxray/tool_registry.py` — 各ツールの python_hint と `_FILTER_HINT`
- `src/yxray/scaffold.py` — `_gen_join`（inner のみ生成）、`_gen_union`（ByName 固定）、`_gen_filter`（複合条件のマスク分割）
- `src/yxray/alteryx_expr.py` — `translate_filter_masks`（トップレベル AND/OR のオペランド分解）
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint
