# Shapefile のサイドカー構造 — 「geometry しか読めない」問題の調査と対策

`gpd.read_file("xxx.shp")` の結果に geometry 列しかなく、
Alteryx XML が宣言する属性列(MESHCODE など)が見えない —
という症状の原因調査と、それを受けて scaffold に入れた対策
(PR [#67](https://github.com/azu-azu/yxray/pull/67))の記録である。

CRS(座標系)側の設計は [spatial-crs-design.md](spatial-crs-design.md) を参照。
本ドキュメントは **ファイル構成(サイドカー)** 側を扱う。

---

## TL;DR

> **Shapefile は .shp 1個では完結しない。属性列は同名の .dbf に入っている。**
> **Alteryx も GeoPandas も、.shp を指定すると同じフォルダの同名サイドカーを自動で読む。**
> **したがって「geometry しか無い」のはコードの問題ではなく、読み込み時点で .dbf がその場所に無いことを意味する。**

厄介なのは、この欠落が **エラーにならない** ことである。
GDAL は .dbf を任意扱いで開き、scaffold が Alteryx パリティのために出す
`SHAPE_RESTORE_SHX=YES` は .shp 単体すら黙って開けてしまう。
そこで scaffold は .shp 読み込みの直前に **.dbf 存在チェック** を生成し、
欠落時は `FileNotFoundError` で即座に落とすようにした。

---

## 基礎ナレッジ: Shapefile はファイル一式である

「Shapefile」は実際には、同じベース名を持つ複数ファイルの集合を指す。

```
mesh.shp   図形本体(ポリゴン等)── これだけでは属性列は無い
mesh.dbf   属性テーブル(MESHCODE, BR_Top, … の列と値)
mesh.shx   図形のインデックス
mesh.prj   座標参照系(CRS)
mesh.cpg   文字エンコーディング(あれば)
mesh.qmd   QGIS のメタデータ(読み込みには不要)
```

読み込みに使うのは `.shp + .dbf + .shx + .prj` の4点セットと考えてよい。
`.qmd` は QGIS が作る付加情報で、GeoPandas での読み込みには関係しない。

### Alteryx の7列と GeoPandas の7列は同じもの

Alteryx XML(MetaInfo)が .shp 入力に対して宣言する列と、
GeoPandas が一式を正しく読んだときの列は 1:1 に対応する。

| Alteryx | GeoPandas | 実体の在処 |
| --- | --- | --- |
| MESHCODE などの属性6列 | 同じ属性6列 | `.dbf` |
| SpatialObj | geometry | `.shp` |

Alteryx は図形列を `SpatialObj`、GeoPandas は `geometry` と呼ぶだけで、
**Python が geometry 列を「余計に追加」しているわけではない**。

### 「.shp を1個指定するだけ」で済む仕組み

Alteryx で .shp を1個指定すると7列読めるのは、
Alteryx が同じフォルダの同名サイドカーを自動参照しているからである。
そして **GeoPandas(の下の GDAL)もまったく同じことをする**。
`gpd.read_file("xxx.shp")` は同ディレクトリの `xxx.dbf` / `xxx.shx` /
`xxx.prj` / `xxx.cpg` を勝手に拾う。

つまり「geometry 以外も読む機能」を scaffold に足す必要はない。
一式が揃ってさえいれば、生成コードの `gpd.read_file(path)` のままで
属性列は全部読める。

---

## 検証結果(geopandas 1.1.4 / 実ファイルで確認)

7列(属性6列 + geometry)の Shapefile を作り、ファイル構成を変えて
`gpd.read_file` の結果を確認した。

| ケース | ファイル構成 | 結果 |
| --- | --- | --- |
| A | .shp + .dbf + .shx + .prj 一式 | **7列**、crs=EPSG:4326 |
| B | .shp 単体 + `SHAPE_RESTORE_SHX=YES` | geometry のみ、crs=None、**エラー無し** |
| C | .shp + .shx(.dbf 欠落) | geometry のみ、**エラー無し** |
| D | サイドカーが大文字拡張子(.DBF / .SHX) | **7列**(GDAL が大小文字を吸収) |
| E | .prj のみ欠落 | 7列、crs=None |

ここから分かる GDAL の挙動:

- **.dbf は任意扱い** — 無くてもエラーにならず、属性列だけが静かに消える(B, C)
- **`SHAPE_RESTORE_SHX=YES` は .shp 単体を蘇生する** — .shx を再生成して
  開けてしまうため、「.shp だけ別フォルダにコピーした」状態でも落ちない(B)
- **サイドカー探索は大小文字を吸収する** — Windows 由来の `.DBF` でも読める(D)
- **.prj 欠落は crs=None になるだけ** — これも無音(E)

---

## 今回の症状の因果関係

「Spatial Match(sjoin)の結果が想定と違う」までの連鎖は次のとおり。

```
.shp が(.dbf 抜きで)単独コピーされる
        │
        ▼
GDAL: .dbf は任意なのでエラー無し
scaffold の SHAPE_RESTORE_SHX=YES: .shx 欠落もエラー無し
scaffold の CRS 正規化: .prj 欠落も EPSG:4326 仮定で通過
        │
        ▼
geometry 1列だけの GeoDataFrame が警告ゼロで完成
        │
        ▼
gpd.sjoin(targets, universe, ...)
universe 側の属性列(MESHCODE 等)が結果に乗らない
        │
        ▼
「sjoin の結果が想定と違う」
```

要するに、**安全側の仕掛け(SHX 復元・CRS 仮定)が
「サイドカー欠落の検知器」を無効化していた** ことが問題の本質である。

---

## 決定事項と実装(PR #67)

### 採用したもの

**1. .shp 読み込みの直前に .dbf 存在チェックを生成する**(`_io.py: _shp_read_stmt`)

```python
# attribute columns live in the same-name .dbf sidecar; GDAL opens
# a .shp without it geometry-only, with no error — fail loudly
_shp = Path(INPUTS["input_1"])
if not any(_shp.with_suffix(s).exists() for s in (".dbf", ".DBF")):
    raise FileNotFoundError(f"{_shp}: .dbf sidecar not found")
df1 = gpd.read_file(_shp)
```

- 属性列が黙って消える経路(検証 B, C)を read の前で塞ぐ
- `.DBF` も許容するのは、GDAL のサイドカー探索が大小文字を
  吸収する(検証 D)ことに合わせるため
- `SHAPE_RESTORE_SHX=YES` は **維持** する。.shx 欠落を許すのは
  Alteryx パリティとして意図した挙動であり、害があるのは
  .dbf 欠落まで一緒に無音化されることだけだからである

**2. CRS 欠落時の EPSG:4326 仮定に warning を添える**(`_io.py: _crs_normalize_stmt`)

```python
if df1.crs is None:
    logger.warning(
        "no CRS metadata (missing .prj?) — assuming EPSG:4326: %s",
        _shp,
    )
    df1 = df1.set_crs("EPSG:4326")
```

4326 仮定そのものは Alteryx と同じ挙動なので変えない
([spatial-crs-design.md](spatial-crs-design.md) の設計どおり)。
ただし、元データが実は別座標系だった場合に結果が静かに狂う仮定なので、
「仮定が発動した」ことだけは実行ログに残す。

**3. `Requirement.PATHLIB` の追加**(`_common.py` / `_assemble.py`)

.md 側 scaffold のヘッダは、.shp ガードを含むときだけ
`from pathlib import Path` を、空間 read を含むときだけ
`import logging` + logger を出す(.py 側の preamble は元々両方 import 済み)。

### 採用しなかったもの

| 案 | 見送り理由 |
| --- | --- |
| `rename_geometry("SpatialObj")` で Alteryx の列名に揃える | 下流の生成コード(Create Points / sjoin)が `geometry` 名前提。golden CSV 比較でも geometry/SpatialObj は比較側で落とす運用が既にコメントに明記されている |
| 入力直後に必要列だけへ絞り込む | 列の絞り込みは Alteryx 上では Select ツールの仕事。DbFileInput の生成コードが勝手に列を落とすとワークフローとの対応が崩れる |
| XML の MetaInfo(RecordInfo)から期待列リストを取り、生成コードに assert を出す | parser は `Properties/Configuration` しか読んでおらず、モデル拡張が必要。MetaInfo は古くなり得るメタデータでもあるため、入れるなら assert より参考コメントが妥当。**将来の選択肢として保留** |

---

## トラブルシューティング早見表

生成コードを実行して空間まわりの結果がおかしいときは、
まず読み込みフォルダのファイル構成を確認する。

```python
from pathlib import Path
path = Path("mesh.shp")
for file in path.parent.glob(f"{path.stem}.*"):
    print(file.name)
```

| 症状 | 原因 | 対処 |
| --- | --- | --- |
| `FileNotFoundError: ... .dbf sidecar not found` | .dbf が同フォルダに無い | .shp と同名の .dbf(できれば .shx / .prj も)を同じフォルダへ揃える |
| 列が geometry だけ(旧生成コード) | 同上 | 同上。scaffold を再生成すればガード付きコードになる |
| `no CRS metadata (missing .prj?)` の warning | .prj が無く EPSG:4326 と仮定した | 座標値が経度緯度(139.7, 35.6 など)なら妥当。`-35000` のような値なら .prj を揃えるか正しい CRS を確認する |
| sjoin 結果に相手側の属性列が無い | universe 側が geometry のみで読まれている | 上記の .dbf 確認へ |
