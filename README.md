# crsscope

> **空间参考语义审计器** — 回答三个问题：**这批坐标是哪个坐标系**、**会不会整体偏几百米**、**有没有混用**。

纯本地 Python CLI（Python 3.11+，**零运行时依赖**）。运行期零网络、零遥测。
不提供坐标转换命令，不产出地图 / 切片 / 图片。

```bash
pip install -e ".[dev]"
crsscope --help
```

当前版本 `0.1.0`。**判定逻辑尚未实现**：五个子命令的参数面与契约已定，调用时以退出码 3
（环境不满足）报 `not implemented`。进度见 [`plan/05-里程碑与发布.md`](plan/05-里程碑与发布.md)。

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
crsscope detect track.gpx --mask data/mask/out/mask.json
crsscope xdiff points.csv --target wgs84
crsscope geojson collection.geojson --strict-ring
crsscope tiles tiles.csv
crsscope report report.json --fail-on conflict,axis
```

公共参数：`--json`（机读到 stdout）、`--out-dir`（报告落盘目录）、`--fail-on`（命中即 exit 1 的类别，
逗号分隔）、`--allow-undecidable`（存在 `undecidable` 时仍 exit 0）。

> 骨架阶段这六条命令都会以 **exit 3 + `not implemented`** 返回：参数面已定、判定逻辑待 M2–M6。
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
