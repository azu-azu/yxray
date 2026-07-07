# Stale Select フィールド検出

---

## 1. 背景: Alteryx の Select ツールと XML の性質

**Alteryx** は、ノードをつないでデータ処理パイプラインを GUI で組むツール。
パイプラインの設定は `.yxmd` という XML ファイルに保存される。
**yxray** はこの XML を解析して Python（pandas）コードに変換するツールで、`acd ex <workflow.yxmd>` コマンドで実行する（`acd` は yxray の CLI エントリポイント）。

### Select ツールとは

Alteryx の **Select ツール**は、列の取捨選択・リネームを行うノード。
XML の `@selected` 属性（`True` / `False`）で keep/drop を、`@rename` 属性で列名の変更を指定する。

Alteryx のキャンバス上の各ツールには一意の整数 ID（**Tool ID**）が自動付与される。
ログや警告でのツールの識別に使われる。

### XML が古くなる問題

Select ツールは**作成した時点の列リスト**を XML に書き込む。
上流のノードを変更して列名が変わっても、**下流 Select の XML は自動更新されない**。

```
Select (Tool 166): "abc" → "def" にリネーム
        │
        ▼
Select (Tool 108): @field="abc" selected=False の設定が XML に残存
```

Tool 108 の GUI には「abc が見つかりません」と表示されるが、XML は更新されない。
この「XML には記載があるが実際のデータストリームには存在しない列」を**ゴースト列**と呼ぶ。

### Alteryx と Python の挙動の違い

| | ゴースト列に対する挙動 |
|---|---|
| **Alteryx** | 実行時に存在しない列を黙ってスキップする |
| **Python (pandas)** | `df.drop(columns=["abc"])` は `KeyError` でクラッシュする |

yxray が XML を忠実に変換すると、Alteryx では動いていたワークフローが Python で動かない問題が起きる。

---

## 2. 解決アプローチ: stale 検出

### 方針

列スキーマを完全に追跡するには、以下のような Alteryx 固有の列変換を考慮する必要がある。

| ツール | 列への影響 |
|--------|------------|
| Formula | 計算式で新規列を追加・既存列を上書き |
| Join | 左右の入力列に `Left_` / `Right_` プレフィックスを自動付与 |
| Union | 複数ストリームの列集合をマージ |
| DynamicRename | 実行時に決まるルールで列名を一括変換 |

これらを全て追跡するとコストが高く、誤検出も増える。
**Phase 1** では「Select ツール間の Rename 追跡のみ」に絞り、精度より実装コストを優先した。

- **検出できるケース**: 上流 Select がリネームした列名を、下流 Select が `@field` 属性で参照している
- **検出できないケース**: DynamicRename、Join のプレフィックス自動付与、Formula での列追加

### アルゴリズム: リネーム履歴の伝播

ワークフローのノードをトポロジカル順（実行順）に処理しながら、各ノードに「ここまでに行われたリネームの対応表（history）」を持ち回る。

```
history = { 旧列名: RenameRecord(旧名, 新名, リネームしたツールID) }
```

各ノードでの処理：

```
Select ノード:
  ① 上流の history を継承
  ② このノードの @field が history に存在すれば → StaleFieldWarning を生成
  ③ stale と判定した列は history から削除（下流への重複警告を防ぐ）
  ④ このノードの @rename エントリを history に追加

Select 以外のノード（Filter, Formula 等）:
  → history をそのまま下流に引き継ぐ（近似）
```

複数の上流がある場合（Union, Join など）は各上流の history を `dict.update()` でマージする。
片方の枝のみでリネームされた列が過剰検出になる場合もあるが、「警告」どまりのため実害は小さいと判断した。

---

## 3. データ構造

```python
@dataclass(frozen=True)
class RenameRecord:
    old_name: str      # リネーム前の列名
    new_name: str      # リネーム後の列名
    renamed_at: int    # リネームを行った Select ツールの ID

@dataclass(frozen=True)
class StaleFieldWarning:
    tool_id: int       # stale 参照を持つ Select ツールの ID
    field_name: str    # stale な列名（XML の @field 値）
    renamed_to: str    # 現在の列名（1ホップ分）
    renamed_at: int    # リネームを行ったツールの ID
    message: str       # 人間向けの説明文
```

---

## 4. 出力: `acd ex` への統合

stale フィールドが検出された場合、以下が追加される。

### ターミナル（stderr）

```
Report     → output/workflow.md
Template   → output/workflow.py
Pyproject  → output/pyproject.toml
```

警告はターミナルには表示しない。生成ファイルを参照する。

### Python scaffold（`.py` / `.md` の Python Scaffold セクション）

該当ツールの `# ToolID` ヘッダー直下に `# WARNING:` コメントが挿入される。

```python
# ────────────────────────────────────────────────────────────────────
# ToolID 108: AlteryxSelect
# WARNING: "abc" was renamed to "def" at Tool 166. This setting in Tool 108 has no effect on the current schema.
_COLS_108 = [
    SelectColumnEdit("abc", selected=False),
    ...
]
```

### Markdown レポート（`.md` ファイル）

レポート冒頭の見出しの下に `## Warnings` セクションが追加される。

| ToolID | Field | Renamed To | Renamed At | Message |
|--------|-------|------------|------------|---------|
| 108 | `abc` | `def` | 166 | "abc" was renamed to "def" at Tool 166. ... |

---

## 4b. `*Unknown` のみの Select（パススルー検出）

stale フィールドとは別に、**列指定が `*Unknown` だけの Select ツール**も scaffold 内で警告する。

| 条件 | 挙動 |
|------|------|
| `SelectColumnEdit` が `*Unknown` selected=True の1件のみ | `# WARNING:` コメントを生成 |
| それ以外（明示的な列指定あり） | 警告なし |

```python
# WARNING: Select only specifies *Unknown — no explicit column edits; likely a source-file issue (passthrough)
_COLS_76 = [
    SelectColumnEdit("*Unknown"),
]
```

`*Unknown` は「それ以外の列をすべて通す」ワイルドカード。他の明示的な列指定が1件もない場合、その Select ツールは実質的にパススルーであり、元の `.yxmd` の編集漏れや意図しないノード挿入の可能性がある。  
stale フィールド警告と同様、scaffold の `# ToolID` ヘッダー直下に出力される（Markdown Warnings テーブルには含まれない）。

---

## 5. 設計上の制約（Phase 1）

| 制約 | 理由 |
|------|------|
| Select→Select の Rename のみ追跡 | DynamicRename・Join の列変換は複雑すぎるため |
| 1ホップ警告（A→B→C の連鎖は A→B どまり） | 連鎖追跡は実装コスト増・偽陽性のリスクあり |
| stale 参照は消費（下流に cascade しない） | 同一フィールドへの重複警告を避けるため |
| 断定ではなく「warning」 | Formula 等で同名列が再追加される偽陽性の可能性があるため |

---

## 6. ファイル構成

```
src/yxray/staleness.py     # RenameRecord, StaleFieldWarning, detect_stale_select_fields()
src/yxray/topology.py      # build_predecessor_map() — staleness.py が使用する public helper
src/yxray/cli.py           # _write_explain_outputs() に warnings 引数を追加
tests/test_staleness.py    # 18 テスト
```

---

## 7. 今後の拡張候補（Phase 2）

- **DynamicRename 対応**: 静的な列名指定のケースのみ。正規表現ベースは「効果不明」として警告を抑制
- **Join プレフィックス追跡**: `Left_` / `Right_` 自動付与を列変換として履歴に記録
- **偽陽性の低減**: Formula での列追加を追跡し、リネーム後に同名列が再追加されたケースをフィルタリング
