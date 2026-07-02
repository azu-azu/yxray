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

## まとめ: 変換レビューのチェックポイント

| Alteryx の挙動 | 移植時に確認すること |
|----------------|----------------------|
| `Contains(col, val)` | `case=False`、`re.escape()` または `regex=False`、`na=False` |
| `IsEmpty(col)` | `isna() \| (== "")` の両建て |
| `and` / `or` / `!` / `=` | `&` / `\|` / `~` / `==` への置換、各条件を `()` で囲む |
| 空白のみのセルを空扱いにしたい | `str.strip()` を前置 |
| Join の L / R 出力を使っている | `how='outer', indicator=True` で分岐 |
| Filter の F 出力を使っている | `~mask` で明示抽出 |
| Union が ByPosition モード | 列名を揃えてから `concat` |
| Sort に NULL が含まれる | `na_position='first'` |
| Summarize に NULL グループがある | `groupby(..., dropna=False)` |

---

## 関連実装

- `src/yxray/tool_registry.py` — 各ツールの python_hint と `_FILTER_HINT`
- `src/yxray/scaffold.py` — `_gen_join`（inner のみ生成）、`_gen_union`（ByName 固定）
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint
