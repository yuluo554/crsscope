# HANDOFF-M5 · 下一步：模块 M4「GeoJSON 结构审计」+ 模块 M5「瓦片 / 投影一致性」

> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务`
> **第一动作（硬约束③）**：先跑布局门 `py -3.12 tools/check-sprint-layout.py`，必须全绿再动手。

---

## 一、当前进度 + 证据

| 项 | 状态 | 证据（2026-10-27 实测） |
|---|---|---|
| 题面定稿 / 计划 00–06 | ✅ | `plan/00`–`plan/06` 齐备 |
| 方法论装订 + 布局门（10 判据） | ✅ | `py -3.12 tools/check-sprint-layout.py` → 全绿 |
| 门变异验证 | ✅ | `py -3.12 tools/mutate-layout-gate.py` → **10/10 符合预期 / 0 SKIP** |
| 里程碑 M1 数据先行 | ✅ | 七份 fixture + 掩膜；8 份生成器 `--check` exit 0 逐字节一致 |
| 里程碑 M2 声明-内容一致性 | ✅ | `crsscope decl` 五项判据落位 |
| 里程碑 M3 GCJ 检测与残差 | ✅ | `crsscope detect` 六环节落位 |
| **里程碑 M4 跨工具差分** | ✅ **本轮完成** | `crsscope xdiff` 三实现差分落位；两类边界分歧逐字段对拍金标；`not_converged` 如实报出（`undecidable` + exit 5） |
| 测试 | ✅ | `py -3.12 -m pytest -o addopts=""` → **218 passed**（骨架 168 + detect 23 + xdiff 28） |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写，**从未被 GitHub 跑过** |
| 判定逻辑（模块 M4–M5 对应里程碑 M5） | ⬜ 未实现 | `geojson` / `tiles` / `report` 一律 exit 3 + `not implemented` |

**M5 = 模块 M4 `geojson.py`「RFC 7946 结构与声明审计」+ 模块 M5 `tiles.py`「瓦片 / 投影一致性」**
（`plan/03` §四 / §五；编号差一位，见 `plan/00` 决策 ⑨）。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

### 2.1 本轮新增（M3 判定侧 · `xdiff`）

1. **`xdiff.run(path, target)`** 已接好（`cli._run_xdiff`）。**方向写死**：输入坐标被读作
   `--target` 指定的坐标系，每个实现把它转成 **WGS84**——三者唯一可比的公共参照系。
   差分在 WGS84 输出之间做（`plan/00` 决策 ⑫）。
2. **适用实现按 target 分档**（`xdiff.TARGET_IMPLEMENTATIONS`，**不是**三个全上）：
   `wgs84` → 三实现（恒等，差分为 0）；`gcj02` / `bd09` → `coordTransform_py` + `gcoord`；
   `webmercator` → `gcoord` + `proj4js_webmercator`。把不适用者塞进来会造出**虚假差分**。
3. **`(72.05, 0.83)` 是"不收敛"样本**（`four_crs` `case-004` 复用）：gcoord 闭区间内、
   coordTransform_py 开区间外 → gcoord 定点迭代 100 次仍不收敛。`xdiff` 把它归
   `undecidable`（`reason: not_converged`）而非 `conflict`——**判不出来 ≠ 判定命中**，
   且**不得**静默返回一个"看起来对"的值（题面 §M3 纪律）。
4. **`boundary_table` 用输入坐标直接代入两库边界框**（**不**复用 WGS84 输出）——
   这与金标 `boundary_divergence/gen.py` 及 §1.3 对照表同口径（"经度 73.2 < 73.66 → 境外"）。
   行形状与 `expect.expected.boundary_table_row` **逐字段同形**。
5. **`pairwise` 的距离只走 `geodesy.haversine_m`**（§4.4，禁止平面欧氏）；
   `max_m` 附该点坐标（`max_at`），平局取更早的点（`key=(dist, -i)`）。

### 2.2 GeoJSON 模块（M5 将用到的既有件）

6. **`geojson.py` 的模块级常量已定**（**照用，不要重命名**，测试钉住）：
   - `CHECKS = ("ring_order","axis","bbox","nesting","null_geometry","crs_member","precision")`
     ——检查项顺序**固定**（`plan/03` §四表）；
   - `CHECK_GEOJSON_GAPS = ("ring_order","precision","crs_member")`——check-geojson 明示不查的三项，
     本工具**必须都查**；
   - `CRS_REMOVED_WORDING`——**必须**含 `"no longer used"` 且**不含** `MUST NOT`
     （`tests/test_wording.py::test_crs_wording_constant_is_correct` 直接断言）；
   - `RFC_R1` / `RFC_R2`——原文照录，`tests/test_wording.py::test_rfc_quotes_are_intact` 逐字断言。
7. **R1 / R2 成对引用 + 级别由 R2 决定**（决策 ②）：`ring_order` 默认 **warning**，
   `--strict-ring` 是**唯一**升级到 error 的路径。**变异靶子**：把 R2 那段逻辑删掉 →
   `ring_order` 必须升级为 error → 单测必须失败（`plan/03` §四 "假门"警告：只断言"报告里有
   ring_order"证明不了分级逻辑存在——**必须**测"删 R2 → 级别变化"这条变异）。
8. **`crs` 措辞只准 "no longer used"**（决策 ①，最高优先级）：RFC 7946 §4 **没有** "crs MUST NOT"。
   `tests/test_wording.py` 扫 `README.md` / `AGENTS.md` / `src/**` 字符串字面量，命中即红。
9. **`geometry: null` / `properties: null` 合法**（RFC 7946 §3.2 + `data/README.md` §4.6）：
   只出 **info**，**不得**进 exit 4。跨 180° bbox（`west > east`，如 `[177,-20,-178,-16]`）
   **不得**报 error（§4.6 R4）。
10. **`--strict-ring` 是 `geojson` 子命令独有的参数**（`cli.py` 已接好 `strict_ring`），
    与公共 `--fail-on` **不同**：前者是 R1 的**唯一**升级路径（`data/README.md` §4.6）。

### 2.3 瓦片模块（M5 将用到的既有件）

11. **`tiles.py` 的检查项顺序已定**：`("axis_flip","y_range","zoom_bbox","wrap","mixed_3857_4326")`
    （`plan/03` §五表 / `data/README.md` §4.7）。`axis_flip` 是**静态**判定——同一 `z` 下
    同时出现 `y` 与 `2^z-1-y` 且指向同一 bbox → 混用（**无需**任何底图）。
12. **`y_range`：`y ∉ [0, 2^z-1]` → error，单点即判**；`zoom_bbox`：`z+1` 覆盖集合
    ⊆ `z` 集合展开，破坏即 `conflict`；`wrap`：`x` 环绕须显式 `wrap: true`，
    经纬跨日界线而缺席 → `conflict`。
13. **不做渲染、不产出图片、不做切片**（题面 §M5 / README 三条纪律）。

### 2.4 门与文档侧（三轮踩过的坑）

14. **台账状态列的编号是里程碑号**（不是模块号）。翻里程碑 ✅ 时，台账里**不许**留"模块 Mx"字样。
15. **布局门 `PENDING_TOOLS`**：`tools/check-release.py` 登记为 M6 落位，M6 翻 ✅ 时必须删除该条。
16. **`.gitignore` 的裸目录名匹配**曾把 `data/mask/` 吞掉（已改成锚定根 `/mask/`）——新增忽略规则时警惕。
17. **`tests/conftest.py` 的补齐判据是"产物目录缺件"**，不是"`expect.json` 缺件"（后者永不触发）。
18. **`exit 3 + not implemented` 是未实现子命令的硬契约**。M5 要**同时**从
    `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉 `"geojson"` 与 `"tiles"`
    （**两个一起**，因为它们同属里程碑 M5 出口）；`report` 留到 M6。

---

## 三、下一棒待办（M5：模块 M4 GeoJSON + 模块 M5 瓦片）

按顺序做。**检查项顺序固定、不许并行**（`plan/03` §四 / §五）。

### A. `geojson.py`

1. **实现 `run(paths, strict_ring=False)`**（接口见 `plan/03` §四；`cli._run_geojson` 已接好）。
   输入 `nargs="+"`：一个或多个 GeoJSON 文件。
2. **七个检查项按固定顺序**（`geojson.CHECKS`）：
   `ring_order`（Shoelace 符号，外环 CCW）→ `axis`（坐标对是否 `lon, lat`）→
   `bbox`（顺序 / 与真实外包框一致 / 跨 180° 合法性）→ `nesting`（GeometryCollection 深度与类型）→
   `null_geometry`（info）→ `crs_member`（"no longer used"，warning）→ `precision`（单分量小数位 > 9）。
3. **R1+R2 成对引用**：`ring_order` 的 `detail` 必须**同时**含 R1 与 R2 的语义；
   级别由 R2 决定——默认 `warning`，`--strict-ring` 才升 `error`。**证据字段**带上 `RFC_R1` / `RFC_R2`。
4. **`crs_member` 只表述 "no longer used"**（用 `geojson.CRS_REMOVED_WORDING`），
   附 R5 的 "prior arrangement 可用替代 CRS" 一句；**严禁**任何强制禁用式措辞。
5. **`null_geometry` / `null_properties` 只出 info**；**跨 180° bbox 不得报 error**。
6. **失败路径**（`data/README.md` §4.9）：非法 JSON / `type` 未知 / 坐标对非数值 → exit 4；
   `geometry: null` **不得**进 exit 4。

### B. `tiles.py`

7. **实现 `run(path)`**（接口见 `plan/03` §五；`cli._run_tiles` 已接好）。
   输入 `z/x/y` 清单（CSV / JSON）或 3857/4326 混用点集——分辨率口径见 §4.7。
8. **五个检查项按固定顺序**：`axis_flip`（同 `z` 下 `y` 与 `2^z-1-y` 并存且同 bbox）→
   `y_range`（越界 error，单点即判）→ `zoom_bbox`（`z+1` ⊆ `z` 展开，破坏 conflict）→
   `wrap`（`x` 环绕须显式 `wrap: true`）→ `mixed_3857_4326`（量级分档冲突）。
9. **不做渲染 / 切片 / 图片**；输出只有布尔 / 数值判定 + 证据。

### C. 收尾

10. **从 `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉 `"geojson"` 与 `"tiles"`**，
    并同步 `ARGS`。
11. **新增 `tests/test_geojson.py` + `tests/test_tiles.py`**：
    - `geojson`：三个"check-geojson 不查"的项都能查；**R1+R2 变异靶子**（删 R2 → 级别升级 → 测试失败）；
      跨 180° bbox 不报 error；`geometry: null` 只 info 且 exit 0；吃 `data/fixtures/geojson_struct/`。
    - `tiles`：`y` 轴翻转**静态**检出（无需底图）；`y` 越界单点即 error；混用给出具体冲突点；
      吃 `data/fixtures/tile_flip/`。
12. **收尾**：`plan/05` §一 M5 翻 ✅、`plan/00` 里程碑表同步翻 ✅、台账对应行翻 ✅、
    `plan/06` 缺口表加/改行（**缺口列不得出现已 ✅ 的里程碑号**）、写 `plan/HANDOFF-M6.md`、commit。

**M5 出口判据**（`plan/05` §三）：check-geojson 不查的三项都查；R1+R2 成对引用**可被变异咬住**；
跨 180° bbox 不报 error、`geometry: null` 不报错；`y` 轴翻转静态检出；
全仓无肯定式 "MUST NOT"（字符串扫描测试）。

---

## 四、既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 谁在守 |
|---|---|---|
| K01 | 退出码优先级 `2→3→4→5→1→0`，只在 `errors.py` 一处定义 | `tests/test_cli.py` + `tests/test_unimplemented_contract.py` |
| K02 | 版本单点 = `__init__.__version__`，pyproject 用 `dynamic` | `tests/test_version.py` |
| K03 | `DECLARED_CRS_CHOICES = ("4326","3857","4490","crs84")`，**GCJ-02/BD-09 不是合法声明值** | `tests/test_cli.py::test_parser_exposes_all_declared_crs_choices` |
| K04 | `algorithms.KRASOVSKY_A == 6378245.0`、`EE == 0.006693421622965823`、`INVERSE_TOLERANCE_DEG == 1e-6` | `tests/test_core.py::test_krasovsky_constants_are_verbatim` |
| K05 | 两库边界：`CT_PY_BBOX` 开区间、`GCOORD_BBOX` 闭区间 | `tests/test_core.py` + `tests/test_fixtures.py` 独立复算 |
| K06 | 距离只走 `geodesy.haversine_m`，`R = 6371008.8` | `tests/test_core.py` |
| K07 | `MaskStats.water_ratio` 无分母时返回 `None`（**不许**返回 0.0） | `tests/test_core.py::test_water_ratio_is_none_when_nothing_evaluable` |
| K08 | `mask.MAX_RESOLUTION_DEG = 1.0`，超限抛 `EnvironmentMissing`（exit 3） | `tests/test_core.py::test_mask_rejects_resolution_above_cap` |
| K09 | `report.TIMESTAMP_FIELD == "generated_at"` 且报告里**只能有一个**时间戳字段 | `tests/test_determinism.py::test_only_one_timestamp_field_in_payload` |
| K10 | 未实现子命令必须 exit 3 + 含 `not implemented` | `tests/test_unimplemented_contract.py` |
| K11 | `crs` 措辞只准 "no longer used"，读者面不得出现断言式禁用表述 | `tests/test_wording.py` |
| K12 | `io` 层拒绝含 `<!DOCTYPE` / `<!ENTITY` 的 XML（GPX 安全） | `tests/test_io.py::test_xml_with_dtd_or_entity_is_rejected` |
| K13 | `--check` 对生成物**允许缺席**，对 `expect.json` **缺件即 FAIL** | `data/_genlib.FixtureRun._check` + `tests/test_fixtures.py` |
| K14 | `expect.json` 顶层键 = `{fixture, generator_version, cases}` ∪ 白名单 | `tests/test_fixtures.py::test_expect_json_has_required_keys` |
| K15 | 「命中」= `conflict`/`error`（默认），`--fail-on` 收窄；**灰区优先** → `undecidable` 即 5 | `errors.outcome_code` + `tests/test_decl.py::test_outcome_code_default_states` |
| K16 | `warning` 默认**不**算命中；升级只能 `--strict-ring` / `--fail-on` 点名 | `tests/test_decl.py::test_fail_on_narrows_the_hit_set` |
| K17 | `decl` 的检查项**一项一责**：`extent` 读 `axis` 的 orientation | `tests/test_decl.py::test_swapped_axis_hits_axis_conflict_only` |
| K18 | `detect` 六环节固定顺序、四项 findings **一项一责** | `tests/test_detect.py::test_findings_follow_fixed_check_order` |
| K19 | `distance_to_bbox_deg` = **到矩形边的真距离**（框内非 0） | `tests/test_detect.py` + `plan/05` §二之三 实测结论 2 |
| K20 | 默认 1° 掩膜复现不了 D2；D2 **必须**用 `water_track` 自带细网格 | `tests/test_detect.py::test_default_mask_rejects_gcj_offset_only_undecidable` |
| **K21** | `xdiff` 三实现差分方向 = 输入读作 target、输出转 WGS84；**适用实现按 target 分档**（不是三个全上） | `tests/test_xdiff.py` + `plan/00` 决策 ⑫ |
| **K22** | `xdiff` 的 `not_converged` 归 `undecidable`（**非** `conflict`），且必须出现在 `payload["not_converged"]` 里 | `tests/test_xdiff.py::test_not_converged_is_reported_not_swallowed` |
| **K23** | `xdiff` 的 `boundary_table` 用**输入坐标**直接代入两库边界框（不复用 WGS84 输出），行与金标逐字段同形 | `tests/test_xdiff.py::test_boundary_table_matches_gold_row_by_row` |
| **K24** | `geojson.CHECKS` 七项顺序固定；`CHECK_GEOJSON_GAPS` 三项**必须都查**；`CRS_REMOVED_WORDING` 含 `no longer used` 且不含 `MUST NOT` | `tests/test_wording.py` + M5 新增测试 |

---

## 五、本机环境坑（只写实测过的，2026-10-27）

- **`python` 是商店占位符**，一律用 `py -3.12`。
- **本机 3.8 通道不参与验证**（项目下限 3.11）；3.11 行为差异只能靠 CI。
- **setuptools 84.2.1**：`license = "MIT"` 表达式可用；**license classifier 会直接报错**。
- **Bash 直接解包 sdist 会被安全扫描拦截**（解包会写 `.py`）。干净环境验证走
  `pip install <wheel|sdist>` 这条通道，**不要** `tar -xzf` 到工作区。
- **离线装 sdist 会卡在 build isolation**：`pip install --no-index <sdist>` 在全新 venv 里
  要现取 `setuptools>=77`，取不到就报错。两个可行通道：① 带网络 `pip install <sdist>`；
  ② **装 wheel**（`--no-index --find-links dist crsscope`，零 build 依赖）。
  **wheel 与 sdist 的判定行为必须一致**——两态各跑一条真命令对拍，不要只验 `--version`。
- **`py -3.12 -m pytest` 输出没有 `passed` 汇总行**（`addopts = -q` 吞掉了）；
  要计数用 `py -3.12 -m pytest -o addopts=""`。
- **跑 `crsscope <cmd>` 会往 CWD 落 `report.json` / `report.md`**（`--out-dir` 默认当前目录）；
  写测试时**一律**传 `--out-dir tmp_path`，否则会把报告写进仓库根。
- **`data/mask/out/mask_v1.json` 约 3 MB**（61200 格单行 JSON）。`--check` 会整读整比，单次约 0.4 s；
  **不要**把它接进逐测试的循环里。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。

---

## 六、DoD 逐项 checklist（M5）

- [ ] `geojson.py` 的 `run()` 落位：七检查项按固定顺序，含 check-geojson 不查的三项
- [ ] R1+R2 成对引用；**变异靶子**：删 R2 → `ring_order` 升级为 error → 单测失败
- [ ] `crs_member` 措辞为 "no longer used"，不含 `MUST NOT`
- [ ] 跨 180° bbox（`[177,-20,-178,-16]`）**不**报 error；`geometry: null` 只 info 且 exit 0
- [ ] `tiles.py` 的 `run()` 落位：`y` 轴翻转**静态**检出（无需底图）；`y` 越界单点即 error
- [ ] 混用样本给出具体冲突点（坐标 + `z/x/y`）
- [ ] `UNIMPLEMENTED` 表里删掉 `geojson` 与 `tiles`
- [ ] 布局门全绿、变异 10/10、pytest 全绿（计数从 218 起涨）
- [ ] `python -m build` 成功；干净 venv 装 sdist 后 `crsscope --help` 正常
- [ ] `plan/00` 与 `plan/05` 的 M5 状态同提交翻 ✅（**台账里别留"模块 M5"字样**）
- [ ] `plan/HANDOFF-M6.md` 已写

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 -m pytest -o addopts=""                 # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_xdiff.py -q        # 本轮已落位的判定守门
py -3.12 -m crsscope --help                      # CLI 面
py -3.12 -m crsscope xdiff data/fixtures/boundary_divergence/out/boundary_divergence.geojson \
    --target gcj02 --json --out-dir /tmp/o
py -3.12 -m build                                # 构建 dist/

# 语料（8 份生成器，全部 --check 必须 exit 0）
py -3.12 data/fixtures/four_crs/gen.py --check
py -3.12 data/fixtures/swapped_axis/gen.py --check
py -3.12 data/fixtures/declared_lie/gen.py --check
py -3.12 data/fixtures/boundary_divergence/gen.py --check
py -3.12 data/fixtures/water_track/gen.py --check
py -3.12 data/fixtures/tile_flip/gen.py --check
py -3.12 data/fixtures/geojson_struct/gen.py --check
py -3.12 data/mask/gen.py --check
```