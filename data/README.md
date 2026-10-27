# data · 依据查证、数据源可获取性与数值口径

> 本文件是**数值口径的唯一权威（§四）**。`plan/01`、代码注释、`README.md` 只可引用；若与 §四冲突，**以 §四为准**，并在同一提交内修正摘录。
>
> **代理实际检索窗口**：**2026-10-27T10:56Z–11:30Z**。以下全部查证、`gh api` 检索、源码实读、RFC 与 EPSG 原文拉取均发生在此窗口内。
>
> **窗口内不可达（如实标注，不当作 0 结果）**：
> - `github.com` 直连被重置 → 仓库元数据改走 `gh api`（含 `gh search code`）读取，**未**依赖网页渲染。
> - `en.wikipedia.org` 与 `wiki.openstreetmap.org` **443 超时** → 本文**不引用**任何维基条目作为事实来源；涉及 GCJ-02 性质的表述只引用**可直连的 HN/V2EX 原话**与**实读源码**。
> - `rfc-editor.org` **✅ 可直连**；`epsg.io` **✅ 可直连**。
>
> **三态标记**：✅ 已核对原文（可指到具体行/字段）/ ⬜ 软论据或未核对 / ⚠️ 部分受限（写明阻断原因）。

---

## 一、依据查证记录

### 1.1 RFC 7946 原文台账（✅ 实读；`curl https://www.rfc-editor.org/rfc/rfc7946.txt`，HTTP **200**，**49143 bytes**）

| 编号 | 条款 | 原文（照录，未改写） | 位置 | 本仓用法 |
|---|---|---|---|---|
| **RFC7946-R1** | 环方向（**MUST**） | "A linear ring MUST follow the right-hand rule with respect to the area it bounds, i.e., exterior rings are counterclockwise, and holes are clockwise." | §3.1.6（txt 行 **468–474**；§7.1 行 **1446** 重述） | 模块 M4 `ring_order` 的判据来源 |
| **RFC7946-R2** | **紧接上一句，对校验器极关键** | "For backwards compatibility, parsers SHOULD NOT reject Polygons that do not follow the right-hand rule." | §3.1.6 同段 | **决定 R1 违规只降级为 warning**；`--strict-ring` 才升 error（§4.9） |
| **RFC7946-R3** | 轴序 `lon, lat` | "The first two elements are longitude and latitude, or easting and northing, precisely in that order and using decimal numbers." | §3.1.1 | 模块 M1 轴序判定、模块 M4 `axis` |
| **RFC7946-R4** | bbox 与跨 180° | `"[west, south, east, north]"`；跨 180° 时"northeast corner longitude **小于** southwest corner longitude"是合法的 | §7.1（txt 行 **1449**）、§5.2 斐济例子 `[177.0,-20.0,-178.0,-16.0]` | 模块 M4 `bbox`：`west > east` **不得**报错 |
| **RFC7946-R5** | **`crs` 成员：没有 "MUST NOT"** | §4 只说坐标系是 WGS 84 / `urn:ogc:def:crs:OGC::CRS84`；替代坐标系 "has been removed from this version…"；并留活口 "where all involved parties have a prior arrangement, alternative coordinate reference systems can be used"。Appendix B.1 只说 'the "crs" member of [GJ2008] is no longer used' | §4、Appendix B.1 | 模块 M4 `crs_member` 文案固定为 "**no longer used**" |
| **RFC7946-R6** | null geometry / null properties | Feature 的 geometry 可为 JSON `null`（"in the case that the Feature is unlocated"）；properties 可为 JSON object 或 `null` | §3.2 | 模块 M4：两者都**不得报错** |

> ⚠️ **纠错留档（最高优先级）**：一次性 WebFetch 摘要曾声称 §4 有 "crs MUST NOT"。**实读原文没有该强制条款。** 本仓一律按"不再使用（no longer used）"表述；发布门执行全仓字符串扫描（`plan/00` 决策 ①）。**本文件出现该短语的两处都只是否定说明本身（R5 行与这段），不存在任何肯定式表述。**
>
> ⚠️ **R1 与 R2 必须成对引用**：只引 R1 → 做出"拒绝合法历史数据"的校验器；只引 R2 → 放过真正的方向错误。

### 1.2 EPSG 台账（✅ `epsg.io/<code>.json` 实读 PROJJSON，非二手转述）

| EPSG | 名称 | 类型 | 注册表轴序（PROJJSON 原文） | 单位 | 本仓用法 |
|---|---|---|---|---|---|
| **4326** | WGS 84 | `GeographicCRS` | **`Geodetic latitude: north`**, **`Geodetic longitude: east`** | degree | 轴序陷阱的**正例**：注册表是 **(lat, lon)**，RFC 7946 是 **(lon, lat)** |
| **3857** | WGS 84 / Pseudo-Mercator | `ProjectedCRS` | `Easting: east`, `Northing: north` | **metre** | 量级判定（米域）与 4326 混用检测 |
| **4490** | CGCS2000 | `GeographicCRS` | 同 4326（**latitude 在前**） | degree | 与 4326 混淆检测（轴序与量级都相同 → 只能靠声明与一致性判） |

- **可确证的两条陷阱**：① EPSG 注册表 4326 是 `(lat, lon)`，GeoJSON/RFC7946 是 `(lon, lat)`；② 3857 单位是**米**、4326 是**度**。两者都"看起来对"，因为海岸线形状不变。
- **GCJ-02 / BD-09 未在 EPSG 注册（无 EPSG 代码）** —— 本仓**不编造**任何 EPSG 编号：
  - 实证：`gh search code 'gcj repo:OSGeo/PROJ'` → **0 命中**；
  - 对照组：`gh search code 'Pseudo-Mercator repo:OSGeo/PROJ'` → **3 命中**（证明 code search 本身工作正常，0 不是检索失灵）。
  - **结论**：`--declared-crs` 的合法枚举 = `4326` / `3857` / `4490` / `crs84`；GCJ-02 与 BD-09 只能作为**检测假设**（`detect` 的候选），**不能作为声明值**。

### 1.3 GCJ-02 两库实测台账（✅ 实读源码，非传闻）

> **路径口径**：本仓只登记**已实测的函数名与常数**。未记录到具体文件的**不写路径**（避免编造）；后续如需固定到行，必须在开发时重新打开源码记录。

| 编号 | 实现 | 星数（窗口快照） | 函数 | 判定式（源码原文） | 逆向算法 |
|---|---|---|---|---|---|
| **CT-PY-BBOX** | `wandergis/coordTransform_py` | 1234★ | `out_of_china(lng, lat)` | `lng` ∈ **(73.66, 135.05)** 且 `lat` ∈ **(3.86, 53.55)** —— **开区间** | — |
| **CT-PY-INV** | 同上 | — | `gcj02_to_wgs84(lng, lat)` | —— | **一步线性近似**：`return [lng * 2 - mglng, lat * 2 - mglat]` |
| **GCOORD-BBOX** | `hujiulong/gcoord` | 3324★ | `isInChinaBbox(lon, lat)` | `lon` ∈ **[72.004, 137.8347]** 且 `lat` ∈ **[0.8293, 55.8271]** —— **闭区间** | — |
| **GCOORD-INV** | 同上 | — | `gcj02towgs84`（逆向） | —— | **定点迭代**：`while (Math.abs(dx) > 1e-6 \|\| Math.abs(dy) > 1e-6)` |
| **GCOORD-CONST** | 同上 | — | 前向常数 | `a = 6378245`；`ee = 0.006693421622965823` | 克氏椭球参数，原样照录 |

**可复现的分歧点**（本题 M3 的核心交付，不是任何一方的 bug）：

| 样本 | `coordTransform_py` | `gcoord` | 结论 |
|---|---|---|---|
| **(73.2°E, 39.5°N)** 新疆西部 | 经度 `73.2 < 73.66` → **境外、不偏移** | `lon ≥ 72.004` 且 `lat` 在域内 → **境内、偏移** | **结论不同**（经向分歧） |
| **(112.0°E, 2.0°N)** 低纬 | 纬度 `2.0 < 3.86` → **境外、不偏移** | `lat ≥ 0.8293` → **境内、偏移** | **结论不同**（纬向分歧） |
| **(112.0°E, 5.0°N)** 对照 | `lat 3.86 < 5.0 < 53.55` → 境内 | `lat` 在域内 → 境内 | **结论相同**（都偏移） |
| **(112.0°E, 60.0°N)** 对照 | 纬度超 53.55 → 境外 | 纬度超 55.8271 → 境外 | **结论相同**（都不偏移） |

> **纠正（规划阶段的一处错误，已修）**：早期设想把"南沙一带 **5°N**"当作纬向分歧样本——**代入常数后不成立**：5°N 同时落在两库纬度域内，两库都判"境内"。真正的纬向分歧必须取 **< 3.86°N**。本仓**不编造分歧**，语料因此固定为上面三例（两分歧 + 一一致），并额外保留一格"都不偏移"的对照。

**性质与精度（✅ 原话 + ✅ 源码，丑话说在前面）**：

- HN 用户引官方名"**地形图非线性保密处理算法**"，称其 "deliberately obfuscated with a **nonlinear** transform"（D1，见 §1.4）。
- **逆向精度**：数值可解——迭代法以 `1e-6°` 容差收敛，约合 **0.1 m**（按 §4.4 的距离口径，1° ≈ 111 km 量级）。
- **不可消解的不确定性（三条，输出必须声明）**：
  1. **民间公式只是近似**：公开版本并非官方未公开实现的等价物；
  2. **厂商差异可达米级**：高德 / Google 中国 / 腾讯各自的实现与数据不一致（V2EX t/442775 原话："高德用 GCJ-02，GCJ-02 转 WGS84 有误差"）；
  3. **边界两侧跳变**：`out_of_china` 是硬边界，边界内外的输出不连续；且**两库边界不同**（见上表）。
- **因此**：`detect` 的结论永远是"**在某组假设下的残差与置信**"，**禁止宣称唯一真值**；`residual.kind` 三段固定（§4.5）。

### 1.4 需求侧原话（✅ 逐条对照 URL，窗口 2026-10-27T10:56Z–11:30Z）

| 编号 | 来源 | 原话（节选，未改写） | 用途 |
|---|---|---|---|
| **D1** | HN **482 分**（2024-05-01）· https://news.ycombinator.com/item?id=40220072（评论 40243314） | "GCJ-02 is based on WGS-84, but with a deliberate obfuscation algorithm…random offsets… **as little as 50m to as much as 500m**" | 偏移量级锚点 |
| **D2** | HN 7689338（2014-05-03，Strava 热力图）· https://news.ycombinator.com/item?id=7689338 | "The major routes are offset north and west of the actual roads: i.e. **People are not really running/riding through lakes and rivers** ;)" | **M2 落水启发式的来源** |
| **D3** | HN 7136213（2014-01-28）· https://news.ycombinator.com/item?id=7136213 | "**a point on the map doesn't know whether it's in geographic coordinates or in the current projection**…we frequently [get] all sorts of fun little bugs" | M1/M5 的动因 |
| **D4** | HN 10966241（2016）· https://news.ycombinator.com/item?id=10966241 | 用 GPS 记录 + 回国跑代码给照片打点，"completely confusing" | 混用场景 |
| **D5** | V2EX t/1071777（**2024-09-10**）· https://www.v2ex.com/t/1071777 | "国行 iPhone 拍照…Exif 中的 GPS 坐标是 GCJ-02…**拍照位置与网站中差个几百米**" | 时代性（2024 仍在发生） |
| **D6** | V2EX t/442775（**2018-03-30**）· https://www.v2ex.com/t/442775 | "无人机 GPS 获取的是 WGS84…高德用 GCJ-02，**GCJ-02 转 WGS84 有误差**。但是这类操作对于坐标精度要求高" | 厂商差异 |
| **D7** | V2EX t/68827（2013-05-14）· https://www.v2ex.com/t/68827 | "求可以对 KML\GPX 文件进行火星坐标纠偏的工具" | GPX 侧需求 |
| **D8** | V2EX t/517697（44 回复）· https://www.v2ex.com/t/517697 | 公交查询定位偏移 | 通用需求 |
| **D9** | V2EX t/822513 · https://www.v2ex.com/t/822513 | 腾讯地图无反向 API | 无真值来源 |
| **D10** | V2EX t/1087212（**2024-11-06**）· https://www.v2ex.com/t/1087212 | "几百米误差" | 时代性 |
| **D11** | V2EX t/771181（2021-04-16，26 回复）· https://www.v2ex.com/t/771181 | "GPX Tracker…可惜坐标系不同，偏移太严重了" | GPX 侧需求 |
| **D12** | V2EX t/1009745（2024-01-18）· https://www.v2ex.com/t/1009745 | "我还是没找到一个'完美的'能在 web page 上展示 gpx 轨迹文件的在线地图" | 形态边界（不做渲染） |
| **D13** | V2EX t/240175（2015-12-01）· https://www.v2ex.com/t/240175 | "找不到一个能编辑 gpx 的软件" | 弃选依据（编辑器已有人要，我们不做） |
| **P1** | Show HN（**2026-09-21**）· https://news.ycombinator.com/item?id=49784845（工具页 `9revolution9.com/tools/geo/geojson-viewer`） | "I kept hitting the same two problems with GeoJSON: **a bbox that no longer matched the data after an edit, and coordinates written as [latitude, longitude]**" | **既有先例**：需求真实但已有人做 → 必须差异化 |
| **P2** | HN《Lon Lat Lon Lat》**336 分** · https://news.ycombinator.com/item?id=30228981（评论 30230091） | "The ordering of lat/lon is not the only tricky part…two levels of abstraction" | 轴序需求的普遍性 |

### 1.5 头部库能力矩阵（✅ 逐个实读 README / 源码 / 驱动页；星数为窗口快照）

| 工具 | 星数 | 覆盖什么 | **不覆盖什么（本题的落点）** |
|---|---|---|---|
| `OSGeo/PROJ` | 2032★ | 通用投影 / 基准变换 | **无 GCJ-02 / BD-09**（code search 0 命中） |
| `pyproj` | 1234★ | PROJ 的 Python 绑定 | 同上 |
| `proj4js` | 2244★ | JS 侧通用投影 | 同上 |
| `OSGeo/gdal` | 6120★ | `ogr2ogr -t_srs` 重投影 | **源 CRS 必须"已知"**，不能从数据反推；GeoJSON driver `RFC7946=[YES/NO]` **"Defaults to NO"** → 默认输出走 GeoJSON 2008，**不强制右手法则** |
| `wandergis/coordtransform` | 4654★ | WGS84/GCJ02/BD09 互转 | **不判定、不报残差、不查边界** |
| `wandergis/coordTransform_py` | 1234★ | 同上（Python） | 同上；逆向是**一步线性近似**（§1.3） |
| `hujiulong/gcoord` | 3324★ | 同上 + WebMercator | 同上；逆向是**定点迭代**（§1.3） |
| `Turfjs/turf` | 10526★ | 含 `booleanValid` | **几何有效性**，与参考系无关 |
| `shapely`（GEOS） | 4533★ | 几何有效性 / 拓扑 | 同上 |
| `mapbox/geojsonhint` | 257★ | 结构 lint（errors + warnings） | **已归档（2024-05-28）**；README 指向 check-geojson |
| `placemark/check-geojson` | 86★ | 接棒结构校验 | README 原文：**"Unlike geojsonhint, this checker _only_ produces errors, not warnings…excessive coordinate precision / **right-hand rule compliance** — This does not check for. Additionally, the `crs` member is **ignored** by this tool"** |
| `mapbox/geojson-rewind` | 133★ | 改写环方向（Shoelace） | **只修不报** |
| `@turf/rewind` | （turf 内） | 外环 CCW / 内环 CW | **只修不报** |
| `tkrajina/gpxpy` | 1106★ | GPX 解析 / 统计 | README 原文：算 `max_speed` 时 **"removes the top `5%` of speeds and points with nonstandard distance (those are usually GPS errors)"**；GPX 1.0→1.1 **静默丢弃 `speed`**（"changes in the speed attribute will be lost after gpx.to_xml()"）→ **把异常藏起来** |
| `GPSBabel` | 553★ | 格式转换 / 轨迹处理 | 转换与清洗，不做"这批点是哪个系"的判定 |
| `mapbox/mercantile` | 452★ | XYZ 瓦片换算 | 实读 `mercantile/__init__.py`：**`grep -ci tms` = 0**；`_getBboxZoom/minmax` 返回 `(0, 2**zoom-1)` → **API 里没有 `tms` 形参**，"y 轴翻转"被抹平 |
| `geojson-vt` | 2081★ | 矢量瓦片切片 | 切片引擎，非审计 |
| `mapshaper` | 4197★ | 几何编辑 / 简化 | 编辑工具，非审计 |
| `supercluster` | 2385★ | 点聚合索引 | 与参考系无关 |
| `chrieke/geojson-validator` | 42★ | 结构校验（含 RFC 7946 部分项） | 不做坐标系判定；不做 GCJ 检测 |
| `chrieke/geojson-invalid-geometry` | 51★ | 构造无效几何样本 | 测试数据生成，非审计器 |
| `jajego/geolint` | 5★ | 结构 lint | 同上 |

### 1.6 开源空白检索（⬜ 软论据：`gh api` 检索式 + `total_count`，窗口 2026-10-27 ~11:00–11:25Z）

| 检索式 | total_count | 头部 / 说明 |
|---|---|---|
| `gcoord in:name` | **24** | hujiulong/gcoord 3324★ |
| `coordtransform in:name` | **46** | wandergis/coordtransform 4654★、coordTransform_py 1234★、pg-coordtransform 486★、qichengzx 273★ |
| **`wgs84 gcj02 detect in:name,description`** | **0** | — |
| **`coordinate crs detection heuristic in:name,description`** | **0** | — |
| `geojson linter in:name,description` | **8** | jajego/geolint 5★ |
| `geojson validation` | **136** | chrieke/geojson-validator 42★、chrieke/geojson-invalid-geometry 51★ |
| `geojson-validation in:name` | **8** | 最高 4★ |
| `rfc7946 in:name,description` | **9** | geojson-kotlin 19★（编解码器） |
| `gpxpy in:name` | **21** | tkrajina/gpxpy 1106★ |
| `gpsbabel in:name` | **40** | 553★ |
| `gpx analysis in:name,description` | **183** | TrailScope 8★、GPXDataAnalyzer 7★，余为健身/爬坡分析 |
| `gps track cleaning in:name,description` | **87** | 最高 17★（fitness app） |
| `mercantile in:name` | **203** | mapbox/mercantile 452★ |
| `supercluster in:name` | **202** | 2385★ |
| `geojson-vt in:name` | **42** | 2081★ |
| `mapshaper in:name` | **41** | 4197★ |

**⬜ 未计入空白的旁证（0 命中，仅说明"没人用这套词"）**：HN "TMS XYZ tiles" 0 命中；HN "tile offset one off" 1407 命中但**全是游戏等距瓦片**（噪声，不作证据）。

**判定（措辞固定）**：**"判定与残差"这一位置空着**；不宣称首创、不宣称空白市场。

---

## 二、数据源可获取性记录

| 数据源 | 状态 | 获取路径 | 实测结果与阻断说明 |
|---|---|---|---|
| RFC 7946 全文 | ✅ **已获取** | `curl https://www.rfc-editor.org/rfc/rfc7946.txt` | HTTP 200，**49143 bytes**；行号引用见 §1.1。**原文不入仓**（体积 + 可重新获取），只入摘录与行号 |
| EPSG 注册表 PROJJSON | ✅ **已获取** | `https://epsg.io/<code>.json`（4326 / 3857 / 4490） | 直连可用；轴序与单位见 §1.2 |
| GCJ-02 两库源码 | ✅ **已读** | `gh api` 读仓库内容 | 常数与判定式见 §1.3；**代码不入仓**（许可与体积），只入常数与函数名 |
| 真实全球陆水掩膜（高分辨率） | ⚠️ **未采用** | — | **未在检索窗口内核对任何真实全球陆水数据的许可与可获取性**（`wikipedia.org` / `wiki.openstreetmap.org` 443 超时）。**因此首期不引入任何真实地理掩膜**，见 §2.1 |
| 用户自有掩膜 | ✅ 支持 | `--mask <file>` | 用户本地提供的网格文件（格式见 §2.1），**运行期不下载** |
| 真实 GeoJSON / GPX 数据 | ⬜ **不入仓** | — | `.gitignore` 封 `*.geojson` / `*.gpx`；语料一律**程序化构造**（§三） |
| GitHub 检索 API | ⚠️ **部分受限** | `gh api search/*` | `github.com` 直连被重置 → 全部走 `gh api`；**未遇到 403 限流**（如实记录：本次无 403） |

### 2.1 离线掩膜：分辨率上限与诚实边界

- **首期形态**：`data/mask/gen.py` 生成一个**构造的**极低分辨率陆水网格（JSON：`cells` 按 `(lat_idx, lon_idx)` 索引，取值 `land` / `water` / `unknown`），网格步长 **≤ 1°**（上限，§4.3）。
- **它不是地理真值**：网格内容为**构造**，只用于"落水率"启发式的**演示、回归与口径固定**，**不承诺海岸线准确性**。报告必须同时输出 `mask_version` 与 `mask_max_resolution_deg`，并附一句"掩膜为构造低分辨率网格，非地理真值"。
- **生产口径**：需要地理准确性时，用户必须用 `--mask <file>` 提供自己的网格（同格式）。**本工具不下载掩膜、不内置任何真实地理数据。**
- **未知格纪律**：`unknown` 格的占比必须进报告；`unknown` **不计入落水分母**（§4.2）。海岸带（与异类相邻的格）在评分时**不计入分母**并单独计数。

---

## 三、合成数据纪律

1. **语料全部程序化构造**，由 `data/fixtures/**/gen.py` 生成；生成器**固定输入、无随机、无时间依赖**，`--check` 重生成逐字节一致。
2. **四份基础语料**（`plan/01` §四 第 3 项）：
   - `four-crs/`：**同一个物理点**分别写成 **WGS84 / GCJ-02 / BD-09 / WebMercator** 四份（四份互为同一地点的不同表示，金标记录任两份之间的位移）；
   - `swapped-axis/`：把 `(lon, lat)` 写成 `(lat, lon)`（**必须能被模块 M1 命中**）；
   - `declared-lie/`：`crs` 成员声明 `4326`，但坐标量级是米（**必须能被模块 M1 命中**）；
   - `boundary-divergence/`：`(73.2, 39.5)` 经向分歧、`(112.0, 2.0)` 纬向分歧、`(112.0, 5.0)` 与 `(112.0, 60.0)` 两组"两库一致"对照。
3. **假地名与保留坐标**：
   - 地名只用虚构名（如"示例谷 / Example Valley"），**不出现任何真实村庄、军事设施、敏感地物名**；
   - 坐标优先取**海洋或无人区**的整数/半整数点（构造用），避免落进真实生产点位；
   - 业务 id 形如 `case-\d{3}` / `demo-\d{3}`，**不出现**真实用户、设备、轨迹来源。
4. **金标来源纪律**：
   - 涉及**两库边界**的金标（§1.3 分歧表）由生成器**直接代入常数**算出，可复算；
   - 涉及**落水率**的金标只对"构造掩膜 + 构造点"成立，**不得**当作真实世界结论；
   - 涉及 GCJ-02 位移的金标标注为"**在某一实现下**的位移"，不写"真实偏移"。
5. **不入仓**：任何真实 `*.geojson` / `*.gpx` / 真实 GPS 轨迹 / 真实照片 EXIF 导出；**不接受"脱敏后的真实轨迹"**（脱敏不可验证）。`fixtures/out/` 为生成中间产物，入 `.gitignore`。

---

## 四、数值口径（唯一权威）

> 本节所有阈值、评分、格式、灰区条件、退出码**一处定义**；`plan/01`、代码注释、`README.md` 只可引用，**不得复制第二份**。

### 4.1 量级与轴序判定（模块 M1）

记 `m = max(|x|, |y|)` 为该点坐标分量绝对值的最大者；`declared` 为声明 CRS。

| 判定 | 定义 | 输出 |
|---|---|---|
| **度域** | `m ≤ 180` | 与 `declared ∈ {4326, 4490, crs84}` 相容 |
| **米域** | `m ≥ 1_000_000` | 与 `declared = 3857` 相容（Web Mercator 全球范围的分量量级为 `10^7` 米） |
| **中间带** | `180 < m < 1_000_000` | 既非度域也非米域的标准量级 → `undecidable`（附 `magnitude_band: neither`） |
| **量级冲突** | `declared` 是度制 **且** `m > 180` | **`conflict`（`reason: magnitude`）** —— 这条**必须**命中"声明 4326 但坐标量级 1e6"的样本 |
| **单位冲突** | `declared = 3857` **且** `m ≤ 180` | `conflict`（`reason: unit`） |

**轴序判定**（只用可判定样本）：

- 可判定样本 = 满足 `|a| ≤ 180 且 |b| ≤ 180` 的坐标对 `(a, b)`。
- **写反（`conflict`, `reason: axis`）** ⟺ 存在可判定样本使 **`|b| > 90` 且 `|a| ≤ 90`**（第二分量越出纬度域，第一分量仍在经度域 → 呈 `(lat, lon)` 形态）。
- **正序（`consistent`）** ⟺ 存在可判定样本使 `|a| > 90` 且 `|b| ≤ 90`（第一分量越出纬度域 → 只能是经度）。
- **`undecidable`** ⟺ 全部可判定样本都落在 `±90` 内（无法区分两种排列）。
- **样本下限**：可判定样本数 `< 5` → 整项 `undecidable`（`reason: insufficient_samples`），**不得**凭 1–2 个点下结论。
- **两类样本互不串扰**：`declared-lie`（量级）与 `swapped-axis`（轴序）必须各自触发对应 `reason`；同一份样本同时触发两条是允许的，但**验收要求各自单独命中**。

### 4.2 落水评分与假设排序（模块 M2）

对候选假设 `h ∈ {WGS84, GCJ02, BD09}`，先求"若 `h` 为上文的假设，则真实坐标 = `inverse_h(p)`"，再评分：

```
water_ratio(h)  = 落水点数 / 可判定点数          # 可判定点 = 掩膜非 unknown 且非 coastal
boundary(h)     ∈ {0, 1}                          # 任一可判定点需跨 out_of_china 边界才成立 → 1
declared(h)     ∈ {0, 1}                          # h 与 --declared-crs 矛盾的强证据 → 1

score(h) = (1 - water_ratio(h)) - 0.25 * boundary(h) - 0.30 * declared(h)
```

| 项 | 取值 |
|---|---|
| 排序 | `score` 降序；同分按假设名字典序（`BD09` < `GCJ02` < `WGS84`） |
| **`confidence = high`** | 第一名领先第二名 **≥ 0.15** |
| **`confidence = medium`** | 领先 **≥ 0.05** 且 `< 0.15` |
| **`confidence = low`** | 领先 **> 0** 且 `< 0.05` |
| **`confidence = undecidable`** | 领先 **= 0**，或可判定点数 `< 30`，或 `unknown + coastal` 占样本 **> 80%** |

- **`unknown` / `coastal` 不计入落水分母**（避免"掩膜看不见的湖"被当作"陆上正确"）。
- **边界外**：样本全部落在假设的 `out_of_china` 域外时，输出 **`out_of_coverage`**（不是"WGS84 胜出"），并附两个 `boundary_profiles` 的各自结论。
- **边界带**：任一点距某库边界 `< 0.05°`（≈ 5.5 km）时打 `boundary_jump` 标记，并把该假设的 `confidence` 上限压到 `medium`。

### 4.3 掩膜分辨率与覆盖（模块 M2）

| 项 | 口径 |
|---|---|
| 网格步长上限 | **1°**（首期）；超出即拒绝加载（`exit 3`） |
| 必须进报告的字段 | `mask_version`、`mask_max_resolution_deg`、`unknown_ratio`、`coastal_ratio`、`evaluable_points` |
| 可判定点下限 | **30**（含）；不足 → `undecidable` |
| 掩膜缺失 | `exit 3`（环境不满足），**不得**默认"全是陆地" |

### 4.4 距离口径（全项目共用）

- **球面大圆距离（haversine）**，地球平均半径 `R = 6371008.8 m`。
- 输出单位**米**，保留 **0.1 m**；`offset_m` 取各点位移的**中位数**，并同时给 `p95_offset_m`。
- 两两差异（`xdiff`）：给 `median_m` / `max_m` / `p95_m`，并对 `max_m` 附该点的坐标。
- **禁止**用平面欧氏距离代替（度与米混算会静默产生错误量级）。
- 角度与距离的换算**只在 `geodesy.py` 一处实现**。

### 4.5 残差报告格式（模块 M2，固定三段）

`residual` 必为数组，元素 `kind` 取自固定枚举，**三段齐全**：

| `kind` | 固定文案要点 |
|---|---|
| `formula_approximation` | 民间公开公式是对未公开实现的近似，不保证等价 |
| `vendor_divergence` | 高德 / Google 中国 / 腾讯等实现差异可达米级，同一坐标可能对应不同"真值" |
| `boundary_jump` | `out_of_china` 为硬边界，边界两侧输出不连续；两库边界框不同（§1.3） |

- 字段格式：`{"kind": ..., "detail": ..., "affected_points": N}`
- **禁止**输出"已还原为 WGS84 真实坐标"一类断言；允许"在 `h` 假设下的坐标"。
- `confidence` 枚举：`high` / `medium` / `low` / `undecidable`（§4.2）。

### 4.6 GeoJSON 严重级别（模块 M4）

| 级别 | 触发 |
|---|---|
| `error` | 结构不可解析；坐标对非数值；`type` 与几何维度不符；bbox 长度不为 4/6 |
| `warning` | **环方向违反 R1（默认）**；`crs` 成员存在（"no longer used"）；坐标有效数字超阈值；bbox 与几何真实外包框不一致 |
| `info` | `geometry: null`、`properties: null`（**合法**，只做提示）；`bbox` 跨 180°（**合法**，R4） |

- **`--strict-ring`**：把 R1 违规从 `warning` 升为 `error`。**这是唯一升级路径**；默认**不**升级（R2：`parsers SHOULD NOT reject`）。
- **坐标精度阈值**：单分量小数位 **> 9** → `precision` warning（9 位十进制 ≈ 0.1 mm，对任何地表坐标无意义）。
- **禁止**把 R1 违规默认为 `error`；**禁止**把 `crs` 成员的措辞写成任何强制禁用表述。

### 4.7 瓦片判定（模块 M5）

| 项 | 口径 |
|---|---|
| `y` 轴混用 | 同一 `z` 下同时出现 `y` 与 `(2^z - 1 - y)` 且两者都指向同一 bbox → `axis_flip` = true |
| `y` 越界 | `y ∉ [0, 2^z-1]` → `error`（单点即判，静态可检） |
| `zoom ↔ bbox` | 给定 bbox 的瓦片覆盖集合必须单调嵌套（`z+1` 的集合 ⊆ `z` 的集合展开）；破坏即 `conflict` |
| 跨 180° | `x` 环绕必须显式记录 `wrap: true`；缺席但经纬跨越日界线 → `conflict` |

- **不做渲染、不产出图片、不做切片**；输出只有布尔 / 数值判定与证据。

### 4.8 灰区条件（必须输出 `undecidable`，不得硬判）

1. 可判定样本/点数低于 §4.1（5 点）或 §4.2（30 点）的下限；
2. 掩膜 `unknown + coastal` 占比超过 §4.2 的上限；
3. 候选假设分差为 0（并列第一）；
4. 轴序无法区分（全部样本在 ±90 内）；
5. 样本落在边界带（`< 0.05°`）→ `confidence` 上限 `medium` 并打 `boundary_jump`；
6. 数据声明与内容互相矛盾且无法判定谁是错的（如声明 `4490` 但坐标呈米域：可能是声明错，也可能是单位标错）。

### 4.9 退出码（全子命令共用，一处定义；优先级为全序）

**优先级（从高到低）**：`2` → `3` → `4` → `5` → `1` → `0`。

| 码 | 语义 | 触发 |
|---|---|---|
| `0` | 成功且无命中 | 无 `--fail-on` 命中项，且无 `error` 级发现 |
| `1` | 判定命中 | `--fail-on` 指定类别出现在结果集中（`conflict` / `axis` / `magnitude` / `ring` / `axis_flip` …，逗号组合） |
| `2` | 用法错误 | 参数缺失 / 互斥 / 非法枚举（含把 GCJ-02 当 `--declared-crs`） |
| `3` | 环境不满足 | 文件不存在、掩膜缺失或步长超 1°、算法常数未加载 |
| `4` | 输入数据无效 | JSON/GPX 不可解析、坐标对非数值、结构破碎（逐条记录但整体按 4 退出） |
| `5` | 结论不可判定 | 存在 `undecidable` 且未开启 `--allow-undecidable`（默认把"判不出来"当作需人工介入，**与 0 严格区分**） |

- 退出码只看结果集，不看人读文本；`--json` 与 `report.md` 的退出码必须相同。
- `4` 优先于 `5`：结果集不完整时"是否不可判定"不是可信结论。
- **不存在其他退出码**；新增语义必须在本节加行并说明优先级位置。

### 4.10 报告头字段（缺一不可）

| 字段 | 含义 |
|---|---|
| `tool_version` | 本工具版本 |
| `declared_crs` | 声明值（或 `none`） |
| `mask_version` / `mask_max_resolution_deg` | 掩膜坐标（模块 M2 必填） |
| `evaluable_points` / `unknown_ratio` | 可判定点数与未知占比 |
| `generated_at` | 唯一允许的时间戳（ISO 8601 UTC；可用 `SOURCE_DATE_EPOCH` 固定以便逐字节比对） |

- 除 `generated_at` 外**不得**含任何时间戳；不得含绝对路径 / 主机名 / 用户名。

---

## 五、维护纪律

- 本文档的每条事实都标三态；**未取到原文的一律 ⬜ 并写明阻断原因**（443 超时 / 直连被重置 / 403 限流 / 仓库 404 都如实写，**不当作 0 结果**）。
- **星数、`total_count`、检索命中**是窗口快照，随窗口漂移；**不得**进代码常量、README 首屏或断言阈值。
- **可进断言的量只有算法常数**（`a`、`ee`、两套边界框、迭代容差 `1e-6`）与 §四的**口径阈值**（它们来自源码原文与设计决定，不是统计）。
- 若 §四任一条被修改，必须在 `plan/00` 决策记录新增一行说明理由，并同步检查 `plan/01` 的摘录。
- 任何"RFC 条款 / EPSG 编号 / GCJ-02 细节 / 日期"的**新增表述**都必须先有原文或源码，否则标 ⬜；**编造即违规**。
