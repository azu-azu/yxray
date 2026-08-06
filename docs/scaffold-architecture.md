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
                   SpatialInfo
                   Distance
                   Buffer

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
| `_transform` | 単一入力の行変換 | Formula, Sort, Sample, Unique, RecordID, CountRecords |
| `_source` | ファイル以外の端点 | TextInput, Browse |
| `_aggregate` | 集約 | Summarize |
| `_findreplace` | golden 検証済み4モード変換 | FindReplace |
| `_spatial` | geopandas 空間ツール | CreatePoints, SpatialMatch, SpatialInfo, Distance, Buffer |
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
- **`GeneratedCode.helpers` で `def` を本流の外に出せる。** TextInput の
  行データがこれ(`build_text_input_df_<ToolID>()`)。`.py` では
  `_emit_helper_defs` が `main()` の上のモジュール階層に持ち上げるので
  `main()` は `df_1 = build_text_input_df_1()` の1行だけになり、
  `.md` では `_tool_blocks(inline_helpers=True)` が呼び出しの直前に
  そのまま置く(md はブロック単位で `<Node>` XML と並べて読むため、
  データがブロック内に残る必要がある)。関数名は他ツール同様 ToolID 接尾辞で
  衝突を防ぐ。

---

## 変更時の注意

- ツールを追加するとき: 該当領域の module に `gen_<tool>(ctx)` を書き、
  `_registry.py` の `GENERATORS` に1行足すだけ。組み立て側は触らない。
- 生成コードの文字列を変えたら `tests/test_scaffold.py` の該当 assert
  (生成コードの完全一致)も更新すること。
- このドキュメントは自動では読み込まれない。依頼時に
  「docs/scaffold-architecture.md 参照」と添えると確実。

## `TOOL_REGISTRY` の `"no"`/`"partial"` を生成器に昇格させる基準

`tool_registry.py` の `python_supported` が `"no"`/`"partial"` のツールは、
`GENERATORS` 未登録のため `_assemble.py` が汎用 TODO スタブしか出さない
(`python_hint` は `acd i`/`acd explain` のヒント表示専用で、`.py` 生成には
使われない)。これを実際の生成器に昇格させてよいかの基準:

- **設定が無い、または設定次第でコードの形が変わらない場合のみ即昇格可**。
  例: `CountRecords`(2026-07-19 昇格) — Alteryx公式ドキュメントで
  「UIに設定項目自体が無い」と確認済みで、`pd.DataFrame({"Count": [len(df)]})`
  以外の出力があり得ない
- **設定次第でコードの形が変わるツールは、実際のAlteryx出力とのgolden突合
  なしに昇格させない**。`_findreplace.py`(golden 検証済み4モード変換)が
  この規律の実例 — 対応済みの組み合わせだけ実コードにし、それ以外は
  「対応不可」と分かる形の明示的TODOに落とす
- `Directory`(`"partial"`)は後者に該当し、2026-07-19 時点で
  リポジトリ内に検証材料(実ワークフローXML)が無いため未昇格
  (`Buffer` も同じ理由で未昇格だったが、実XMLが出てきたので
  [2026-08-05 に部分昇格](#buffer-の部分昇格2026-08-05)した)。
  `MultiRowFormula`/`PolySplit`/`DynamicInput`
  (`"no"`)はcommit `56b34d5` で「1つの生成スニペットに還元すると誤ったコードを
  出すリスクの方が高い」と判断され、そもそも昇格候補から意図的に外されている
- 昇格させる場合は本ドキュメントの表と `tool_registry.py` の該当 `ToolInfo`
  (hint文言が実際の生成コードと食い違わないよう)を両方更新すること

### `SpatialInfo` の部分昇格(2026-07-31、`"no"` → `"partial"`)

同じく `56b34d5` で候補外だったが、実ワークフローの `<Node>` XML が出てきたので
`_findreplace` 型の部分昇格をした。**選択項目のうち `CentroidObj` だけ実コード、
他は明示 TODO** という形である。

`SelectedItems` の項目ごとに、golden 突合が要るかどうかが割れるのが理由:

| 項目 | 出力の型 | golden CSV に出るか | 判断 |
| --- | --- | --- | --- |
| `CentroidObj` | SpatialObj | **出ない**(Map タブのみ) | 昇格。値がズレても CSV 比較を汚さない |
| `Area` / `Length` | 数値 | 出る | 未昇格。EPSG:4326 は単位が度で、Alteryx の単位設定(sq miles / km)と一致しない |
| その他 | — | — | 未昇格。実XMLが無く項目名すら未確定 |

出力列名 `Centroid` は推測ではなく、実XMLの MetaInfo
(`source="SpatialInfo: CentroidObj Source=SpatialObj"`)で裏取りしてある。
Spatial Info はチェックボックスだけでリネームUIを持たないため、名前は固定。

項目を増やすときは `_spatial.py` の `_SPATIAL_INFO_ITEMS` に1行足す。
ただし数値を返す項目は、投影CRSの選択と Alteryx の単位設定を決めるまで
足してはいけない(投影CRSの方は
[spatial-crs-design.md の共通ルール](spatial-crs-design.md#メートル演算は-utm-へ投影してから測る共通ルール)
で解決済みだが、単位設定は Spatial Info の XML に現れないため未解決)。

### `Distance` の部分昇格(2026-07-31、`"no"` → `"partial"`)

同じく実XMLが出てきたので昇格。**単一入力・直線距離だけ実コード、
方位と2入力モードとドライブタイムは TODO** という形である。

単一入力に限る根拠は MetaInfo で、出力 RecordInfo が1系統の列しか持たない
(2入力なら `Target_`/`Universe_` 接頭辞つきで両系統が並ぶ)。
`SpatialObjSource`/`SpatialObjDest` は同じレコード内の2列を指している。

| 出力 | 判断 |
| --- | --- |
| 距離 | 昇格。ただし投影誤差があるので生成コードに WARNING を出す |
| 方位(`Direction`) | 未昇格。8方位なのは `size="2"` から確定できるが、ポリゴンのどの点への方位かが不明 — [distance-direction-pending.md](distance-direction-pending.md) |
| ドライブタイム | 未昇格。routing サービスが要る |
| 2入力モード | 未昇格。`ReturnNearest` の行選択規則が未検証 |

距離だけ「golden 突合なし」の原則を緩めているのは、
**形が完全に確定していて、残る不確定が投影誤差だけ** だからである。
しかも誤差は golden diff に必ず現れる(黙って通らない)。
それでも Double 列なので、生成コードに
`WARNING: this is a planar UTM distance` を残してある。

### `Buffer` の部分昇格(2026-08-05)

`python_supported` は `"partial"` のままだが、hint だけの状態から
`GENERATORS` 登録済みの生成器(`gen_buffer()`)になった。
2026-07-19 時点では「設定次第でコードの形が変わるのに実XMLが無い」ため
未昇格だったが、実ノードの `<Configuration>` が出てきたので昇格した。
**`BufferSizeSource=FromField` だけ実コード、それ以外は明示 TODO** という、
`_findreplace` 型の形である。

根拠にした実XML(ToolID・ファイル名に加えて **サイズ列の名前も匿名化**
してある。昇格の根拠になるのは `BufferSizeSource` と `Units` の組み合わせで、
列名そのものではない。`SpatialObj` は Alteryx 側の既定名なのでそのまま):

```xml
<SpatialObjectField>SpatialObj</SpatialObjectField>
<IncludeSourceInOutput value="True"/>
<GeneralizeToOnePercent value="True"/>
<BufferSizeSource>FromField</BufferSizeSource>
<BufferSizeField>bufferSize</BufferSizeField>   <!-- 実際の列名は別 -->
<Units>Kilometers</Units>
```

| 設定 | 判断 |
| --- | --- |
| `BufferSizeSource=FromField` | 昇格。列を metres に換算して `buffer()` に渡す(`buffer()` は配列サイズを受ける — 実測確認済み) |
| 固定サイズ(`Fixed` 等) | **未昇格**。サイズを保持するタグ名が実XMLで確認できていない。推測で読むより TODO |
| `Units` | 昇格。Distance の `<OutputUnits>` と同じ綴りなので `_METRES_PER_UNIT` を共用。未知の綴りは TODO |
| `GeneralizeToOnePercent` | 昇格。`simplify(サイズの1%)`。負サイズ対策に `.abs()`(GEOS は負の tolerance を例外にする) |
| 出力フィールド名 | 昇格。**`<入力フィールド名>_Buffer`** で確定(下記 MetaInfo)。Buffer は入力オブジェクトを上書きせず、**列を1本足す** |
| `IncludeSourceInOutput=False` | 生成コードは元オブジェクトを残したまま、コメントで「Alteryx 出力にはバッファだけ」と明示する。SpatialObj は golden CSV に出ないので列の有無は比較に影響せず、落とすと上流が作った geometry を失うほうが害が大きい |

出力フィールド名は推測ではなく、Buffer ノードの出力 MetaInfo で裏取りしてある。
Spatial Info と同じくリネームUIを持たないため、名前は固定である。

```xml
<Field name="SpatialObj_Buffer" size="2147483647" type="SpatialObj"
       source="Buffer: Source=SpatialObj SizeField=… Units=Kilometers"/>
```

**バッファ側をアクティブ geometry にする**のは、`gen_spatialmatch` が
下流ノードの `SpatialObj=` 属性を読まずアクティブ geometry で `sjoin` するため
([alteryx-pandas-differences.md 18章](alteryx-pandas-differences.md#設計上の保留--rename_geometrycentroid-は条件付き保留))。
元オブジェクトをアクティブのままにすると、**バッファする前の形で空間結合される**
という静かな誤りになる。元オブジェクトはフレームに残るので、名前で引けば取れる。

Buffer が「golden 突合なし」で昇格できるのは、Distance の距離とは違う理由で、
**出力が SpatialObj だから** である(Spatial Info の `CentroidObj` と同じ根拠)。
バッファ形状は Alteryx と頂点一致しない — shapely の64分割円は真円より
面積が 0.16% 小さく、1% generalize でさらに 0.5% 減る(いずれも実測)— が、
SpatialObj は Results grid にも golden CSV にも出ないので比較を汚さない。

CRS の扱い(**メートル系へ出て、必ず EPSG:4326 へ戻る**)は
[spatial-crs-design.md](spatial-crs-design.md#buffer-はメートル系へ出て戻ってくる)
にまとめてある。

固定サイズを昇格させるときの依頼文:

```
docs/scaffold-architecture.md 参照
ex/Buffer scaffold側: 固定サイズが TODO のまま。実XMLの
<Configuration> を貼るので昇格して。
(BufferSizeSource が FromField 以外のノードの Configuration をそのまま貼る)
```

---

## 生成コードにヘルパー関数を出すかどうか

「毎回同じパターンが出るなら `apply_select_edits` のように関数化すべきか」の
判断基準は
[alteryx-pandas-differences.md 19章「生成コード側の関数化はいつ許されるか」](alteryx-pandas-differences.md#生成コード側の関数化はいつ許されるか--全ツール共通の基準)
にある。要点だけ再掲:

- 選択肢は4つ — (a) 生成器側の関数 / (b) `GeneratedCode.helpers` / (c)
  `reference_impl/` / (d) ベタ書き。**既定は (a) で DRY を取り、出力側では取らない**。
- 出力側へ出すのは「pandas 組み込みで書けない」かつ「ベタ書きだと静かに間違う」
  かつ「設定でなく機構」かつ「golden で固定できる」かつ「繰り返し出る」を
  **すべて**満たすときだけ。出現回数だけでは昇格させない。
- 満たしたうえで、自己完結するなら (b)、golden で挙動を育てるなら (c)。

### 空間ツールの繰り返しパターンを関数化しない判断（2026-08-04）

Spatial Info / Distance で毎ブロック同じ形が出るが、いずれも (d) のまま置く。

| 繰り返している部分 | 判断 |
| --- | --- |
| `df_out["Centroid"] = _geom.centroid` | (d)。`.centroid` が geopandas 組み込みそのもので、隠す機構が無い。生成ブロック15行のうち11行はコメント（golden CSV に出ない理由・平面centroidの誤差・Area/Length が無い理由）で、それこそがこのブロックの中身。関数にするとコメントの置き場が消える。項目を増やすときの変更点は今も `_SPATIAL_INFO_ITEMS` の1行だけで、重複は既に (a) で潰れている |
| `_spatial_field_note()` + `_geoseries_expr()`（XML のフィールド名 → 無ければアクティブ geometry、+ `crs="EPSG:4326"` のラベル付け） | 当面 (a)。現時点で SpatialInfo ×1・Distance ×2・Buffer ×1 の4箇所に出るが、中身は分岐の無い1式で、CRS は 4326 固定の不変条件（[spatial-crs-design.md](spatial-crs-design.md)）に守られている |
| UTM へ投影 → メートルで演算（Distance / Buffer）＋ `total_bounds` ガード | (a)。共有しているのは注釈（`_METRIC_CRS_NOTE` / `_empty_geometry_note()`）と換算表（`_METRES_PER_UNIT`）だけで、演算そのものは1行ずつ違う（測る／描く、戻る／戻らない）。関数化すると「Buffer は 4326 へ戻す」という差が隠れる |

`_geoseries_expr` の昇格条件（どれかが起きたら見直す。回数だけでは動かさない）:

1. 4326 以外の CRS を扱う必要が出て、フォールバックに**分岐**が増えたとき
2. geometry 列の候補が複数ある／CRS が `None` のケースを実データで踏んだとき
3. 呼び出し箇所が5を超え、**かつ** 1 か 2 が起きているとき

昇格するなら (c) ではなく **(b) を先に検討する**。CRS 解決は設定ではなく純粋な
機構で、利用者にコピー手順を課す理由が無いため。`reference_impl` に置くのは
「挙動を golden / `tests/test_reference_scripts.py` で固定したい」ものに限る。

いずれの場合も `tool_registry.py` の `python_hint`（現状
`df["Centroid"] = gpd.GeoSeries(geom, crs="EPSG:4326").centroid`）を同時に直すこと
— Formula で `.assign()`（hint）と添字代入（scaffold）がズレた前例がある
（`docs/explain-output-anatomy.md`）。
