# 空間データの座標系(CRS)設計 — 入口で WGS84 に統一する

yxray が生成するコードは、空間データに対して次の方針をとっている。

> **空間データがパイプラインに入ってきた瞬間に、座標系をすべて EPSG:4326 に統一する。**
> **だから後続の Spatial Match は、座標系を気にせず結合だけすればよい。**

このドキュメントでは、まず前提となる用語を整理し、そのうえで
この設計がコードのどこで、どのように実現されているかを説明する。

---

## 前提知識

### CRS とは

CRS は **Coordinate Reference System(座標参照系)** の略。

「この座標の数字を、地球上のどこにどう対応させるか」というルールのこと。

```
CRS(座標参照系)
├── EPSG:4326        経度・緯度。単位は「度」
├── EPSG:3857        Web 地図用。単位はおおむねメートル
└── 平面直角座標系     日本の地域別。単位はメートル
```

### EPSG:4326 とは

地球上の場所を **経度・緯度** で表すためのルール。
GPS や Google Maps などで使われる、いわば世界標準の座標系である。

たとえば東京なら次のように表す。

```
経度: 139.7
緯度: 35.7
```

`POINT (139.7 35.7)` という座標だけでは、単なる数字の組にすぎない。
どの測地系か、単位は度かメートルか、が分からないからだ。

そこに `crs="EPSG:4326"` が付くと、GeoPandas は

- 139.7 は経度
- 35.7 は緯度
- 地球上のこの場所を示している

と解釈できるようになる。

### Spatial Match とは

Alteryx の Spatial Match は、
**2つの空間データを「位置関係」を条件に突き合わせるツール**。

普通の Join は「値」で結合する(顧客 ID が同じ、商品コードが同じ、など)。
Spatial Match は「場所」で結合する。

```
普通の Join:
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

`contains` と `within` は同じ位置関係を反対側から見たもの。

```
市区町村 contains 店舗
店舗     within   市区町村
```

### なぜ座標系を揃える必要があるのか

片方のデータが経度・緯度(`139.7, 35.7`)、
もう片方がメートル座標(`15550000, 4250000`)だったとする。

どちらも東京付近を表していても、数字の表現方法がまったく違う。
コンピュータは単純に数字を比べるので、`139.7` と `15550000` を
別の場所として扱ってしまう。

だから空間結合の前に、両方を同じ CRS に揃えて
「同じ物差し・同じ座標表現」で比較できるようにする必要がある。

---

## 全体の流れ

空間データ(geometry を持つ GeoDataFrame)がパイプラインに入る入口は
**2つだけ** であり、どちらも EPSG:4326 に固定される。

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
        gpd.sjoin(...)  ← Spatial Match は CRS を気にしない
```

以下、それぞれの入口を順に見ていく。

---

## 入口①: ファイル読み込み(`_io.py`)

### 空間ファイルの判定

空間ファイルの拡張子は `src/yxray/scaffold/_io.py` で定義されている。

```python
SPATIAL_EXTS = frozenset({".shp", ".geojson", ".gpkg", ".gdb"})
```

これらの拡張子は `pd.read_csv()` ではなく `gpd.read_file()` で読み込まれる。

### 読み込み直後の正規化

空間ファイルを読んだ場合だけ、`read_stmt()` が
直後に `_crs_normalize_stmt()` の出力を追加する。

```python
stmt = f"{target} = {_file_read(path_expr, ext)}"
if ext in SPATIAL_EXTS:
    stmt += "\n" + _crs_normalize_stmt(target)
```

生成されるコードは実質こうなる。

```python
df = gpd.read_file(path)

# Alteryx SpatialObj is always WGS84 — assume it when CRS metadata
# is missing (e.g. .shp without .prj), reproject anything else
if df.crs is None:
    df = df.set_crs("EPSG:4326")
else:
    df = df.to_crs("EPSG:4326")
```

### `set_crs` と `to_crs` は意味が違う

ここが重要なポイント。

**CRS 情報がない場合 — `set_crs("EPSG:4326")`**

座標値は **変換しない**。

`139.70, 35.69` という座標に対して
「この数字は緯度経度(EPSG:4326)として解釈してほしい」という
**ラベルを付けるだけ** である。

**CRS 情報がある場合 — `to_crs("EPSG:4326")`**

座標値を **実際に変換する**。

たとえば日本の平面直角座標や Web メルカトルで保存されていたら、
緯度経度へ計算し直す。

まとめると、`_io.py` の考え方はこうなる。

| 状態 | 処理 | 意味 |
| --- | --- | --- |
| CRS なし | `set_crs` | 座標値はすでに WGS84 だと **仮定** する |
| CRS あり | `to_crs` | 本当に WGS84 へ **変換** する |

---

## なぜ「CRS なし = WGS84」と仮定できるのか

### `.prj` が欠けると CRS が分からなくなる

Shapefile は通常、複数のファイルで構成される。

```
sample.shp   形状本体
sample.shx   インデックス
sample.dbf   属性テーブル
sample.prj   座標系情報
```

このうち `.prj` が欠けると、GeoPandas には座標系が分からず
`df.crs is None` になる。

そのまま Create Points 由来の EPSG:4326 データと `sjoin` すると、

```
片方: CRS None
片方: EPSG:4326
```

となって CRS 不一致の警告が出る。しかも GeoPandas は座標変換をせず、
**生の座標値どうしをそのまま比較してしまう**。
`_io.py` の `_crs_normalize_stmt()` の docstring にも、
この問題を避けるための処理だと明記されている。

### Alteryx 側の規約を再現している

Alteryx は SpatialObj を常に WGS84 として保持し、入力時に変換する。
yxray はこの前提を生成コード側でも再現するために
「CRS 情報がなければ WGS84 とみなす」という判断をしている。

### ただし万能ではない

この仮定は「そのファイルの座標値が本当に WGS84 である」ことが前提。

`.prj` がないだけで、実際の座標値が平面直角座標だった場合、
`set_crs("EPSG:4326")` は誤った解釈になる。

- 座標が `139.7, 35.6` のような緯度経度なら妥当
- 座標が `-35000, -42000` のような値なら疑うべき

つまり「CRS なしなら何でも安全に WGS84 にできる」のではなく、
**「Alteryx に入るデータは WGS84 である」というプロジェクト上の契約に
基づいて WGS84 と宣言している**、ということである。

---

## 入口②: Create Points(`_spatial.py`)

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

ここでも座標変換はしていない。
入力値が WGS84 の経度・緯度であると **宣言している** だけである
(`set_crs` と同じ立場)。

---

## Spatial Match は CRS 処理を持たない

`gen_spatialmatch()` が出すコードは、ほぼこれだけ。

```python
df_out = gpd.sjoin(
    df_targets,
    df_universe,
    how="inner",
    predicate="intersects",   # Alteryx の Method 設定から取得
)
```

`to_crs()` も CRS チェックもしていないが、これは処理漏れではなく
**意図的な責務分担** である。

| モジュール | 責務 |
| --- | --- |
| `_io.py` | ファイル由来の空間データを EPSG:4326 にする |
| `_spatial.py` / Create Points | 作った点に EPSG:4326 を付ける |
| `_spatial.py` / Spatial Match | すでに揃っている前提で空間結合だけする |

`_spatial.py` の先頭 docstring にも、この分担が明記されている。

これは設計としては **「不変条件を入口で確立する」** という考え方である。

パイプライン内部では常に

```
空間 GeoDataFrame の crs == EPSG:4326
```

というルールが成立している。そうすれば Spatial Match のたびに

- CRS はあるか?
- 一致しているか?
- 変換が必要か?

を確認せずに済む。

---

## Filter や Select で何もしなくてよい理由

GeoDataFrame に対して通常の行・列操作をしても、
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

という流れで、途中のツールが毎回 `to_crs()` する必要はない。

ただし Select で `geometry` 列そのものを落とせば、
それ以降は空間データとして使えない。
これは CRS の問題ではなく、SpatialObj を削除したという問題である。

---

## intersects などが EPSG:4326 のままで動く理由

Spatial Match が使う代表的な述語は
`intersects` / `contains` / `within` / `touches` / `overlaps` など。

これらは「交差しているか」「内側にあるか」「含んでいるか」という
**位置関係(トポロジー)の判定** であり、
両方が同じ座標系で表現されていれば距離の単位に依存せず判定できる。

そのため `gpd.sjoin(..., predicate="intersects")` は
EPSG:4326 のままで問題ない。

---

## 距離やバッファでは事情が変わる

EPSG:4326 の座標単位はメートルではなく **度** である。
したがって、次のような処理をそのまま書いてはいけない。

```python
df.geometry.buffer(100)   # NG: この 100 は「100メートル」ではなく「100度」
```

距離計算も同じで、結果は度を基準にした値になる。

```python
df1.geometry.distance(df2.geometry)   # NG: メートルではない
```

メートル単位の処理が必要な場合は、一時的に投影座標系へ変換する。

```python
original_crs = df.crs
df_metric = df.to_crs("適切なメートル系CRS")     # 例: UTM、平面直角座標系
df_metric["buffer"] = df_metric.geometry.buffer(100)
df_result = df_metric.to_crs(original_crs)
```

### EPSG:3857 は万能ではない

Web メルカトル(EPSG:3857)は Web 地図表示には便利だが、
場所によって距離・面積の歪みが大きい。

正確なメートル計算では、

- 地域に合った UTM
- 日本なら平面直角座標系

など、対象地域に適した CRS を選ぶべきである。

なお、現状の scaffold が生成する Spatial Match は述語ベースだけなので、
**生成コードの範囲ではこの問題は起きない**。
生成後のコードに手作業で距離・バッファ処理を足すときの注意点である。

---

## この設計の核心

一言でいうと、**境界で正規化し、内部を単純にする**。

悪い設計は、Spatial Match のたびにこうなる。

```python
if left.crs is None:
    ...
if right.crs is None:
    ...
if left.crs != right.crs:
    ...
```

今の設計は、入口で一度だけ統一する。

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

yxray 全体でいうと、

- `_io.py` と `gen_createpoints()` が空間データの **不変条件を確立** し、
- `gen_spatialmatch()` はその不変条件を **信頼** して、
  本来の責務である空間結合だけを担当する

という分担になっている。

---

## この設計が保証しないこと

「CRS 不一致が絶対に起きない」わけではない。
正確には **「yxray が把握している2つの入口を必ず通り、
途中で利用者が CRS を変更しない限り起きない」** である。

次のような場合、不変条件は崩れる。

- 生成後のコードに手作業で別の GeoDataFrame を追加した
- 途中で `set_crs()` / `to_crs()` を呼んで CRS を変えた

また、入口①の判定は **パスの拡張子(suffix)ベース** なので、
拡張子判定をすり抜けるパスは空間ファイルとして認識されない。

| 入力パス | 現状の扱い |
| --- | --- |
| `C:\data\mesh.shp` | `gpd.read_file` + 正規化 ✅ |
| `C:\data\geo.gdb\layer1`(レイヤー名付き gdb) | `pd.read_csv` 扱いになり正規化されない |
| `C:\data\pts.yxdb`(SpatialObj を含み得る) | 同上 |

このようなワークフローでは、生成されたコードの読み込み部分を
手で直す必要がある。
