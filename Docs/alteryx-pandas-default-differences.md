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
業務上これも空とみなしたい場合は、両方とも `strip()` してから判定する。

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

## まとめ: 変換レビューのチェックポイント

| Alteryx の式 | 移植時に確認すること |
|---|---|
| `Contains(col, val)` | `case=False` の追加、`re.escape()` または `regex=False` の追加 |
| `IsEmpty(col)` | `isna() \| (== "")` の両建て |
| `and` / `or` / `!` / `=` | `&` / `\|` / `~` / `==` への置換、各条件を `()` で囲む |
| 空白のみのセルを空扱いにしたい | `str.strip()` を前置 |

---

## 関連実装

- `src/yxray/tool_registry.py` — `_FILTER_HINT` に `str.contains` と `isna() | (== "")` のパターンを収録
- `src/yxray/static/single_graph.js` — inspect パネルの Filter python_hint にこれらのコメントを表示
