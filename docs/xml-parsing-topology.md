# XML の解析方法

`.yxmd` は Alteryx のワークフローを収めた XML。yxray はこれを
**「構造化データ → 依存グラフ → 実行順」** の3段で読み解く。

## トポロジーソートとは

- **トポロジー**: 何と何が、どうつながっているか(つながり方)。
- ワークフローの各ツールは「前のツールの出力を入力に使う」依存関係を持つ。
  これを **有向グラフ**(ノード=ツール、辺=接続)としてモデル化する。
- **トポロジカルソート** = 「依存されている側を先に」並べ替えること。
  Input → Filter → Join → Output のように、上流から下流への順序を得る。
  この順に生成すれば、生成コードは常に「使う変数が既に定義済み」になる。

---

## 3段のパイプライン

```
  .yxmd (XML)
     │
     ▼
  parser.py                      Node と Connection を読み取って
  （構造化）                       WorkflowDoc を作る
     │
     │   models/workflow.py:
     │     WorkflowDoc
     │     ├── filepath
     │     ├── nodes         … AlteryxNode（tool_id, tool_type, config, ...）
     │     └── connections   … AlteryxConnection（src_tool → dst_tool）
     ▼
  topology.py                    Connection を依存関係として解釈し、
  （順序計算）                     順番を計算する（topo_order）
     │
     │   戻り値: 実行順に並んだ tool_id のリスト
     ▼
  scaffold/ パッケージ            計算済みの順番で Python コードを生成する
  （コード生成）                   （_assemble.py が topo_order を呼ぶ）
     │
     ▼
  Python / pandas コード
```

---

## 各段の責任

### 1. `parser.py` — 構造化

lxml で XML を読み、2種類の要素を抽出する(`_parse_nodes` / `_parse_connections`):

- `<Node>` → `AlteryxNode`(`tool_id` / `tool_type` / `config` / 座標 / 元XML)
- `<Connection>` → `AlteryxConnection`(`src_tool` → `dst_tool` を結ぶ有向辺)

結果を `WorkflowDoc` に束ねる(`models/workflow.py`):

```
WorkflowDoc
├── filepath
├── nodes         : tuple[AlteryxNode, ...]
└── connections   : tuple[AlteryxConnection, ...]
```

**接続は `WorkflowDoc` 側に持ち、`AlteryxNode` は topology-free**
(ノードは自分の接続への参照を持たない)。「何がどうつながるか」の情報は
すべて `connections` に集約されているので、順序計算はここだけを見ればよい。

### 2. `topology.py` — 順序計算

`topo_order(doc)` が `connections` を依存グラフとして解釈し、
**実行順に並んだ `tool_id` のリスト**を返す。中身は Kahn's algorithm:

1. `ToolContainer` ノードを除外(見た目のグループ化用でデータフローを持たず、
   残すと入次数0の「偽のソース」になる)。
2. 各辺から**入次数**(何個の上流に依存するか)と後続ノードを作る。
3. 入次数0のノード(依存のないソース)から取り出し、後続の入次数を1つ減らす。
   0になったら次に取り出す。これを繰り返す。
4. 同時に取り出せるノードが複数あるときは **min-heap で `tool_id` の小さい順**
   に。枝の長さが不揃いでも、番号順・フロー順に近い並びになる。
5. サイクルに含まれて取り出せなかったノードは、落とさず元の順で末尾に追加。

関連ヘルパー:

- `build_predecessor_map(doc)` → `{dst: [src, ...]}`。各ツールの入力元を引く。
  scaffold 側で「このツールの入力フレームは誰か」を解決するのに使う。
- `compute_node_layer(doc)` → 各ノードの階層(描画レイアウト用)。

### 3. `scaffold/` パッケージ — コード生成

`scaffold/_assemble.py` が `topo_order(doc)` を呼び、返ってきた順に
ツールを1つずつ Python/pandas コードへ変換する。上流から下流の順なので、
各ツールの入力変数(`df<上流ToolID>`)は必ず生成済みになっている。

> かつては単一の `scaffold.py` がこれを担っていたが、現在は領域ごとの
> `scaffold/` パッケージに分割されている。構成は
> `docs/scaffold-architecture.md` を参照。

---

## まとめ

| 段 | モジュール | 入力 → 出力 |
|---|---|---|
| 構造化 | `parser.py` | `.yxmd` (XML) → `WorkflowDoc` |
| 順序計算 | `topology.py` | `WorkflowDoc.connections` → 実行順の `tool_id` リスト |
| コード生成 | `scaffold/` | 順序 + `WorkflowDoc.nodes` → Python コード |

「つながり方」は parser が `connections` に構造化し、topology がそれを
依存グラフとして順序に変換し、scaffold がその順で生成する — という一方向の流れ。

---

このドキュメントは自動では読み込まれないので、依頼時に
「docs/xml-parsing-topology.md 参照」と一言添えると確実。
