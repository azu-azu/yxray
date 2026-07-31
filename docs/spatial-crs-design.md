# 空間データの座標系(CRS)設計 — 入口で WGS84 に統一する

CRS や Spatial Match という言葉に馴染みがない場合は、
先に末尾の [Appendix: CRS basics](#appendix-crs-basics) を読むことを推奨する。

---

## TL;DR

yxray が生成するコードは、空間データに対して次の方針をとっている。

> **空間データがパイプラインに入った時点で、座標系をすべて EPSG:4326 に統一する。**
> **そのため後続の Spatial Match は、座標系を意識せず結合に専念できる。**

空間データ(geometry を持つ GeoDataFrame)がパイプラインに入る入口は
**2つ** に限られており、どちらも EPSG:4326 に固定される。

```
入口① 空間ファイル                     入口② Create Points
.shp / .geojson / .gpkg / .gdb         Longitude / Latitude 列
        │                                      │
        ▼                                      ▼
gpd.read_file(...)                     gpd.points_from_xy(...)
        │                                      │
        ▼                                      ▼
_io.py が正規化コードを付加            gpd.GeoDataFrame(
        │                                  ...,
        ├─ CRS なし → set_crs             crs="EPSG:4326",
        └─ CRS あり → to_crs           )
        │                                      │
        ▼                                      ▼
GeoDataFrame(EPSG:4326)               GeoDataFrame(EPSG:4326)
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
        gpd.sjoin(...)  ← Spatial Match は CRS を意識しない
```

---

## Design principle

yxray の空間処理は、

> **入口で不変条件を確立し、内部ではその不変条件を信頼する**

という設計原則に基づいている。

空間データはパイプラインへ入る時点で EPSG:4326 に統一される。
そのため各 Spatial Match が、CRS の有無や変換の要否を
毎回確認する必要はない。

パイプライン内部では常に、次の不変条件が成立している。

```
空間 GeoDataFrame の crs == EPSG:4326
```

責務は次のように分離される。

| モジュール | 責務 |
| --- | --- |
| `_io.py` | ファイル由来の空間データを EPSG:4326 に正規化する(確立) |
| `_spatial.py` / Create Points | 新しい geometry に EPSG:4326 を付与する(確立) |
| `_spatial.py` / Spatial Match | 空間結合に限定される(信頼) |
| `_spatial.py` / Spatial Info | 重心の算出に限定される(信頼) |
| `_spatial.py` / Distance | 測るあいだだけメートル系へ投影する(一時離脱) |

`_spatial.py` の先頭 docstring にも、この分担が明記されている。

この設計にしない場合、Spatial Match のたびに毎回次のような
防御的コードが必要になる。

```python
if left.crs is None:
    ...
if right.crs is None:
    ...
if left.crs != right.crs:
    ...
```

現在の設計では、正規化は入口で一度だけ行う。

```
外部世界
  ├─ CRS なしのファイル
  ├─ 別の CRS のファイル
  └─ Create Points の X/Y 列
          │
          ▼
   EPSG:4326 に統一(入口で一度だけ)
          │
          ▼
内部パイプライン
  「空間データは全部 EPSG:4326」という不変条件
```

このように境界で不変条件を確立することで、
後続の実装は単純になり、責務も明確になる。

---

## Implementation

### 入口①: ファイル読み込み(`_io.py`)

空間ファイルの拡張子は `src/yxray/scaffold/_io.py` で定義されている。

```python
SPATIAL_EXTS = frozenset({".shp", ".geojson", ".gpkg", ".gdb", ".tab"})
```

これらの拡張子は `pd.read_csv()` ではなく `gpd.read_file()` で読み込まれる。

さらに空間ファイルを読んだ場合に限り、`read_stmt()` が
直後に `_crs_normalize_stmt()` の出力を追加する
(サイドカーを持つ形式 — .shp/.dbf と .tab/.dat — は
`_sidecar_read_stmt()` 経由で、存在チェックも前置される —
[shapefile-sidecar-anatomy.md](shapefile-sidecar-anatomy.md) 参照)。

```python
if ext in SIDECAR_EXTS:
    return _sidecar_read_stmt(target, path_expr, ext)
stmt = f"{target} = {_file_read(path_expr, ext)}"
if ext in SPATIAL_EXTS:
    stmt += "\n" + _crs_normalize_stmt(target, path_expr)
```

生成されるコードは概ね次のようになる。

```python
df = gpd.read_file(path)

# Alteryx SpatialObj is always WGS84 — assume it when CRS metadata
# is missing (e.g. .shp without .prj), reproject anything else
if df.crs is None:
    logger.warning(
        "no CRS metadata (missing .prj?) — assuming EPSG:4326: %s",
        path,
    )
    df = df.set_crs("EPSG:4326")
else:
    df = df.to_crs("EPSG:4326")
```

CRS なしの分岐が warning を出すのは、4326 仮定が
「Alteryx と同じ挙動」である一方、元データが別座標系だった場合に
結果が静かに狂う仮定でもあるため、発動したことをログに残す判断である。

### `set_crs` と `to_crs` の違い

**CRS 情報がない場合 — `set_crs("EPSG:4326")`**

座標値は **変換しない**。

`139.70, 35.69` という座標に対して
「この数字は緯度経度(EPSG:4326)として解釈する」という
ラベルを付与する操作であり、座標値そのものは変更されない。

**CRS 情報がある場合 — `to_crs("EPSG:4326")`**

座標値を **実際に変換する**。

たとえば日本の平面直角座標や Web メルカトルで保存されていた場合、
緯度経度へ計算し直す。

まとめると、`_io.py` の考え方は次のとおりである。

| 状態 | 処理 | 意味 |
| --- | --- | --- |
| CRS なし | `set_crs` | 座標値はすでに WGS84 だと **仮定** する |
| CRS あり | `to_crs` | 本当に WGS84 へ **変換** する |

### なぜ「CRS なし = WGS84」と仮定できるのか

Shapefile は通常、複数のファイルで構成される。

```
sample.shp   形状本体
sample.shx   インデックス
sample.dbf   属性テーブル
sample.prj   座標系情報
```

このうち `.prj` が欠けると、GeoPandas には座標系が分からず
`df.crs is None` になる
(サイドカー構成の詳細と .dbf 欠落時の挙動は
[shapefile-sidecar-anatomy.md](shapefile-sidecar-anatomy.md) を参照)。

そのまま Create Points 由来の EPSG:4326 データと `sjoin` すると、

```
片方: CRS None
片方: EPSG:4326
```

となって CRS 不一致の警告が出る。しかも GeoPandas は座標変換をせず、
**生の座標値どうしをそのまま比較してしまう**。
`_io.py` の `_crs_normalize_stmt()` の docstring にも、
この問題を避けるための処理だと明記されている。

そして Alteryx は SpatialObj を常に WGS84 として保持し、入力時に変換する。
yxray はこの前提を生成コード側でも再現するために
「CRS 情報がなければ WGS84 と仮定する」という判断をしている。

つまり「CRS がなければ何でも安全に WGS84 へ変換できる」のではなく、
**「Alteryx に入るデータは WGS84 である」というプロジェクト上の契約に
基づいて WGS84 と宣言している**、ということである
(この仮定が外れるケースは [Limitations](#limitations) を参照)。

### 入口②: Create Points(`_spatial.py`)

Create Points の生成コード(`gen_createpoints()`)は、
X/Y 列から geometry を作る際に最初から CRS を明示する。

```python
df_out = gpd.GeoDataFrame(
    df_in,
    geometry=gpd.points_from_xy(_x, _y),
    crs="EPSG:4326",
)
```

つまり Create Points では、

```
X = Longitude(経度)
Y = Latitude(緯度)
```

を前提として `crs="EPSG:4326"` を宣言している。

ここでも座標変換は行っていない。
入力値が WGS84 の経度・緯度であると宣言している
(`set_crs` と同じ立場である)。

### Spatial Match は CRS 処理を持たない

`gen_spatialmatch()` が生成するコードは概ね次のとおりである。

```python
df_out = gpd.sjoin(
    df_targets,
    df_universe,
    how="inner",
    predicate="intersects",   # Alteryx の Method 設定から取得
).drop(columns=["index_right"])  # sjoin の人工列。Alteryx 出力に対応物なし
```

`to_crs()` も CRS チェックも行っていないが、これは処理漏れではなく、
不変条件を信頼して責務を空間結合に限定した結果である
([Design principle](#design-principle) 参照)。

### Spatial Info は不変条件を宣言し直す

`gen_spatialinfo()` が生成するコードは概ね次のとおりである。

```python
_geom = gpd.GeoSeries(
    df_1["SpatialObj"] if "SpatialObj" in df_1.columns else df_1.geometry,
    crs="EPSG:4326",
)
df_2 = df_1.copy()
df_2["Centroid"] = _geom.centroid
```

3点、意図がある。

**1. 入力列名は XML どおりに引かず、アクティブ geometry へ落ちる。**
Alteryx は空間列を `SpatialObj` と呼ぶが、`gpd.read_file()` も Create Points も
生成フレームでは `geometry` と名付ける。XML の名前がそのまま列として存在するのは、
上流でリネームされている場合か、前段の Spatial Info が作った `Centroid` を
入力に選んでいる場合だけなので、両方に対応する形にしてある。

**2. GeoDataFrame 化ではなく GeoSeries 化。**
`gpd.GeoDataFrame(df, geometry=...)` にするとアクティブ geometry を
上書きしてしまう。重心は *列を1本足すだけ* の操作なので、フレームの
空間としての性格は変えない。

**3. `crs="EPSG:4326"` はアサーション。**
プレーンな Series ならラベル付けになり、すでに GeoSeries なら
CRS 不一致で `ValueError` になる。不変条件が崩れていたら黙って進まない。

なお `.centroid` を EPSG:4326 のまま呼ぶと GeoPandas が警告を出す
(度空間の平面重心になるため)。建物スケールでは測地的な重心との差は無視できる。
一方 **面積・長さは同じ扱いにできない** ので、`Area`/`Length` が選択されていても
生成せず TODO に落としている([Limitations](#limitations) の距離・バッファと同じ理由)。

### Distance はメートル系へ一時離脱する

`gen_distance()` は、不変条件をそのまま信頼できない唯一のツールである。
出力が「キロメートル」という **メートル単位の数値** だからで、
EPSG:4326 のまま `.distance()` を呼ぶと度が返る。

```python
_src = gpd.GeoSeries(df_1["Centroid"] if ... else df_1.geometry, crs="EPSG:4326")
_dst = gpd.GeoSeries(df_1["SpatialObj"] if ... else df_1.geometry, crs="EPSG:4326")
_crs_m = _src.estimate_utm_crs()
df_2["DistanceKilometers"] = (
    _src.to_crs(_crs_m).distance(_dst.to_crs(_crs_m).boundary) / 1000
)
```

投影の作法は
[メートル演算は UTM へ投影してから測る](#メートル演算は-utm-へ投影してから測る共通ルール)
に共通ルールとしてまとめてある。`.boundary` を挟んでいるのは
Alteryx の `DistToInsideEdge=True`(ソースがポリゴンの内側なら 0 ではなく
最寄りの辺までの距離を返す)に対応するためで、外側のときは
`.distance(poly)` と `.distance(poly.boundary)` が恒等的に一致するので
両ケースをこれ1つで満たせる。

方位(`Direction`)は生成しない。8方位の文字列であることは
MetaInfo の `size="2"` から確定できるが(16方位なら `NNE` で3文字必要)、
ポリゴン相手にどの点への方位を取るのかが XML からは決まらないためである。

### Filter や Select で何もしなくてよい理由

GeoDataFrame に対して通常の行・列操作を行っても、
geometry 列を残している限り、CRS 情報は引き継がれる。

```python
# 行のフィルタ — GeoDataFrame と CRS は保持される
df2 = df[df["status"] == "active"]

# 列の選択 — geometry を残していれば保持される
df2 = df[["id", "name", "geometry"]]
```

したがって、

```
入力時に EPSG:4326
  ↓
Filter
  ↓
Select
  ↓
Spatial Match
```

という流れで、途中のツールが毎回 `to_crs()` を行う必要はない。

ただし Select で `geometry` 列そのものを落とすと、
それ以降は空間データとして使えない。
これは CRS の問題ではなく、SpatialObj を削除したという問題である。

### intersects などが EPSG:4326 のままで動く理由

Spatial Match が使う代表的な述語は
`intersects` / `contains` / `within` / `touches` / `overlaps` などである。

これらは「交差しているか」「内側にあるか」「含んでいるか」という
**位置関係(トポロジー)の判定** であり、
両者が同じ座標系で表現されていれば距離の単位に依存せず判定できる。

そのため `gpd.sjoin(..., predicate="intersects")` は
EPSG:4326 のままで問題ない。

---

## Limitations

「CRS 不一致が絶対に起きない」わけではない。
正確には **「yxray が把握している2つの入口を必ず通り、
途中で利用者が CRS を変更しない限り起きない」** である。

### 不変条件が崩れるケース

- 生成後のコードに手作業で別の GeoDataFrame を追加した場合
- 途中で `set_crs()` / `to_crs()` を呼んで CRS を変えた場合

### 「CRS なし = WGS84」の仮定が外れるケース

`.prj` がないだけで、実際の座標値が平面直角座標だった場合、
`set_crs("EPSG:4326")` は誤った解釈になる。

- 座標が `139.7, 35.6` のような緯度経度なら妥当である
- 座標が `-35000, -42000` のような値なら疑う必要がある

### 拡張子判定をすり抜けるパス

入口①の判定は **パスの拡張子(suffix)ベース** であるため、
次のようなパスは空間ファイルとして認識されない。

| 入力パス | 現状の扱い |
| --- | --- |
| `C:\data\mesh.shp` | `gpd.read_file` + 正規化 ✅ |
| `C:\data\master.tab`(MapInfo TAB) | `gpd.read_file` + 正規化 ✅(2026-07-31 追加) |
| `C:\data\geo.gdb\layer1`(レイヤー名付き gdb) | `pd.read_csv` 扱いになり正規化されない |
| `C:\data\pts.yxdb`(SpatialObj を含み得る) | 同上 |

`.tab` はタブ区切りテキストの拡張子でもあるため、判定は拡張子だけで、
中身までは見ていない。テキストの `.tab` を読むワークフローでは
生成コードの読み込み部分を手で戻す必要がある。

このようなワークフローでは、生成されたコードの読み込み部分を
手で修正する必要がある。

### 距離やバッファは EPSG:4326 のままでは計算できない

EPSG:4326 の座標単位はメートルではなく **度** である。
したがって、次のような処理をそのまま書いてはいけない。

```python
df.geometry.buffer(100)   # NG: この 100 は「100メートル」ではなく「100度」

df1.geometry.distance(df2.geometry)   # NG: 結果はメートルではない
```

メートル単位の処理が必要な場合は、一時的に投影座標系へ変換する。

```python
original_crs = df.crs
df_metric = df.to_crs("適切なメートル系CRS")     # 例: UTM、平面直角座標系
df_metric["buffer"] = df_metric.geometry.buffer(100)
df_result = df_metric.to_crs(original_crs)
```

なお Web メルカトル(EPSG:3857)は Web 地図表示には便利だが、
場所によって距離・面積の歪みが大きい。正確なメートル計算では、
地域に合った UTM や日本の平面直角座標系など、
対象地域に適した CRS を選ぶべきである。

この問題に生成コード側で答えを出しているのが、次の共通ルールである。

### メートル演算は UTM へ投影してから測る(共通ルール)

Distance のようにメートル単位の数値を出すツールは、
不変条件(EPSG:4326)のままでは翻訳できない。かといって
ツールごとに投影先を選ぶと基準がバラつくので、
**投影先の決め方を1つに固定** している(`_spatial.py` の `_METRIC_CRS_NOTE`)。

```python
_crs_m = _src.estimate_utm_crs()          # データから UTM ゾーンを推定
_src.to_crs(_crs_m).distance(_dst.to_crs(_crs_m)) / 1000   # m → km
```

ルールは3つ。

1. **投影先はデータから推定した UTM**(`estimate_utm_crs()`)。
   ゾーン内ならスケール誤差は 0.1% 未満で、建物スケールなら cm オーダー
2. **オペランドは全部、同じ CRS へ投影する**。
   片方だけ投影すると座標系の違う数値どうしを比べることになる
3. **測るのはメートル、単位換算は最後**。
   Alteryx の `OutputUnits`(Kilometers / Miles / …)に応じて割る

EPSG:3857 は使わない。緯度によって `1/cos(緯度)` 倍に膨らむので、
東京(北緯35.7°)では距離が約 23% 過大になる。

なお、この投影は **測るあいだだけの一時離脱** であり、
出力フレームの geometry 列は EPSG:4326 のままである
(新しい列に数値を入れるだけで、フレームを投影し直さない)。

Spatial Info の Area/Length にこのルールを適用していないのは、
CRS の問題が解けても **Alteryx 側の単位設定が XML に現れない** ためで、
CRS とは別の未解決点が残っているからである。

---

## Appendix: CRS basics

### CRS とは

CRS は **Coordinate Reference System(座標参照系)** の略である。

「この座標の数字を、地球上のどこにどう対応させるか」というルールを指す。

```
CRS(座標参照系)
├── EPSG:4326        経度・緯度。単位は「度」
├── EPSG:3857        Web 地図用。単位はおおむねメートル
└── 平面直角座標系     日本の地域別。単位はメートル
```

### EPSG:4326 とは

地球上の場所を **経度・緯度** で表すためのルールである。
GPS や Google Maps などで使われる、いわば世界標準の座標系である。

たとえば東京なら次のように表す。

```
経度: 139.7
緯度: 35.7
```

`POINT (139.7 35.7)` という座標だけでは、単なる数字の組にすぎない。
どの測地系か、単位は度かメートルか、が分からないためである。

そこに `crs="EPSG:4326"` が付くと、GeoPandas は

- 139.7 は経度
- 35.7 は緯度
- 地球上のこの場所を示している

と解釈できるようになる。

### Spatial Match とは

Alteryx の Spatial Match は、
**2つの空間データを「位置関係」を条件に突き合わせるツール** である。

通常の Join は「値」で結合する(顧客 ID が同じ、商品コードが同じ、など)。
Spatial Match は「場所」で結合する。

```
通常の Join:
    店舗データ (店舗ID = 101)
    売上データ (店舗ID = 101)
    → 店舗 ID が同じだから結合

Spatial Match:
    店舗の位置   POINT (139.7 35.7)
    営業エリア   POLYGON (...)
    → 店舗の点が営業エリアの中にあるから結合
```

入力は主に2つある。

| 入力 | 例 |
| --- | --- |
| Targets | 店舗の点 |
| Universe | 市区町村の境界ポリゴン |

```
市区町村ポリゴン
┌────────────┐
│            │
│    ● 店舗   │
│            │
└────────────┘

結果: 店舗A → 杉並区、店舗B → 中野区、…
```

位置関係の判定条件(述語)には次のようなものがある。

| 述語 | 意味 |
| --- | --- |
| intersects | 交差・接触・重なりが少しでもある |
| contains | A が B を含む(市区町村ポリゴンが店舗の点を含む) |
| within | A が B の内側にある(店舗の点が市区町村ポリゴン内にある) |

`contains` と `within` は、同じ位置関係を反対側から見たものである。

```
市区町村 contains 店舗
店舗     within   市区町村
```

### なぜ座標系を揃える必要があるのか

片方のデータが経度・緯度(`139.7, 35.7`)、
もう片方がメートル座標(`15550000, 4250000`)だったとする。

どちらも東京付近を表していても、数字の表現方法がまったく違う。
コンピュータは数値をそのまま比較するため、`139.7` と `15550000` を
別の場所として扱ってしまう。

したがって空間結合の前に、両者を同じ CRS に揃えて
「同じ物差し・同じ座標表現」で比較できるようにする必要がある。
