# scaffold パッケージの構成

`src/yxray/scaffold/` は Alteryx ワークフロー → Python/pandas コード生成器。
かつては単一の `scaffold.py`(約1300行)に「全体組み立て」と「ツールごとの
コード生成」が同居していたが、2段階のリファクタで **領域ごとに責任と依存方向を
整理したパッケージ** に分割した。

外部利用者は `from yxray.scaffold import scaffold` だけを見ればよく、内部構成が
変わっても影響しない(`cli.py` / `single_graph_renderer.py` は無変更)。

---

## 全体像

```
                    __init__.py
                （公開APIを再エクスポート）
                         │
                         ▼
                   _assemble.py
             （全体を組み立てる司令塔：
              preamble / paths / main() / 公開API）
                    │        │
                    │        └──────────────┐
                    ▼                        ▼
              _registry.py                 _io.py
        「このToolは誰が担当？」        Input/Output は
         セグメント→生成関数の対応表     パス描画が特殊なので
                    │                    _assemble も直接使う
     ┌──────┬───────┼────────┬─────────┬────────┬─────────┐
     ▼      ▼       ▼        ▼         ▼        ▼         ▼
   _io   _filter _select _combine _transform _source _aggregate
    │       │       │        │         │        │         │
    ▼       ▼       ▼        ▼         ▼        ▼         ▼
 Input   Filter  Select    Join     Formula  TextInput Summarize
 Output                    Union     Sort     Browse
                           Append    Sample
                                     Unique
     ┌──────────┬──────────┐
     ▼          ▼          ▼
 _findreplace          _spatial
     │                    │
     ▼                    ▼
 FindReplace       CreatePoints
                   SpatialMatch

  （↑ すべての生成モジュールは _common だけに依存する）
                         │
                         ▼
                    _common.py
        FIELD_RE / frame_name / anchor_src /
        ToolContext / PathStyle  ← 依存チェーンの底
```

---

## 依存の向き(一方向)

循環 import を防ぐため、依存は必ず下向きの一方向に固定している。

```
_common               ← 共有プリミティブ。ここは誰も上を見ない
   ↑
_io / _filter / _select / _combine / _transform /
_source / _aggregate / _findreplace / _spatial
                      ← 各ジェネレータは _common だけを見る
   ↑
_registry             ← ジェネレータ群を import する唯一の場所
   ↑
_assemble             ← registry(+ _io)を使って全体を組む
   ↑
__init__              ← 外部にはここだけ見せる
```

ポイントは **`_registry.py` が合流地点** であること。各モジュールが互いを
直接 import し始めると依存が絡むが、「ジェネレータを知るのは registry だけ」に
することで、ツール module 同士は疎結合のまま保たれる。

---

## モジュール一覧

| モジュール | 責任 | 担当ツール |
|---|---|---|
| `_common` | 共有プリミティブ・`ToolContext`・`PathStyle` | — |
| `_io` | ファイル I/O(拡張子ディスパッチ / CRS正規化 / .shx 対応) | Input, Output |
| `_filter` | Filter 式変換サブシステム(日付比較・IsEmpty 死コード検出) | Filter |
| `_select` | stale-XML 警告つき列編集 | Select |
| `_combine` | 複数入力の結合(アンカー駆動) | Join, Union, AppendFields |
| `_transform` | 単一入力の行変換 | Formula, Sort, Sample, Unique |
| `_source` | ファイル以外の端点 | TextInput, Browse |
| `_aggregate` | 集約 | Summarize |
| `_findreplace` | golden 検証済み4モード変換 | FindReplace |
| `_spatial` | geopandas 空間ツール | CreatePoints, SpatialMatch |
| `_registry` | セグメント→生成関数の対応表(`GENERATORS`) | — |
| `_assemble` | 全体組み立て・公開API | — |

分割の粒度は「1ツール1ファイル」ではなく **機能の凝集** で切っている
(3行の Browse を独立させても意味がないため)。将来太った領域だけ、その時点で
さらに分ければよい。

---

## ToolContext による統一(第2フェーズ)

すべてのジェネレータは `ToolContext` 1個を受け取る形に統一されている。

```python
def gen_xxx(ctx: ToolContext) -> str: ...
```

`ToolContext`(`_common.py`)は `tool_id / segment / config / preds / anchors /
names / paths` を束ね、`df_in` / `df_out` を computed property で提供する。

これにより:

- **Input/Output も `GENERATORS` に入る。** 以前は Input/Output だけ
  `input_paths` / `output_paths` を余分に受け取っていたため registry に入れず、
  組み立てループ側で `if segment in INPUT/OUTPUT:` の分岐が必要だった。
  `.py`(`INPUTS[...]` 経由)と `.md`(生パスリテラル + .shx ノート)の描画差は
  context が持つ `PathStyle`(`PROJECT_PATHS` / `INLINE_PATHS`)に隔離した。
- **組み立てループが1本化。** `.py` 用 `_emit_main_body` と `.md` 用の
  `scaffold_simple_blocks` 内ループはほぼ同一実装だったが、セグメントだけで
  ディスパッチする単一の `_tool_blocks` に統合。`scaffold()` はそれをインデント
  して `main()` で包み、`scaffold_simple()` は平坦化するだけ。
  **ツール追加は1箇所の変更で済む。**

---

## 変更時の注意

- ツールを追加するとき: 該当領域の module に `gen_<tool>(ctx)` を書き、
  `_registry.py` の `GENERATORS` に1行足すだけ。組み立て側は触らない。
- 生成コードの文字列を変えたら `tests/test_scaffold.py` の該当 assert
  (生成コードの完全一致)も更新すること。
- このドキュメントは自動では読み込まれない。依頼時に
  「docs/scaffold-architecture.md 参照」と添えると確実。
