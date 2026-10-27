# 00 · README 总览 — 10-27-crsscope（空间参考语义审计器）

> **方法论装订**：本项目遵循 `ai-tool-project-sprint` 方法论；布局门 = `py -3.12 tools/check-sprint-layout.py`；装订日期 2026-10-27。新对话第一件事 = 跑这条门。
>
> - **性质**：不参赛项目题 · 发布 GitHub **公开仓库** · 署名 `yuluo554`
> - **交付形态**：**纯本地 Python CLI**（可进 CI；**不做地图渲染、不联网**）。唯一形态，不设备选。
> - **定位宣言**（原文照录）："所有头部库都在**悄悄修**：geojsonhint 已归档、check-geojson 明示不查环方向且忽略 `crs`、gcoord/coordtransform 只转换不判定、PROJ 里 GCJ-02 零命中、GDAL 的 RFC7946 默认 NO、gpxpy 把异常删掉不报。**'判定 + 残差 + 问责'这一层无人占位。** 本工具回答：这批坐标是哪个坐标系、会不会整体偏几百米、有没有混用、残差多少。"
> - **检索窗口**：代理实际检索窗口 **2026-10-27T10:56Z–11:30Z**（`wikipedia.org` / `wiki.openstreetmap.org` 443 超时、github.com 直连被重置，均如实标注；`rfc-editor.org` 与 `epsg.io` 可直连 ✅）
> - **状态**：**M2 声明-内容一致性 + M3 GCJ 检测与残差 + M4 跨工具差分 + M5 GeoJSON 结构 / 瓦片投影已完成**（2026-10-27）：`crsscope decl` 五项判据（量级 / 轴序 / 单位 / 混用 / 范围）、`detect` 六环节（逆变换 / 覆盖检查 / 三路评分 / 排序置信 / 残差三段 / 边界画像）、`xdiff` 三实现差分（两两米级差异 / 两库边界结论表 / 跳变点 / `not_converged` 如实报出）、`geojson` 七项结构与声明审计（含 check-geojson 明示不查的环方向 / 精度 / `crs` 三项；R1+R2 成对分级）、`tiles` 五项轴序/投影检查（`y` 轴翻转静态检出、`y` 越界单点即判、`zoom_bbox`、`wrap`、3857/4326 混用）全部落位；D2 类水域轨迹可复现、边界外不硬判、两类边界分歧均可复现；M1 数据先行（七份 fixture + 离线掩膜）已在位。**只剩 `report` 未实现**（里程碑 M6，exit 3 + `not implemented`）——进度以 `plan/05` 状态表为准。

---

## 文档索引表

| 文档 | 内容 | 状态 |
|---|---|---|
| `plan/00-README总览.md` | 本文档：索引 / 决策记录 / 弃选项 / 承诺-证据台账 / 里程碑 | ✅ v1 |
| `plan/01-题目文档.md` | 十段式题目定稿：头部（含与时区题的切割）/ 介绍（头部库矩阵 + RFC 原文 + EPSG 轴序 + GCJ 两库边界差异 + 需求原话 + 空白检索 + 差异化）/ 任务要求（M1–M5）/ 提交材料 / 评分四栏 / 含金量锚点 / 边界与非目标 / 交付形态 / 风险 / 变更记录 | ✅ v1 |
| `data/README.md` | 依据查证记录（三态 + URL + 检索窗口）/ RFC 7946 原文台账 / EPSG 台账 / GCJ-02 两库实测台账 / 头部库能力矩阵 / 数据源可获取性 / 合成数据纪律 / **数值口径（唯一权威，§四）** | ✅ v1 |
| `.gitignore` | Python 标准模板 + `*.geojson` / `*.gpx` 真实数据不入仓 + `fixtures/out/` | ✅ v1 |
| `plan/02-架构与技术选型.md` | 分层架构（geodesy / algorithms / mask / io / 五子命令 / report）、依赖方向、选型与弃选、确定性设计 | ✅ v1 |
| `plan/03-模块详设.md` | 五模块接口、数据结构、判定顺序、失败路径、测试点 | ✅ v1 |
| `plan/04-数据计划.md` | fixture 生成器确定性纪律、掩膜构建流程、金标回填口径 | ✅ v1 |
| `plan/05-里程碑与发布.md` | 每里程碑 DoD、已知未验证项、环境事实、发布流程 | ✅ v1 |
| `plan/06-交付对标与决策.md` | 题面逐条落位、缺口表、风险登记 | ✅ v1 |
| `AGENTS.md` | 方法论锚点：强制布局清单 + 门命令 + 新对话第一动作 | ✅ v1 |
| `tools/check-sprint-layout.py` | 布局门（零依赖，10 条判据） | ✅ v1 |
| `tools/mutate-layout-gate.py` | 门的变异验证（每组必须变红） | ✅ v1 |
| `plan/HANDOFF-*.md` | 里程碑交接单 | ✅ M1 / M2 / M3 / M4 / M5 / M6 已出（`plan/HANDOFF-M1.md` ～ `plan/HANDOFF-M6.md`） |
| `plan/RELEASE-M6.md` | 发布留档（tag 时点 / tag 后追加两栏） | ⬜ 待建（M6） |

> 状态列随里程碑同步翻转；不得一处标 ✅ 而另一处标 ⬜。

---

## 决策记录表

> 本表同时登记已定案决策与弃选项（弃选项见下一节）。**前五条是本题的产品地基与事实地基，不得在后续文档中被改弱；第 ① 条是纠错条款，优先级最高。**

| 日期 | 决策 | 结论与理由 |
|---|---|---|
| 2026-10-27 | **①【纠错·最高优先级】RFC 7946 §4 没有 "crs MUST NOT"** | 一次性 WebFetch 摘要曾声称 §4 含"crs MUST NOT"。**实读原文**（`curl https://www.rfc-editor.org/rfc/rfc7946.txt`，HTTP 200，49143 bytes）：§4 只说坐标系是 WGS 84 / `urn:ogc:def:crs:OGC::CRS84`，替代坐标系 "has been removed from this version…"，并留活口 "where all involved parties have a prior arrangement, alternative coordinate reference systems can be used"；Appendix B.1 只说 'the `crs` member of [GJ2008] is no longer used'。**本仓所有文档、代码注释、报告文案一律按"不再使用（no longer used）"表述，禁止出现 "crs MUST NOT"。** 发布门加一条字符串扫描（见 §承诺-证据台账末行）。 |
| 2026-10-27 | **② 环方向 MUST 逆时针，但必须紧接引用"解析器 SHOULD NOT 拒绝"** | §3.1.6 原文两句话相邻："A linear ring MUST follow the right-hand rule…exterior rings are counterclockwise, and holes are clockwise." + "For backwards compatibility, parsers SHOULD NOT reject Polygons that do not follow the right-hand rule." **只引前句会做出"拒绝合法历史数据"的校验器**（大量存量数据方向就是错的，而规范明确要求解析器容忍）。因此 M4 的环方向检查**分级为 warning 而非 error**，并在报告里成对引用两句。**变异靶子**：把 R2 从代码里删掉 → 环方向必须升级为 error → 单测必须失败。 |
| 2026-10-27 | **③ GCJ-02 逆向的诚实边界：数值可收敛 ≈0.1 m，但不得宣称唯一真值** | 迭代法收敛容差 `1e-6°` ≈ 0.1 m 是**数学上的收敛**，不是**事实上的还原**。三条不可消解不确定性：(a) 民间公式只是对未公开实现的近似；(b) 厂商实现（高德 / Google 中国 / 腾讯）差异可达**米级**（V2EX t/442775 原话"GCJ-02 转 WGS84 有误差"）；(c) `out_of_china` 边界两侧存在**跳变**。因此 `detect` **必须**输出 `offset_m` + `confidence` + `residual.kind` 三段，**禁止**输出"精确还原为 WGS84"这类断言。 |
| 2026-10-27 | **④ 两库中国边界框不同（73.66–135.05 vs 72.004–137.8347）是可复现的审计发现点，不是 bug** | 实读源码：`coordTransform_py` 的 `out_of_china` 用 `lng∈(73.66,135.05) ∧ lat∈(3.86,53.55)`；`gcoord` 的 `isInChinaBbox` 用 `lon∈[72.004,137.8347] ∧ lat∈[0.8293,55.8271]`。**同一坐标在两边可能得出相反结论**，这是本题 M3 的核心交付（`boundary_table`）。文档**不得**把它表述为"某个库写错了"——两边都是各自的选择，缺的是"把分歧报出来"的工具。 |
| 2026-10-27 | **⑤ Show HN 2026-09-21 已有 GeoJSON 校验器先例，M4 必须靠 M1/M2/M3 差异化** | 该工具页自述："I kept hitting the same two problems with GeoJSON: **a bbox that no longer matched the data after an edit, and coordinates written as [latitude, longitude]**"。需求真实，但**做浏览器版单文件校验器 = 同质竞争 + 滑向可视化**。故：形态固定为 **CLI / CI 批量审计**；GeoJSON 结构检查**降为 M4 的一个模块**，产品差异全部压在 M1（声明-内容一致性）/ M2（偏移+残差）/ M3（跨实现差分）。 |
| 2026-10-27 | **⑥【实例纠正】"南沙 5°N"不构成两库分歧，5°N 用作对照** | 规划阶段曾把"新疆西部 73.2°E"与"南沙 5°N"并列为两类边界分歧样本。**按两库常数逐条代入后不成立**：5°N 同时落在 `coordTransform_py` 的 `lat∈(3.86,53.55)` 与 `gcoord` 的 `lat∈[0.8293,55.8271]` 内，两库都判"在中国"→ 结论**相同**。真正的纬向分歧必须取 **< 3.86°N**（如 2.0°N：`coordTransform_py` 判"境外、不偏移"，`gcoord` 判"境内、偏移"）。因此语料改为：**经向分歧 73.2°E + 纬向分歧 2.0°N + 对照组 5°N/112°E（两库一致）**，三例齐备。**不编造分歧**，这是本题"可复现"纪律的直接体现。 |
| 2026-10-27 | **⑦ 数值口径单点定义在 `data/README.md` §四** | 量级阈值 / 轴序可判定样本下限 / 落水评分与权重 / 残差报告格式 / 灰区（`undecidable`）条件 / 退出码 / 距离口径（§4.4）七项一处定义。`plan/01`、代码注释、README 只可引用，**不得复制第二份**。理由：本题结论对"阈值取多少"和"灰区怎么判"极敏感，两处口径必然漂移。 |
| 2026-10-27 | **⑦b 骨架阶段的空实现必须 exit 3 且打 `not implemented`** | `decl` / `detect` / `xdiff` / `geojson` / `tiles` / `report` 在 M2–M6 之前抛 `UnimplementedFeature`（映射到 §4.9 的 3）。**不许返回空结果集**：那会以 exit 0 退出，把"没实现"读成"跑过且没问题"。守门见 `tests/test_unimplemented_contract.py`。 |
| 2026-10-27 | **⑧ 不写漂移硬数字** | 星数（3324★ / 4654★ / 257★ …）与检索 `total_count` 全部标注为"**检索窗口 2026-10-27T10:56Z–11:30Z 快照**"；**不得**进代码常量、不得作断言阈值、不得作 README 卖点。唯一允许进断言的量是**算法常数**（`a=6378245`、`ee=0.006693421622965823`、两套边界框、迭代容差 `1e-6`），因为它们来自源码原文而非统计。 |
| 2026-10-27 | **⑨ 里程碑编号与模块编号是两套，映射固定写在本文档** | 里程碑按**交付顺序**编号（M1 语料先行 → … → M6 发布）；模块按**能力**编号（模块 M1 声明一致性 … 模块 M5 瓦片投影）。二者相差一位且**不是同一件事**，任何文档引用时必须写"里程碑 Mx"或"模块 Mx"。映射见 §里程碑表下方注。 |
| 2026-10-27 | **⑩ 品牌隔离与时区题切割** | 本系列已有一题做**时区/时间语义**；本题只做**空间**语义。时间戳只作从属输入（"缺时间戳 → 速度无法判定 → 落水启发式降级"）。文档/代码/提交信息**不得提名任何其他项目**，不引用其结论、不复用其代码。 |
| 2026-10-27 | **⑪【§4.9 细化】"命中"的定义写死，灰区优先于命中** | 里程碑 M2 落地时发现 §4.9 的 `1` 行（"`--fail-on` 指定类别出现"）与 `0` 行（"无 `--fail-on` 命中项"）在**裸命令**（不给 `--fail-on`）下的语义互斥：按 0 行字面读法，一份明显 `conflict` 的数据会以 0 退出，与 README 三条设计纪律的"判定而非放过"相反。定为：**`conflict` / `error` 级发现默认即命中 → `1`；`--fail-on` 给定时收窄为只认点名的类别**（类别名可匹配 `status`/`reason`/`check`）。同时写死**灰区优先**：`undecidable` 一出现即 `5`（除非 `--allow-undecidable`），不因同一结果集另有 `conflict` 而被吞掉（依据 = README 纪律 2"灰区一律输出 undecidable 并置退出码 5"）。`warning` 默认不算命中，必须 `--strict-ring` / `--fail-on` 显式点名——否则 R1 环方向违规（§4.6 默认 warning）会把历史数据判成失败，违反"分级而非拒绝"。落点：`data/README.md` §4.9 定义块 + `errors.outcome_code`，守门 = `tests/test_decl.py::test_outcome_code_default_states` / `test_fail_on_narrows_the_hit_set`。 |
| 2026-10-27 | **⑫【M4 落地细化】`xdiff` 的差分方向、适用实现与 `not_converged` 处置** | 三处口径在落地时写死，理由都来自"不编造差分"这条纪律：①**方向**——输入坐标被读作 `--target` 指定的坐标系，每个实现把它转成 **WGS84**（三者唯一可比的公共参照系），差分在 WGS84 输出之间做；②**适用实现**——三个实现覆盖的坐标系不同（§1.5），`gcj02`/`bd09` 只用两库（`coordTransform_py` 开区间 / `gcoord` 闭区间），`webmercator` 只用 `gcoord`/`proj4js`，`wgs84` 三实现恒等差分 0；把不适用者塞进来只会造出**虚假差分**；③**`not_converged` 处置**——gcoord 定点迭代在个别点（闭区间内、开区间外的极端坐标，如 `(72.05, 0.83)`）超上限不收敛，`xdiff` 把它归为 `undecidable`（`reason: not_converged`）**而非** `conflict`：判不出来 ≠ 判定命中，且**不得**静默返回一个"看起来对"的值（题面 §M3 纪律）。落点：`src/crsscope/xdiff.py`，守门 = `tests/test_xdiff.py`。 |
| 2026-10-27 | **⑬【M5 落地细化】GeoJSON 分级、结构错误出口与 `axis_flip` 的可证条件** | 四处口径在落地时写死，理由都是"判据必须可被变异咬住、不得靠文案充数"：①**`ring_order` 的级别由 R2 推导**——`_ring_order_status()` 读 `RFC_R2` 里的容忍语义标记（`SHOULD NOT reject`）：在 → `warning`，不在 → `error`；`--strict-ring` 是另一条显式升级路径。删掉 R2 分支，`tests/test_geojson.py::test_ring_level_is_derived_from_r2` 立刻红。②**结构性问题不能靠 `error` 状态折算退出码**——`errors.outcome_code` 把 `error` 归为"命中 → 1"，而 §4.9 要求非法 JSON / 坐标对非数值 / 结构破碎一律 `4`。故 `geojson.run()` 先逐条收集 `structure/error`（`audit()` 可见），再整体抛 `InvalidInput`（失败路径零副作用）。③**`axis_flip` 的"同一 bbox"必须可证**——只凭同 `z`/`x` 下 `y` 与 `2^z-1-y` 并存会误伤相邻两行；判据要求组级/单枚 bbox 相同，**或** `scheme` 明写 `xyz`/`tms`。fixture 的 `bbox` 是"两枚指向同一 bbox"的声明，不用于反算瓦片号。④**语料缺陷修正**——`geojson_struct/gen.py` 的 `_feature()` 曾把 `properties=None` 吞成默认 dict，使 `case-005` 落盘的 `properties` 不是 `null`（与金标 `properties_is_null: true` 矛盾）；改用哨兵默认值后 `--check` 10/10 逐字节一致。落点：`src/crsscope/geojson.py`、`src/crsscope/tiles.py`，守门 = `tests/test_geojson.py` / `tests/test_tiles.py`。 |

---

## 弃选项汇总（附理由与已占证据）

| 弃选项 | 一句话理由 | 已占证据 |
|---|---|---|
| **纯坐标转换库 / 服务** | 只作 M3 的**对照实现**存在于仓库内；不提供 `convert` 子命令、不承诺 API 稳定 | `coordtransform` **4654★**、`coordTransform_py` **1234★**、`gcoord` **3324★**、`PROJ` 2032★、`pyproj` 1234★、`proj4js` 2244★ |
| **纯瓦片换算工具** | 需求证据最弱（v2ex/HN 无强原话），原生产品已成熟 → **降为 M5 的一个检查项**，且不做切片引擎 | `mercantile` **452★**、`geojson-vt` **2081★**、`supercluster` 2385★、`mapshaper` 4197★ |
| **GPX 编辑器 / 可视化 / 3D 回放** | 已占且滑入可视化禁区 → 只保留"物理可行性判定"从属检查 | `gpxpy` **1106★**、`GPSBabel` **553★**；v2ex t/240175 求"能编辑 gpx 的软件"正是编辑器需求，已被满足 |
| **完整 GIS 几何校验** | GEOS/turf 已占且滑向数学形式化（自相交、拓扑修复），与参考系语义无关 | `shapely` **4533★**、`Turfjs/turf` **10526★**（`booleanValid`） |
| **纯 GeoJSON 浏览器校验器** | Show HN 2026-09-21 已有直接先例 → 同质竞争 + 可视化风险；语义检查项保留为 M4，形态改 CLI/CI | https://news.ycombinator.com/item?id=49784845（9revolution9.com/tools/geo/geojson-viewer） |
| **栅格瓦片渲染 / 切片引擎** | 与审计无关；M5 明确不做可视化 | `geojson-vt` 2081★、`mapshaper` 4197★、`mercantile` 452★ |
| **"点落海里判坐标系"独立成题** | 只是 M2 的一个评分维度，单独立题会退化成噱头（且依赖掩膜分辨率，证据强度不足以独立支撑） | — 无直接竞品，但形态过薄 |
| **在线厂商 API 反查坐标系** | 破坏零网络红线，且把结论交给不可复算的黑箱 | 隐私红线（§`plan/01` 七） |
| **修补/纠正输出（`--fix`）** | 会退化为"又一个转换器"，并掩盖"数据本身有问题"这一结论；首期只判定与报告 | `geojson-rewind` 133★、`@turf/rewind` 已占"只修" |

---

## 承诺-证据台账

> 全项目只此一份；其他文档只可引用，不得复制。状态列随里程碑同步翻转。

| 承诺项 | 素材来源 | 交付物内可达性 | 核验方式 | 状态 |
|---|---|---|---|---|
| 声明-内容一致性判定（量级 / 轴序 / 范围 / 混用） | EPSG 台账（4326 lat 在前、3857 米）✅ | `crsscope decl` | "声明 4326 + 量级 1e6"与"轴序写反"**各自单测**（`tests/test_decl.py`，吃真实语料） | ✅ 已交付（里程碑 M2，2026-10-27） |
| GCJ-02 / BD-09 偏移检测 + 残差 | 两库源码实质 ✅ | `crsscope detect` 的 `winner`/`confidence`/`offset_m` | D2 类水域轨迹复现；边界外 `out_of_coverage` | ✅ 已交付（里程碑 M3，2026-10-27） |
| 不可消解残差三段声明 | §2.4 三条不确定性 ✅ | `detect` 的 `residual.kind` | 三段文案齐全性断言 | ✅ 已交付（里程碑 M3，2026-10-27） |
| 边界框不一致显式警告 | 两库常数 ✅ | `detect` 的 `boundary_profiles` | 73.2°E 样本两 profile 结论必须不同 | ✅ 已交付（里程碑 M3，2026-10-27） |
| 跨实现两两差分（米） | 本地算法重实现 ✅ | `crsscope xdiff` 的 `pairwise` | 三实现同点对拍，差异量级可解释（`tests/test_xdiff.py`，吃真实语料） | ✅ 已交付（里程碑 M4，2026-10-27） |
| 两库边界结论表 | 决策 ④ / ⑥ ✅ | `xdiff` 的 `boundary_table` | 73.2°E 分歧 + 2.0°N 分歧 + 5°N 一致（四行逐字段对拍 `boundary_divergence/expect.json`） | ✅ 已交付（里程碑 M4，2026-10-27） |
| GeoJSON 环方向（R1+R2 成对） | RFC 7946 §3.1.6 ✅ | `crsscope geojson` 的 `ring_order` | 删 R2 → 级别升级 → 测试失败（变异） | ✅ 已交付（里程碑 M5，2026-10-27） |
| `crs` 成员提示（"no longer used"） | RFC 7946 §4 / App. B.1 ✅ | `geojson` 的 `crs_member` | 断言措辞不含 `MUST NOT`；**发布门全仓字符串扫描** | ✅ 已交付（里程碑 M5，2026-10-27） |
| bbox 跨 180° 合法 | RFC 7946 §7.1 + §5.2 斐济例 ✅ | `geojson` 的 `bbox` | 跨日界线样本不得报 error | ✅ 已交付（里程碑 M5，2026-10-27） |
| null geometry / null properties 合法 | RFC 7946 §3.2 ✅ | `geojson` | `geometry: null` 不得报错 | ✅ 已交付（里程碑 M5，2026-10-27） |
| 坐标精度检查 | check-geojson 明示不查 ✅ | `geojson` 的 `precision` | 超出阈值的样本出 warning | ✅ 已交付（里程碑 M5，2026-10-27） |
| 瓦片轴序静态检出 | mercantile 无 `tms` 形参 ✅ | `crsscope tiles` 的 `axis_flip` | 翻转样本静态检出（无需底图） | ✅ 已交付（里程碑 M5，2026-10-27） |
| zoom ↔ bbox / 跨 180° 环绕 | — | `tiles` | 覆盖数与单调性自洽 | ✅ 已交付（里程碑 M5，2026-10-27） |
| 四份语料（四坐标版本 / 写反轴序 / 声明撒谎 / 边界分歧） | 程序化构造 | `data/fixtures/**/gen.py` + `expect.json` | `--check` 重生成逐字节一致 | ✅ 已交付（2026-10-27） |
| 离线水陆掩膜（≤1°） | 仓库内构造 | `data/mask/` | 分辨率上限声明 + 未知格不计入分母 | ✅ 已交付（2026-10-27） |
| 零网络 / 零遥测 | — | 全部子命令 | 断网跑通；代码内无 HTTP 客户端 → `tests/test_no_network.py`（AST 扫全仓 `import`） | 🟡 守门已落位；**断网实跑待 M6** |
| 零第三方运行时依赖 | — | `pyproject.toml` + `src/**` | `tests/test_no_third_party.py`（AST 扫全仓 import，只允许标准库 + 本包） | ✅ 骨架已落位（2026-10-27） |
| 未实现能力必须 exit 3 且打 `not implemented` | 决策 ⑦b | 五子命令 + `report` | `tests/test_unimplemented_contract.py` | ✅ 骨架已落位（2026-10-27） |
| fixture 可重建 | 生成脚本固定输入 | `data/fixtures/**/gen.py --check` | 逐字节一致 | ✅ 已交付（2026-10-27） |
| 发布三件套 | — | tag / Release 附产物 / `plan/RELEASE-M6.md` | tag 树内含留档；附件 sha256 | ⬜ 待建（里程碑 M6） |
| **发布门：全仓不含肯定式 "MUST NOT"** | 决策 ① | `README.md` / `AGENTS.md` / `plan/**` / `src/**` / `data/**` | `tests/test_wording.py` 全仓扫描（允许"RFC 没有该条款"这类否定句，禁止任何强制禁用式表述） | 🟡 守门已落位；**发布门 `tools/check-release.py` 待 M6** |

---

## 里程碑

> **编号说明（决策 ⑨）**：里程碑按交付顺序编号；模块按能力编号，二者相差一位。

| 里程碑 | 内容 | 出口门 | 状态 |
|---|---|---|---|
| 出题阶段 | 题面定稿 + 数据台账 + 骨架入库 | `plan/00` + `plan/01` + `data/README.md` + `.gitignore` 齐；事实全部三态标注；`git log -1` 可见首提交 | ✅ 已完成（2026-10-27） |
| M1 | **数据先行** | 七份语料（`four_crs` / `swapped_axis` / `declared_lie` / `boundary_divergence` / `water_track` / `tile_flip` / `geojson_struct`）全部由 `gen.py` 生成且 `--check` 逐字节一致；`expect.json` 金标回填；**离线掩膜（1°）构建脚本 + 覆盖率自检** | ✅ 已完成（2026-10-27） |
| M2 | **声明一致性**（模块 M1） | "声明 4326 + 量级 1e6" 与 "轴序写反" 两类样本**各自**命中（互不串扰）；可判定样本不足 → `undecidable` | ✅ 已完成（2026-10-27） |
| M3 | **GCJ 检测与残差**（模块 M2） | D2 类水域轨迹可复现（正确假设把落水率压到近零）；边界外输出 `out_of_coverage`；`residual.kind` 三段齐；`boundary_profiles` 两库结论可不同 | ✅ 已完成（2026-10-27） |
| M4 | **跨工具差分**（模块 M3） | 73.2°E 与 2.0°N 两类分歧均报出，5°N 报一致；迭代不收敛报 `not_converged`，不静默 | ✅ 已完成（2026-10-27） |
| M5 | **GeoJSON 结构（模块 M4）+ 瓦片/投影（模块 M5）** | check-geojson 不查的三项都查；R1+R2 成对引用可被变异咬住；`y` 轴翻转静态检出。**瓦片只作为一个检查项，不做渲染/切片** | ✅ 已完成（2026-10-27） |
| M6 | 发布 | **git tag + GitHub Release（附产物）+ `plan/RELEASE-M6.md` 发布留档**；干净环境按 README 跑通；断网跑通；发布 GitHub **公开仓库** | ⬜ 待开工 |

**里程碑 → 模块映射**：里程碑 M2 ↔ 模块 M1｜M3 ↔ 模块 M2｜M4 ↔ 模块 M3｜M5 ↔ 模块 M4 + M5｜M1 与 M6 无对应模块（语料 / 发布）。

---

## 维护纪律

- 台账状态列在对应里程碑完成的**同一次提交**里翻转，不得滞后。
- 任何一条承诺若在开发中被砍，必须在决策记录表新增一行说明理由，并**同步删除题面对应措辞**；不得只改台账不改题面。
- **事实纪律**：RFC 条款、EPSG 编号、GCJ-02 常数、日期一律**照原文**；**不得编造**。未取到原文的一律标 ⬜ 并写明阻断原因（443 超时 / 直连被重置 / 403 限流都如实写，不当作 0 结果）。
- **数值纪律**：阈值、权重、残差格式、灰区条件、退出码只在 `data/README.md` §四定义。
- 里程碑出口门**只能加强**，不得为了让里程碑"看起来完成"而改弱（尤其 M6 的"附产物"三个字）。
- 实测/检索快照数字**不得**进入代码常数、README 首屏或断言阈值（例外见决策 ⑧）。
