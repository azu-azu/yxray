# PolySplit — 部分昇格(SplitTo=Point)の記録と、残っている保留事項

Poly Split ツールを `python_supported="no"` → `"partial"` に部分昇格させた
(`src/yxray/scaffold/_spatial.py` の `gen_polysplit()`)。SplitTo の3モードの
うち **Point だけ実コード**、Region / DetailedRegion は明示 TODO のまま、という
[`SpatialInfo`](scaffold-architecture.md#spatialinfo-の部分昇格2026-07-31no--partial) /
[`Distance`](distance-direction-pending.md) と同じ形の切り方である。

昇格基準は [scaffold-architecture.md](scaffold-architecture.md#tool_registry-の-nopartial-を生成器に昇格させる基準)、
CRS の共通ルールは [spatial-crs-design.md](spatial-crs-design.md) を参照。
本ドキュメントは PolySplit 固有の話だけを扱う。

---

## TL;DR

> **SplitTo=Point の出力スキーマ(列名・型)は実ワークフローの XML で確定した。**
> **ただし列の「値」— 1頂点をどう数えるか — はまだ golden 未検証。**
> **`Split_SequenceNum` は golden CSV に出る Int32 列なので、この2つは別問題。**

commit `56b34d5` が PolySplit を昇格候補から意図的に外した理由(「1つの
生成スニペットに還元すると誤ったコードを出すリスクの方が高い」)は
Region / DetailedRegion にはそのまま残っている。Point だけは実XMLが
出てきたので、この一枠だけ先に進めた。

---

## 確定していること(実ワークフローの XML が根拠)

> 以下は実ワークフローで裏取り済みだが、`distance-direction-pending.md`
> と同じ方針で **ToolID・ファイル名は匿名化してある**。Configuration と
> MetaInfo の中身(Alteryx 側の固定語彙)はそのままである。

### Configuration

```xml
<Configuration>
  <SpatialObj field="SpatialObj" />
  <SplitTo type="Point" />
</Configuration>
```

### 出力側 MetaInfo

```xml
<Field name="Split_SpatialObj" size="2147483647"
       source="PolySplit: SpatialObj Source=SpatialObj" type="SpatialObj" />
<Field name="Split_SequenceNum"
       source="PolySplit: SequenceNum Source=SpatialObj" type="Int32" />
```

この2点から確定するのは:

- 列名は **`Split_SpatialObj`** と **`Split_SequenceNum`**(公開ドキュメント/
  ブログ経由で先に立てていた `Split_SpatialObject` + `Split_IsHole` という
  推測は誤りだった — 実XMLの `source=` 属性がどちらも
  `PolySplit: <出力名> Source=<入力フィールド>` の形で明言している)
- `Split_SequenceNum` は連番用の列として実在する(Bool の `Split_IsHole`
  ではない)
- 型は `SpatialObj` と `Int32`
- `SpatialInfo`/`Distance` と同じ規約(`_centroid_field`/`_metainfo_centroid_field`
  のパターン)どおり、列名は `source=` 属性の文字列一致で裏取りできる

この repo に PolySplit の実XMLはこの1件しかなく、`SplitTo` は
`Point` 以外の値(`Region`/`DetailedRegion`)を見た実例が無い。
`Split_IsHole` / `Split_SpatialObject` という文字列も全文検索でゼロ件。

---

## まだ確定していないこと(スキーマではなく値の話)

MetaInfo は「列が存在する」ことしか教えてくれない。`Direction` の教訓
(distance-direction-pending.md)と同じで、**列の計算ロジックは別に検証が要る**。

1. **閉じ点の重複**
   `Polygon.exterior.coords` は始点と終点が同じ座標で戻ってくる
   (例: 正方形の4頂点が5点になる)。Alteryx がこの重複点を1頂点として
   数えるか、2つ目として `Split_SequenceNum` を振るかは未確認。
   `gen_polysplit()` は重複を落とさず、5点として振っている
   (shapely の生の出力をそのまま使う、最も素朴な読み方)。

2. **穴(interior ring)がある場合の連番**
   外周を終えたあと内周(穴)の頂点にどう番号を振るか
   — 外周からの通し番号で続けるのか、穴ごとに1から振り直すのか — が
   未確認。`gen_polysplit()` は外周 → 各内周の順に通し番号で続けている。

3. **3D 入力の Z 座標**
   3次元の座標が来たとき Alteryx の `SpatialObj` が Z を保持するのかは
   未確認(`_io.py` を含めこの repo のどこにも Z の扱いに関する記述が無い)。
   `gen_polysplit()` は `gpd.points_from_xy()` を使うため常に X/Y だけを
   拾い、Z があれば黙って落とす。**最も無難な選択ではあるが、
   Alteryx の挙動に「合わせた」結果ではない。**

4. **NaN / 空ジオメトリ行の扱い**
   `geometry is None` も `float('nan')`(pandas の欠損表現)も、
   `shapely` 以外の値(WKT文字列や `pd.NA`)もまとめて拾い、その行を
   出力から落とす。geopandas 純正の `explode()` も同じ挙動(2行 → 1行を
   実測済み)なので選択としては妥当だが、Alteryx 自身がどう扱うかは
   別problem。**黙って落とさず、落とした件数を `logger.warning` で
   報告する**形にした(`Distance`/`Buffer` が異常系で
   `Requirement.LOGGING` を使っている前例に合わせた)。

いずれも `Split_SequenceNum` という **golden CSV が比較する Int32 列**に
直接影響する。値がズレていても例外にはならないので、golden 突合なしに
「動いている」と誤診しないよう、生成コードの `_POLYSPLIT_SCHEMA_NOTE` に
上記4点をそのまま書き出してある。

---

## 実装した内容

`src/yxray/scaffold/_spatial.py` の `gen_polysplit()`。

- `SplitTo` が `Point` 以外、または `SpatialObj` の入力フィールドが
  見つからない場合は TODO に落ちる(`Distance`/`Buffer` の blocker
  パターンと同じ)
- Point モードでは、ノードごとのヘルパー関数
  `_iter_vertices_<ToolID>()` を生成し(`geom.exterior.coords` →
  `geom.interiors` の順で頂点を yield)、1入力行 → N出力行に展開する
- 出力列は確定どおり `Split_SpatialObj`(`gpd.points_from_xy` 由来の
  GeoSeries)と `Split_SequenceNum`(`int32` の numpy 配列)
- 分割後の点が**フレームの active geometry になる**
  (`.set_geometry("Split_SpatialObj")`)。Buffer の
  `_BUFFER_ACTIVE_GEOMETRY_NOTE` と同じ理由 — 後続に Spatial Match が
  繋がったとき、`gpd.sjoin` は列名ではなく active geometry を見るため
- 空/欠損ジオメトリの行は出力から落ち、件数を `logger.warning` で報告

Region / DetailedRegion は `SplitTo` の値が違うだけで TODO に落ちる
(実装済みの Point 分岐とは独立しているので、実XMLが出てきたときに
そのまま追加できる)。

---

## 決着のつけ方(golden 突合)

`Split_SequenceNum` を含む Alteryx 出力行が要る。特に:

- **穴のあるポリゴン**を1件(内周の番号が続くか振り直すかを見るため)
- **閉じた多角形**を1件(始点=終点の重複が2頂点として数えられるかを見るため)
- 可能なら null / 空ジオメトリの行を混ぜたケース(落ちる行数が
  Alteryx の出力行数と一致するかを見るため)

これが埋まれば `_POLYSPLIT_SCHEMA_NOTE` の4点のうち該当するものを外し、
[`Distance`](distance-direction-pending.md) の `DistToInsideEdge` 側と同じ形の
「golden-verified」コメントに置き換えられる。Region / DetailedRegion の
昇格には、それぞれの `SplitTo` 設定を持つ実XMLが別途要る。
