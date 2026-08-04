# バッチマクロのインターフェース — コントロールパラメータをどう読むか

「コンテナの中にコントロールパラメータがあるのに、HTML にもmdにも出てこない」
という症状の原因調査と、それを受けて入れた対応の記録である。

ノードのフィルタ(`filter_ui_tools`)の話と、
**そもそもノードの中に情報が無い** という話が重なっていた。

> XML の構造と設定値は実バッチマクロで裏取り済みだが、**ToolID は匿名化して
> ある**(ControlParam を `101`、Action を `102`、書き換え先を `2` と呼ぶ)。
> `コントロールパラメーター (101)` の形式そのものは Alteryx の既定名で、
> パーサがここから ToolID を取り出す仕様に依存している。

---

## TL;DR

> **コントロールパラメータと Action の `<Node>` は `<Configuration/>` が空。**
> **実体は `<Nodes>` の外、`<BatchMacro><ControlParams>` と
> `<RuntimeProperties><Actions>` にある。**
> **なので「フィルタを外して表示する」だけでは何も分からない。**

yxray はこの2ブロックを `WorkflowDoc.macro_interface` としてパースし、
**書き換えられる側のツール** に警告として出す。

```
[#1] 出力ファイル名 (ToolID 101)      ← <BatchMacro><ControlParams> 由来
        │
        ▼
Action 102                            ← <RuntimeProperties><Actions> 由来
        │  Expression=[#1]  Destination=2/File
        ▼
ToolID 2 の File を実行時に上書き      ← ここに警告が出る
```

---

## 症状の3層構造

### 層1: 既定でノードが捨てられている

`parser.py` は `AlteryxGuiToolkit.*` を既定で除外する
(ToolContainer だけ例外)。ControlParam は
`AlteryxGuiToolkit.Questions.ControlParam.ControlParam`、Action は
`AlteryxGuiToolkit.Action.Action` なので、どちらも消える。
コンテナだけが残って中身が空に見えるのはこのため。

`acd inspect --show-ui`(長い別名は `--no-filter-ui-tools`)を付ければ
ノード自体は出る。

### 層2: `explain` にはそのフラグが無い

`inspect` と `diff` にはあるが、`_explain_impl` は
`parse_one(workflow)` を既定のまま呼ぶ。md/py 側は
**フラグで解決できる問題ではなかった**。

ただし後述のとおり、この非対称は解消しなくてよい。
インターフェースツールをデータフローに混ぜないのが正しく、
必要な情報は別経路(警告)で md にも py にも届くようにしたためである。

### 層3(本命): ノードを出しても中身が無い

```xml
<Node ToolID="101">
  <GuiSettings Plugin="AlteryxGuiToolkit.Questions.ControlParam.ControlParam">
  <Properties>
    <Configuration />          ← 空
    <Annotation>
      <AnnotationText>コントロールパラメーター (101)</AnnotationText>
```

パーサが読むのは `Properties/Configuration` だけなので、
フィルタを外しても `config={}` の箱が増えるだけだった。

---

## 実体はどこにあるか

### `<BatchMacro><ControlParams>` — `[#N]` の番号を決める

```xml
<BatchMacro>
  <ControlParams>
    <ControlParam>
      <Name>コントロールパラメーター (101)</Name>
      <Description>出力ファイル名</Description>
    </ControlParam>
  </ControlParams>
</BatchMacro>
```

**出現順が `[#1]`, `[#2]`, … に対応する。** 番号はどこにも書かれていない。

`<Questions>` にも同じパラメータが載るが、そちらは Interface タブの
設計情報で、Tab 要素が混ざるうえ **ブロックが複数現れることがある**
(実ファイルで2ブロック・4件ヒットして誤読した実績が
`tools/analyze_macro_actions.py` に記録されている)。
なので `<BatchMacro>` 側だけを読む。2ブロック以上あった場合は
先頭を使い、`MacroInterface.warnings` に記録して黙って進まない。

キャンバス上の ToolID は `<Name>` の `(101)` から取る。
リネームされていると取れないので `tool_id=None` になるが、
`[#N]` と Description は生きる。

### `<Properties><RuntimeProperties><Actions>` — 書き換え先

```xml
<Action>
  <ToolId value="102"/>
  <Expression>[#1]</Expression>
  <Destination>2/File</Destination>
</Action>
```

`Destination` は `ToolID/フィールド名`。`Expression` の `[#N]` が
上のパラメータを指す。

---

## モデル

`src/yxray/models/macro.py`:

| クラス | 意味 |
| --- | --- |
| `ControlParam` | `index`(= `[#N]`)/ `name` / `description` / `tool_id` |
| `MacroAction` | Action の `tool_id` / `expression` / `destination_tool_id` / `destination_field` / `param_indexes` |
| `MacroInterface` | 上2つの集合 + `warnings`。空なら falsy |

`WorkflowDoc.macro_interface` に載せている。**ノードではなく文書レベル**
なのは、XML 上そこにあるからで、どの `AlteryxNode` にも属せないため。

普通の .yxmd では空インスタンスになる(それが正常系)。

---

## どこに出るか

### md / py(`acd explain`)

`macro_overrides.detect_macro_overrides(doc)` が
**書き換えられる側のツール** ごとの警告を返す。
`output_collisions` と同じ形にしてあるので、`cli.py` は
`warnings_by_tool` に混ぜるだけでよく、scaffold 側は無変更。

```python
# ToolID_2: DbFileOutput
# WARNING: Batch macro: Action 102 rewrites "File" at runtime as [#1] from
# [#1] 出力ファイル名 (ToolID 101). The configuration here is only the
# design-time default — parameterize this value instead of hard-coding it.
df_1.to_csv(r"C:\data\out.csv", index=False)
```

生成コードのパスが「実際には使われない既定値」であることが、
そのパスを使っている行の真上に出る。

### HTML(`acd inspect`)

ノード詳細パネルに `runtime override (batch macro)` セクションが増える。
**チェーン上の3者がそれぞれ自分の視点で読める** ようにしてある
(どれをクリックしても、その場で疑問が解ける形にするため):

| クリックしたノード | 表示 |
| --- | --- |
| 書き換えられるツール(2) | `File ← [#1] 出力ファイル名 — Action 102` |
| Action(102) | `rewrites 2/File as [#1] 出力ファイル名` |
| ControlParam(101) | `[#1] 出力ファイル名 → 2/File via Action 102` |

後ろ2つは `--show-ui` のときだけ見える。
書き換えられる側は常に見える(ここが一番重要な情報なので)。

`MacroInterface.warnings` は、影響を受ける全行に `⚠` 付きで併記する。
`[#N]` の対応が信用できるかどうかが変わるためである。

### annotation(ついでに全ツールへ)

`AlteryxNode.annotation` に `Properties/Annotation/AnnotationText` を
取り込んだ。ControlParam / Action は `<Configuration/>` が空なので、
**これが唯一の人間可読な手がかり** になる(`値を更新` など)。
パネルの `annotation` 行に出る。diff のハッシュは `config` のみから
計算されるので、差分検出には影響しない。

---

## 同時に直したバグ: `df_?` が生成されていた

接続はノードのフィルタと無関係に全件パースされる。そのため
除外されたノードを指す接続が残り、`build_predecessor_map()` が
**存在しないツールを先行ノードとして返していた**。

Action が下流のデータツールに繋がっていて、その接続が XML 上で
データ接続より先に並んでいると、`ctx.preds[0]` が幽霊 ToolID になり:

```python
df_2 = df_?[df_?["a"] > 1]   # 構文エラー。接続の並び順次第で発火した
```

`build_predecessor_map()` を **データフローツールに限定** して修正した。
`topo_order()` も同様に `AlteryxGuiToolkit.*` を除外する
(以前は ToolContainer だけを除外していた)。

判定は `tool_registry.is_dataflow_tool()` に集約してある。
Action → Filter という辺は「実行時に設定を書き換える」であって
「行を流す」ではないので、**フィルタの有無に関わらず** データグラフから
外すのが正しい。この修正により、`--show-ui` で
インターフェースノードを取り込んでも、`df_101 = ...` のような
無意味なスタブは生成されない。

---

## 現状の限界

- **`[#N]` の値そのものは解決しない。** 呼び出し元(親ワークフロー)が
  レコードごとに渡す値なので、静的には決まらない。yxray が出せるのは
  「ここは実行時に変わる」という事実まで
- **`Expression` は評価しない。** `[#1]` のような単純参照はそのまま出すが、
  式が組み立てられている場合(文字列連結など)は式のまま表示する
- **ToolID の対応はパラメータ名依存。** `(101)` を含む既定名から取るので、
  リネームされていると `tool_id=None` になる
- **`<Questions>` は読まない。** 上記の理由で信用できないため
- **Action 以外のインターフェースツール**(Tab / TextBox / チェックボックス系)は
  モデル化していない。バッチマクロの `[#N]` 解決に必要なのは
  ControlParam と Action だけだったため

---

このドキュメントは自動では読み込まれないので、依頼時に
「docs/macro-interface-model.md 参照」と一言添えると確実。
