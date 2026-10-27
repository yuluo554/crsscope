# crsscope

> **空间参考语义审计器** — 回答三个问题：**这批坐标是哪个坐标系**、**会不会整体偏几百米**、**有没有混用**。

纯本地 Python CLI（Python 3.11+，**零运行时依赖**）。运行期零网络、零遥测。
不提供坐标转换命令，不产出地图 / 切片 / 图片。

```bash
pip install -e ".[dev]"
crsscope --help
```

当前版本 `0.1.0`。**五个判定子命令全部可用**：`crsscope decl`（声明-内容一致性）、
`crsscope detect`（偏移检测与残差）、`crsscope xdiff`（跨实现差分）、
`crsscope geojson`（RFC 7946 结构与声明审计）、`crsscope tiles`（瓦片轴序 / 投影一致性）。
`crsscope report`（多份报告汇总与门禁）的参数面与契约已定，调用时以退出码 3（环境不满足）报
`not implemented`。进度见 [`plan/05-里程碑与发布.md`](plan/05-里程碑与发布.md)。

---

## 它要解决什么

头部库都在**悄悄修**或**悄悄放过**：

| 工具 | 它做的 | 它不做 / 悄悄放过的 |
|---|---|---|
| `check-geojson` | 结构校验 | README 明写不查**环方向**、不查**坐标精度**、**忽略 `crs`** |
| `geojsonhint` | 结构 lint | 已归档（2024-05-28），无后续 |
| `gcoord` / `coordtransform` | 坐标转换 | **不判定、不报残差、不查边界** |
| `PROJ` / `pyproj` | 通用投影 | **GCJ-02 / BD-09 零命中**（无 EPSG 代码） |
| `GDAL ogr2ogr` | 重投影 | 源 CRS 必须已知；GeoJSON 驱动 `RFC7946` **默认 NO** |
| `gpxpy` | GPX 解析 / 统计 | 算 max speed 时**删掉顶部 5% 的点**；1.0→1.1 **静默丢弃 `speed`** |
| `mercantile` | XYZ 瓦片换算 | API 里**没有 `tms` 形参**，"y 轴翻转"被抹平 |

**判定 / 残差 / 问责这一层没有对应输出。** 本工具只占这一层：

- 不宣称发明 GCJ-02，不宣称首创坐标转换，不宣称填补空白市场；
- 只说：这三件事（判定、残差、问责）在现有工具里找不到对应输出。

---

## 五个子命令

| 命令 | 模块 | 回答 |
|---|---|---|
| `crsscope decl <file> --declared-crs 4326` | M1 声明-内容一致性 | 声明的坐标系和坐标量级/轴序/范围**对不对得上** |
| `crsscope detect <file>` | M2 偏移检测与残差 | 更像 WGS84 / GCJ-02 / BD-09 的哪一个，**偏多少**，**哪些不确定性消不掉** |
| `crsscope xdiff <file> --target wgs84` | M3 跨实现差分 | 同一坐标喂三个本地实现，**两两差多少**，**边界结论一不一致** |
| `crsscope geojson <file>…` | M4 RFC 7946 结构 | 环方向 / 轴序 / bbox / `crs` / 精度（含 check-geojson 不查的三项） |
| `crsscope tiles <file>` | M5 瓦片投影 | `y` 轴翻转（XYZ vs TMS）、zoom↔bbox、跨 180° 环绕 |

输出双轨：`report.json`（机器可复算）+ `report.md`（人读），**同一份结果对象渲染两次**。
每条结论带 `evidence`（命中的规则 id / 声明来源 / 边界框来源）。

### 用法

```bash
crsscope --version
crsscope decl points.geojson --declared-crs 4326
crsscope detect track.gpx --mask data/mask/out/mask_v1.json
crsscope xdiff points.csv --target wgs84
crsscope geojson collection.geojson --strict-ring
crsscope tiles tiles.csv
crsscope report report.json --fail-on conflict,axis
```

公共参数：`--json`（机读到 stdout）、`--out-dir`（报告落盘目录）、`--fail-on`（命中即 exit 1 的类别，
逗号分隔；**缺省时 `conflict` / `error` 即命中**，给了该参数就收窄为只认点名的类别）、
`--allow-undecidable`（存在 `undecidable` 时仍 exit 0）。

### 最小复现（五个子命令，语料为程序化生成）

```bash
py -3.12 data/fixtures/declared_lie/gen.py --out data/fixtures/declared_lie
py -3.12 data/fixtures/swapped_axis/gen.py --out data/fixtures/swapped_axis
py -3.12 data/fixtures/water_track/gen.py --out data/fixtures/water_track
py -3.12 data/fixtures/boundary_divergence/gen.py --out data/fixtures/boundary_divergence
py -3.12 data/fixtures/geojson_struct/gen.py --out data/fixtures/geojson_struct
py -3.12 data/fixtures/tile_flip/gen.py --out data/fixtures/tile_flip
crsscope decl data/fixtures/declared_lie/out/declared_lie.geojson --declared-crs 4326 --allow-undecidable --fail-on magnitude
crsscope decl data/fixtures/swapped_axis/out/swapped_axis.geojson --declared-crs 4326 --fail-on axis
crsscope detect data/fixtures/water_track/out/water_track.gpx --mask data/fixtures/water_track/out/water_track_mask.json
crsscope xdiff data/fixtures/boundary_divergence/out/boundary_divergence.geojson --target gcj02
crsscope geojson data/fixtures/geojson_struct/out/case-001_ring_cw.geojson --strict-ring
crsscope tiles data/fixtures/tile_flip/out/tile_flip.json
```

- **`declared_lie`**：`crs` 成员声明 4326、坐标却是 3857 米域 → `magnitude` 项 `conflict`，
  上面那条命令 **exit 1**。**裸跑则 exit 5**——米域样本进不了轴序的可判定子集，`axis` 是灰区，
  而灰区优先于命中（§4.9）。
- **`swapped_axis`**：`(lon, lat)` 被写成 `(lat, lon)` → `axis` 项 `conflict`，**exit 1**；
  量级项保持 `consistent`（两类样本互不串扰，`data/README.md` §4.1 末条）。
- **`water_track`**（D2 场景）：被 GCJ-02 偏移的**陆上**轨迹。直接当 WGS84 会整条落到水面上
  （落水率 1.0），按 **GCJ02** 假设反解回落水率 **0.0** → `winner: GCJ02`、`confidence: high`；
  同时固定输出三段不可消解残差。**必须用它自带的 0.0008° 细网格**——默认 1° 网格（≈111 km）
  跨不过 GCJ-02 的 250–600 m 位移，只能落 `undecidable`（`plan/05` §二之三）。
- **`boundary_divergence`**：同一坐标喂给两库（`coordTransform_py` **开区间** / `gcoord`
  **闭区间** 的 `out_of_china`）。`(73.2°E, 39.5°N)` 经度 `73.2 < 73.66` 与 `(112.0°E, 2.0°N)`
  纬度 `2.0 < 3.86` → 两库给出**相反**结论（`boundary_table.agree: false`，进 `jumps`）；
  `(112.0°E, 5.0°N)` / `(112.0°E, 60.0°N)` 两库一致。`pairwise` 给两库的两两差分
  （`median_m` / `max_m` / `p95_m`，`max_m` 附该点坐标）；迭代不收敛的点如实报 `not_converged`。
- **`geojson_struct`**：九份用例覆盖七项检查。`case-001` 外环顺时针违反 **R1**，但按 **R2**
  （parsers SHOULD NOT reject）默认只记 **warning**——裸跑 **exit 0**，`--strict-ring` 才 **exit 1**；
  跨 180° bbox（`[177,-20,-178,-16]`）与 `geometry: null` 都只出 **info**、exit 0；
  `crs` 成员措辞固定为 "no longer used"；12 位小数触发 `precision` warning；
  坐标对只有 1 个元素 → 逐条 `structure` 错误 → **exit 4**（失败路径不落报告）。
  环方向 / 坐标精度 / `crs` 三项正是 `check-geojson` README 明示不查的。
- **`tile_flip`**：四组纯 `z/x/y` 编号，不含任何地物、**不需要底图**。
  `z=5` 下 `y=3` 与 `y=28`（`2^5-1-3`）指向同一 bbox → `axis_flip`（混用 XYZ 与 TMS）；
  `z=3, y=9` 越出 `[0,7]` → **单点即判** error；跨日界线的 `x` 环绕（`x=0` 与 `x=3` 并存）
  缺 `wrap: true` → `wrap` conflict。不做渲染 / 切片 / 图片。

> `crsscope report` 当前会以 **exit 3 + `not implemented`** 返回：参数面已定、汇总与门禁待 M6。
> 这是有意设计——未实现的命令**不许**以 0 退出，否则 CI 会把"没跑"读成"跑过且没问题"。


## 三条设计纪律（会体现在输出的每个字段上）

1. **判定而非转换**——没有 `convert` 子命令。转换只作为 M3 的对照实现留在仓库内。
2. **不确定就说不确定**——灰区一律输出 `undecidable`，并置退出码 5；不硬判。
3. **残差永远带三条不可消解声明**：民间公式只是近似 / 厂商实现差可达米级 / 边界两侧跳变。

## 数值口径

**唯一权威是 [`data/README.md` §四](data/README.md)**：量级阈值、轴序样本下限、落水评分与权重、
残差格式、灰区条件、退出码（`0/1/2/3/4/5`）、距离口径（haversine，`R = 6371008.8 m`）。
代码与本文只引用，不复制第二份。

## 已知边界

- **掩膜是构造网格，不是地理真值**：首期分辨率上限 **1°**，`unknown` 与海岸带不计入落水分母；
  需要地理准确性请用 `--mask` 提供自己的网格。本工具不下载任何掩膜。
- **GCJ-02 逆向只给"某假设下的残差与置信"**，不给"真实坐标"。
- **不做渲染**：无地图、无切片、无图片。
- **真实 `*.geojson` / `*.gpx` 不入仓**：语料一律由 `data/fixtures/**/gen.py` 程序化生成。

## 开发

```bash
py -3.12 tools/check-sprint-layout.py     # 布局门（0 全绿 / 1 有 FAIL / 2 用法）
py -3.12 tools/mutate-layout-gate.py      # 门的变异验证（每组必须变红）
py -3.12 -m pytest -q
```

方法论：本仓库遵循 `ai-tool-project-sprint` 的方法论布局，入口见 [`AGENTS.md`](AGENTS.md)。

## 许可

MIT — 见 [`LICENSE`](LICENSE)。
