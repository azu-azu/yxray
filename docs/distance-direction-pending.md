# Distance の `Direction`(8方位)— 未翻訳の理由と、決着のつけ方

Alteryx の Distance ツールが出力する `Direction` 列を Python 生成コードへ
翻訳する作業が、**golden 突合待ちで保留** になっている。その保留の根拠と、
再開するときに踏んではいけない罠をまとめた記録である。

CRS(座標系)側の設計は [spatial-crs-design.md](spatial-crs-design.md)、
昇格基準は [scaffold-architecture.md](scaffold-architecture.md) を参照。
本ドキュメントは **`Direction` という1列** だけを扱う。

---

## TL;DR

> **8方位であることは XML から確定できるが、ポリゴン相手にどの点への方位を**
> **取るのかが確定しない。だから実コードを出さず TODO に落としている。**
> **決着には Alteryx 出力の実測値(golden)が要る。**

そして再開時にいちばん効くのは次の一点である。

> **素朴な候補実装は「全行 `N`」という、もっともらしい間違いを出す。**
> 起点がポリゴン内部にあるため `nearest_points()` が同一点を返すのが原因で、
> 例外にならないので golden と突き合わせた人が
> 「最寄り点説が外れた」と誤診しかねない。詳細は
> [候補実装の落とし穴](#候補実装の落とし穴実測で確認)。

---

## 現在地

Distance は **部分昇格済み**(`python_supported="no"` → `"partial"`)。
PR [#81](https://github.com/azu-azu/yxray/pull/81) で入った。
実装は `src/yxray/scaffold/_spatial.py` の `gen_distance()`。

| 出力・モード | 状態 |
| --- | --- |
| 距離(`Distance<Units>`) | **実コード**。UTM へ投影して測り、単位換算する |
| `DistToInsideEdge=True` | **実コード**。宛先に `.boundary` を挟む |
| ドライブタイムモード | 未昇格。routing サービスが要る |
| 2入力モード | 未昇格。`ReturnNearest` の行選択規則が未検証 |
| **方位(`Direction`)** | **未昇格 ← 本ドキュメントの対象** |

方位の TODO を出しているのは `_direction_todos()`。

---

## なぜ後回しにできない問題なのか

`Direction` は **String 列なので golden CSV に出る**。

Spatial Info が作る `Centroid` は SpatialObj 型で、Results grid にも
golden CSV にも現れないため、値がズレても比較を汚さなかった。
`Direction` は違う。**現状の生成コードでは golden 比較で列が1本足りない。**

---

## 確定していること(実ワークフローの XML が根拠)

対象ノードは `Plugin="AlteryxSpatialPluginsGui.Distance.Distance"`。
XML 本体はリポジトリに入っていない(`.gitignore` が `*.yxmd` を除外)ため、
根拠となる断片だけをここに転記しておく。

> 以下は実ワークフローで裏取り済みだが、**ToolID・ファイル名は匿名化して
> ある**(この文書では Distance を `ToolID=D`、直前の Spatial Info を
> `ToolID=S` と呼ぶ)。設定値と MetaInfo の中身はそのままである。

### 1. `Direction` は Distance ツールが作った列

出力側 MetaInfo に、Alteryx が「どのツールが作った列か」を記録している。

```xml
<Field name="Direction" size="2"
       source="Distance: Direction Source=Centroid Destination=SpatialObj"
       type="String"/>
```

直前の Spatial Info ノード(`ToolID=S`)の MetaInfo は `Centroid` で
終わっており `Direction` は存在しない。作っているのは Distance で確定。

### 2. 8方位である

`size="2"` = 最大2文字。16方位なら `NNE` で3文字必要になるので、
`N / NE / E / SE / S / SW / W / NW` の8種で確定してよい。

### 3. 起点と終点

`source` 属性のとおり `Source=Centroid`、`Destination=SpatialObj`。
どちらも **同じレコード内の2列**(2入力ではない)。
`Centroid` は直前の Spatial Info が作った列、`SpatialObj` は
`polygons.tab`(MapInfo TAB)由来のポリゴンである。

つまり **起点は「そのポリゴン自身の重心」** であり、
**起点は常に宛先ポリゴンの内側にある**。この事実が
[落とし穴 (a)](#a-宛先にポリゴンをそのまま渡すと全行-n-になる)
の直接の原因になる。

### 4. 該当する設定

```xml
<OutputCardinalDirection value="True"/>    <!-- これが Direction を出す -->
<OutputDirectionDegrees value="False"/>    <!-- 度数出力。今回は無効 -->
<DistToInsideEdge value="True"/>
<SpatialObjSource>Centroid</SpatialObjSource>
<SpatialObjDest>SpatialObj</SpatialObjDest>
```

---

## 未確定の1点

> **ポリゴンが宛先のとき、Alteryx はどの点への方位を取っているのか。**

候補は「宛先の最寄り点」か「宛先の重心」か。

**最寄り点説が有力**。理由は上記のとおり起点が宛先ポリゴンの内側にあるためで、
宛先の重心への方位なら起点と終点がほぼ同一点になり値が定義できない。
実際に値が入っているなら最寄り点のはずである。
`DistToInsideEdge=True`(最寄りの辺までの距離)を測っていることとも整合する。

ただしこれは **推論であって検証ではない**。
丸めの境界(`N` が -22.5°〜22.5° なのか等)も未確認。

### 外部ドキュメントで裏が取れた範囲

[Alteryx 公式 Help の Distance Tool](https://help.alteryx.com/current/designer/distance-tool)
および Tool Mastery 記事の記述:

- Source は「a point or the **centroid of a polygon** to measure from」
- Destination は任意の空間オブジェクトで、距離は
  「**the closest part of the object**」まで

**距離が最寄り点基準であることは公式に確定した。**
一方 **方位も同じ点を使うとはどこにも書かれていない**。
したがって推論の格は変わらず、golden 突合は依然として必要である。

---

## 候補実装の落とし穴(実測で確認)

保留メモに書かれていた素朴な候補実装には、**2つの実害あるバグ**がある。
どちらも shapely 2.1.2 / geopandas 1.1.4 で実際に回して確認した。
golden 値が手に入ったとき、この実装をそのまま当てて判定してはいけない。

問題の候補実装:

```python
p_from, p_to = nearest_points(s, d)                       # (a) 宛先が生ポリゴン
bearing = np.degrees(np.arctan2(p_to.x - p_from.x, p_to.y - p_from.y)) % 360
labels.append(_COMPASS[int(round(bearing / 45)) % 8])     # (b) 偶数丸め
```

### (a) 宛先にポリゴンをそのまま渡すと全行 `N` になる

起点はそのポリゴン自身の重心 = **点がポリゴンの内側**。
その場合 `nearest_points()` は距離0とみなして **同一点を返す**。

```
nearest_points(centroid, poly)           -> POINT (50 10), POINT (50 10)  # 同一点
  bearing = atan2(0, 0) = 0.0            -> "N"     ← 全行これになる
nearest_points(centroid, poly.boundary)  -> POINT (50 10), POINT (50 0)
  bearing = 180.0                        -> "S"     ← 正しい(最寄りの辺)
```

宛先に `.boundary` が要る。距離側が `DistToInsideEdge=True` で
既に `.boundary` を挟んでいるのとまったく同じ理由である。

質が悪いのは、**失敗が例外ではなく「全部 `N`」という、もっともらしい列**
になる点である。golden と突き合わせた人が「最寄り点説が外れたから
重心説を試そう」と誤った分岐へ進む。

### (b) round による8方位の丸めは境界規則が非対称になる

Python の `round()` は偶数丸め(round-half-to-even)なので、
8つある境界のうち4つが「上に丸め」、4つが「下に丸め」になる。

| bearing | `int(round(x/45))` | `int(np.floor(x/45 + 0.5))` |
| --- | --- | --- |
| 22.5° | `N` | `NE` |
| 67.5° | `E` | `E` |
| 112.5° | `E` | `SE` |
| 157.5° | `S` | `S` |
| 202.5° | `S` | `SW` |
| 247.5° | `W` | `W` |
| 292.5° | `W` | `NW` |
| 337.5° | `N` | `N` |

`int(np.floor(bearing / 45 + 0.5)) % 8` なら一貫して上側に丸まる。
**この実装のままだと「境界付近だけズレる」という診断分岐を必ず踏む** ので、
Alteryx 側の境界規則を調べる前に、まずこちらを潰しておく必要がある。

### (c) ベクトル化すると欠損行で添字が黙ってズレる

行ループの代わりに `GeoSeries.shortest_line()` を使うと、距離が使うのと
**同一の最寄り点ペア**が線分で返るので、方位と距離の整合が保証される。

```
_src.shortest_line(_dst.boundary)
  -> [LINESTRING (50 10, 50 0), LINESTRING (5 5, 20 20)]
     bearings [180, 45] -> ['S', 'NE']        # 実行確認済み
```

ただし geometry が欠損している行では `shortest_line()` が `None` を返し、
`shapely.get_coordinates()` の行数が「2 × 行数」にならない。

```
入力3行(有効1・None 1・empty 1) -> 座標は2行しか返らない
```

`.notna()` でマスクして index 経由で戻さないと、**例外を出さずに
方位が別の行にずれて入る**。`_EMPTY_GEOMETRY_NOTE` が守っている
「geometry が1件も無い」ケースとは別枠のガードが要る。

---

## 投影平面の方位か、測地方位か

保留メモは「数百m スケールでは無視できる」としていたが、
**8方位に丸めても完全には無視できない**。

UTM の子午線収差(grid north と true north のズレ)は
γ ≈ Δλ · sin φ。中緯度(φ ≈ 35°)で中央子午線から 1.3° 離れれば
**0.7° 前後**になる。8方位は45°幅なので、境界から
その角度以内にある行 — 分布次第だが**数 %** — が反転しうる。

問題は誤差の大きさではなく **切り分けができなくなること** である。
反転する行は [(b) の丸め規則](#b-round-による8方位の丸めは境界規則が非対称になる)
の影響を受ける行と完全に重なるため、少数行だけズレたときに
原因が「収差」なのか「丸め」なのか判定できない。

推奨:

1. 最寄り点は **UTM 平面** で求める(距離と同じ根拠にするため)
2. その2点を EPSG:4326 に戻し、**`pyproj.Geod.inv` で測地方位**を取る

これで変数が1つ減る。pyproj は geopandas が既に依存しているので
追加の依存は発生しない。

---

## 決着のつけ方(golden 突合)

`Direction` 列を含む Alteryx 出力 CSV が用意できれば、候補実装を当てて
一致するか見るだけで確定する。必要なのは
`Centroid` / `SpatialObj` / `DistanceKilometers` / `Direction` の数行。

**行の選び方が重要**: 方位がバラける行を5〜10行選ぶ
(南寄りのポリゴンと東寄りのポリゴンが混ざるように)。
全行が同じ方位だと、[落とし穴 (a)](#a-宛先にポリゴンをそのまま渡すと全行-n-になる)
のバグと正解が区別できない。

判定の指針:

- 一致 → TODO を外して昇格。`gen_distance()` に組み込む
- 全部ズレる → 宛先の重心への方位を試す
- 境界付近だけズレる → 先に (b) を潰してから、丸め規則を調整する
- **Alteryx 側の `Direction` が全行 `N`** → 仕様ではなく Alteryx 側でも
  同じ現象が起きている可能性がある。別のポリゴンデータで再確認する

---

## まだ答えが出ていない設定の組み合わせ

`DistToInsideEdge=False` かつ起点が宛先ポリゴンの内側のとき、距離は 0 になる。
そのとき Alteryx の `Direction` が何を出すか(空文字 / `N` / 最寄り辺の方位)は
**未確定**である。

検証対象の設定は `True` なので当面の翻訳には影響しないが、
`gen_distance()` は両方を生成し分けるため、
**`False` 側は TODO に落として部分昇格を維持する** のが
`_findreplace.py` が確立した規律(検証済みの組み合わせだけ実コードにし、
それ以外は明示 TODO)に沿う。

---

## 実装するときの勘所

**場所**: `src/yxray/scaffold/_spatial.py`

- `_direction_todos()` — 今 TODO を出している関数。ここを置き換える
- `gen_distance()` — 生成本体。距離の実コードはここ
- `_geoseries_expr(df, field)` — Alteryx の空間フィールド名から
  GeoSeries 式を作る共有ヘルパ(アクティブ geometry へのフォールバック込み)
- `_METRIC_CRS_NOTE` — メートル演算の共通ルール(UTM 推定)
- `_EMPTY_GEOMETRY_NOTE` — geometry が1件も無いときのガード。
  方位にも同じガードが要る(加えて [(c)](#c-ベクトル化すると欠損行で添字が黙ってズレる) の行単位マスク)

**規律**([scaffold-architecture.md の昇格基準](scaffold-architecture.md)):

- 設定次第でコードの形が変わるツールは、golden 突合なしに昇格させない
- 対応済みの組み合わせだけ実コードにし、それ以外は明示 TODO に落とす
- 昇格させたら `docs/scaffold-architecture.md` の表と
  `tool_registry.py` の `ToolInfo`(hint 文言)を両方更新する

**hint 側と scaffold 側の同期**: `tool_registry.py` の Distance の
`python_hint` が生成コードと食い違わないようにする。
`tests/test_tool_registry.py::test_distance_hint_agrees_with_what_scaffold_generates`
がその見張り。

**テスト**: `tests/test_scaffold.py` の Distance セクション。
`_distance_config()` / `_distance_doc()` ヘルパが実XMLの設定を持っている。
現在は `test_scaffold_distance_direction_stays_todo()` が TODO を固定しているので、
昇格時はこのテストごと置き換えることになる。

**ヘルパ関数を生成コードに出す場合**: 定義そのものは生成せず、
`reference_impl/` に置いて「そこからコピーせよ」とコメントで指す規約がある
(`fill_empty` / `find_any_append` / `apply_select_edits` が実例)。
`cardinal_direction()` のような複数行の関数はこの形が合う。
その場合 `Requirement.NUMPY` の宣言も要る。

---

## 再開時の依頼文

```
docs/distance-direction-pending.md 参照
ex/Distance scaffold側: Direction(8方位)が未翻訳のまま。
golden 突合まで済んだので実装して。
Alteryx 出力の実測値は以下:
(Centroid / SpatialObj / DistanceKilometers / Direction を数行貼る)
```

golden 突合がまだなら、先に候補実装を単体スクリプトで回して
Alteryx 出力と比べるところから依頼する。
そのとき **必ず (a) と (b) を修正してから回すこと** —
未修正のまま回すと、判定そのものが壊れる。
