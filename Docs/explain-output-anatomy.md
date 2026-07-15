# explain (ex) 出力の構造

`acd explain workflow.yxmd`(別名 `ex`)は出力ディレクトリに3ファイルを生成する
(`cli.py` の `_explain_impl` → `_write_explain_outputs`):

- `<stem>.md` — ツールごとの Python コードブロック + 元 `<Node>` XML(+ 警告表)
- `<stem>.py` — 実行用 Python テンプレート(`scaffold(doc)`)
- `pyproject.toml` — 検出依存(geopandas 等)

ツールごとの Python コードは **2系統** ある。修正依頼のときは
「hint側 / scaffold側」で呼び分ける:

- **hint側**: `tool_registry.py` の `ToolInfo`(1行ヒント)。
  `python_hint_for()` 経由で `explain.py` の `ExplainStep.python_hint` になり、
  inspect レポート(`single_graph_renderer.py`)の右ペインに出る。
- **scaffold側**: `scaffold.py` の `_gen_<tool>` 関数(実コード)。
  md/py の本体になるほか、`node_code_snippets()` 経由で
  inspect レポートのノード詳細スニペットにも出る。

scaffold側を変えたら `tests/test_scaffold.py` の該当 assert
(生成コードの文字列一致)も更新すること。

依頼の短縮記法(この形で来たら上記2系統の特定から始める):

```
ex/<ツール名> <hint側|scaffold側>: <症状 or エラー1行>。整理→方針→(実装まで)
```

このドキュメントは自動では読み込まれないので、依頼時に
「Docs/explain-output-anatomy.md 参照」と一言添えると確実。
