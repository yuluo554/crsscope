# HANDOFF-M6 · 下一步：`report` 汇总 + `tools/check-release.py` + 发布（tag / Release / 留档）

> 用法：新对话 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务`
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
| 里程碑 M4 跨工具差分 | ✅ | `crsscope xdiff` 三实现差分落位 |
| **里程碑 M5 GeoJSON + 瓦片** | ✅ **本轮完成** | `crsscope geojson` 七项检查（含 check-geojson 不查的环方向 / 精度 / `crs`）；`crsscope tiles` 五项（`y` 轴翻转静态检出） |
| 测试 | ✅ | `py -3.12 -m pytest -o addopts=""` → **273 passed**（decl 24 + detect 23 + xdiff 28 + geojson 28 + tiles 28；未实现契约只剩 `report`） |
| CI | ⬜ **待首推验证** | `.github/workflows/ci.yml` 已写，**从未被 GitHub 跑过** |
| `report` 子命令 | ⬜ 未实现 | `crsscope report` 一律 exit 3 + `not implemented`（`tests/test_unimplemented_contract.py` 里只剩它） |
| 发布门 `tools/check-release.py` | ⬜ 未实现 | `AGENTS.md` §六 + 布局门 `PENDING_TOOLS` 登记为 **M6 落位** |

**M6 = 发布里程碑**：`report` 汇总/门禁 + `tools/check-release.py` 三档 + 构建双装态 +
tag / GitHub Release（附产物）+ `plan/RELEASE-M6.md` 两栏留档。

---

## 二、当前事实 · 状态不变量（下一棒动手前必须知道）

### 2.1 本轮新增（M5 判定侧 · `geojson` / `tiles`）

1. **`geojson.run(paths, *, strict_ring=False)`**（`cli._run_geojson` 已接好）。七项检查顺序固定
   `CHECKS = ("ring_order","axis","bbox","nesting","null_geometry","crs_member","precision")`，
   每项**一条** finding，跨文件聚合。
2. **`ring_order` 的级别由 R2 推导**：`_ring_order_status(strict_ring)` 读 `RFC_R2` 里的
   `R2_TOLERANCE_MARKER = "SHOULD NOT reject"`——在 → `warning`，不在 → `error`；
   `--strict-ring` 是另一条显式升级路径。**变异靶子**：
   `tests/test_geojson.py::test_ring_level_is_derived_from_r2` 把 `RFC_R2` 换掉并要求升 `error`；
   删掉那条分支测试立刻红。**不要**把级别改回写死的 `warning`。
3. **结构性问题走 exit 4，不靠 `error` 状态折算**：`geojson.audit(paths)` 返回
   `(每个文件的 FileAudit, structure/error findings)`；`run()` 发现 issues 非空就整体抛
   `InvalidInput`（exit 4），**不落报告**。`error` 状态在 `errors.outcome_code` 里是"命中 → 1"，
   与 §4.9 的 4 不同——这是有意分层，别合并。
4. **`geometry: null` / `properties: null` 只出 info、exit 0**；跨 180° bbox（`west > east`）
   只出 info（R4）。`crs_member` 措辞固定 `CRS_REMOVED_WORDING`（含 "no longer used"）+
   `CRS_PRIOR_ARRANGEMENT`（prior arrangement），**不含任何强制禁用表述**。
5. **精度口径**：JSON 用 `parse_float=Decimal` 读入，小数位直接读 Decimal 指数
   （`PRECISION_MAX_FRACTION_DIGITS = 9`）——不经过 float 往返。
6. **`tiles.run(path)`**（`cli._run_tiles` 已接好）。输入两态：
   `z/x/y` 清单（JSON：`{"tiles":…}` / `{"cases":[…]}` / 顶层数组；CSV 表头 `z,x,y[,wrap]`）
   或 GeoJSON / CSV(lon,lat) 点集。五项检查顺序固定
   `("axis_flip","y_range","zoom_bbox","wrap","mixed_3857_4326")`。
7. **`axis_flip` 的"同一 bbox"必须可证**：组级/单枚 bbox 相同，**或** `scheme` 明写 `xyz`/`tms`；
   只凭同 `z`/`x` 下 `y` 与 `2^z-1-y` 并存会误伤相邻两行（`test_axis_flip_needs_shared_bbox_or_scheme_labels`）。
   fixture 的 `bbox` 是声明，不用于反算瓦片号。
8. **`y_range` 单点即判**（`y ∉ [0, 2^z-1]` → `error`）；**`wrap`** 的触发条件：同一 `z` 下
   `x=0` 与 `x=2^z-1` 并存，或 `x` 越界，或组级 bbox `west > east`；缺 `wrap: true` → `conflict`
   并列出具体 `z/x/y`。**`mixed_3857_4326`** 只对点集生效（`§4.1` 的度域/米域分档）；
   瓦片编号输入报 `info`（本项不适用）。
9. **不做渲染 / 切片 / 图片**：`tiles` 的 payload 只有布尔 / 数值 + 证据。

### 2.2 语料侧（本轮的两处实测）

10. **`geojson_struct/gen.py` 的 `_feature()` 已修正**：原实现把 `properties=None` 当成
    "省略参数"吞掉，导致 `case-005` 落盘的 `properties` 不是 `null`（与金标 `properties_is_null: true`
    矛盾）。现在用 `_UNSET` 哨兵区分；产物已重生成，`--check` 10/10 逐字节一致。
    **改语料后必须 `--out` 重生成再 `--check`**，否则下一棒会看到假红。
11. **`tile_flip` 金标的 `wrap` 通过态写作 `"ok"`**，不是 `Finding.status` 的 `consistent`。
    测试里做了显式映射（`tests/test_tiles.py::test_wrap_declared_passes`），**不要**为了对齐
    金标把 `Finding.status` 改成 `ok`（`plan/03` 开头的固定枚举不允许）。
12. **`geojson` 的 bbox 包含判定按跨 180° 语义**：`west > east` 时 `lon >= west or lon <= east`。
    fixture `case-004` 的 `[177,-20,-178,-16]` 覆盖点 `(179.5,-18)`，所以它必须是 `info` 而不是
    "bbox 与几何不一致" warning。

### 2.3 门与文档侧（五轮踩过的坑）

13. **台账状态列的编号是里程碑号**（不是模块号）。翻里程碑 ✅ 时，台账里**不许**留"模块 Mx"字样。
14. **布局门 `PENDING_TOOLS`**：`tools/check-release.py` 登记为 M6 落位，M6 翻 ✅ 时必须删除该条，
    否则 `LAYOUT.DOC_TOOLS` 变红（登记项过期即红）。
15. **`plan/RELEASE-M6.md` 的形态由门断言**（M6 翻 ✅ 后 `LAYOUT.RELEASE` 才生效）：
    必须有 `## 一、tag 前事实`、`## 二、tag 后追加`，以及标题含"覆盖对账"的小节，
    且三态行（`实现` / `不适用` / `待首推`）**≥ 3 行**。
16. **`plan/06` 缺口列不得出现已 ✅ 的里程碑号**（本轮已把 "M5 逐个落位" 从缺口行移走）。
17. **`.gitignore` 的裸目录名匹配**曾把 `data/mask/` 吞掉（已改成锚定根 `/mask/`）；
    `data/fixtures/*/out/` 与 `*.geojson` 刻意不入仓——语料靠生成器重建。
18. **`tests/conftest.py` 的补齐判据是"产物目录缺件"**，不是"`expect.json` 缺件"。
19. **CI 里"未实现命令必须 exit 3"的靶子已改成 `report`**（`.github/workflows/ci.yml`）。
    M6 实现 `report` 后，这个步骤必须**整段删除**（或改成"不存在的子命令 → exit 2"），
    否则会拿已实现命令当靶子 → 假红/假绿。
20. **`exit 3 + not implemented` 是未实现子命令的硬契约**（决策 ⑦b）。`report` 落位时要从
    `tests/test_unimplemented_contract.py` 的 `UNIMPLEMENTED` 删掉它——删空之后 `test_contract_table_matches_handlers`
    仍应通过（`set()` 是任何集合的子集），但两个参数化测试会变成空参数集，pytest 会报
    "no tests ran" 的告警；**建议**把该文件改成"契约表为空即通过 + 断言表已空"的形态，
    或把 `report` 的实现与契约表清理放在同一提交里并保留一个显式的"未实现清单为空"测试。

---

## 三、下一棒待办（M6：report + 发布门 + 发布）

按顺序做。**发布是时序敏感操作**：构建晚于交付面定稿；tag 树内不写字面值。

### A. `report` 子命令（汇总 + 门禁）

1. **实现 `cli._run_report`**（`plan/03` §六 + §七）。输入 `nargs="+"` 的多份 `report.json`；
   输出：聚合的 findings / 每份报告的 `command` / `exit_code` 汇总 / 门禁结论。
   `--fail-on` 语义复用 `errors.outcome_code`（**不要在 report 里另写一份退出码映射**）。
2. **失败路径**（§4.9）：文件不存在 → exit 3；JSON 不可解析 / 顶层缺 `findings` → exit 4。
   聚合后出现 `undecidable` → 5（除非 `--allow-undecidable`）。
3. **新增 `tests/test_report.py`**：吃前面五个子命令真实产出的 `report.json`；
   断言聚合计数、退出码优先级、`--fail-on` 收窄、坏 JSON → 4。
4. **契约表清理**：`UNIMPLEMENTED` 删掉 `report`（见 §2.3 第 19/20 条，注意空表的处理）。
5. **CI**：删掉"Unimplemented commands must exit 3"步骤（或改成"未知子命令 → exit 2"）。

### B. `tools/check-release.py`（发布门，三档）

6. **三档**（`plan/05` §五 / M6 DoD）：
   - `--pre-tag`：零网络，tag 推送时必红（检查"tag 还未创建"这一前置事实）；
   - 默认（离线）：进 CI；只落仓库内文件（不读 `git` 元数据）；
   - `--online`：需要网络与已发布事实（tag 对象 / Release 附件 / sha256）。
7. **判据**：附件与 `git archive <tag>` 解包树的**共有文件**逐字节相等（**不是** `diff -r` 零差异——
   附件不含 `.git` 等仅归档侧文件）；`SHA256SUMS` 可复核；README 命令面可跑。
8. **落位后**：从布局门 `PENDING_TOOLS` 删除 `tools/check-release.py`；从 `AGENTS.md` §六删除登记行
   （或改成"已落位"）；在 `plan/05` §五登记三档命令。
9. **守门**：`tests/test_release_gate.py`（或并入 `test_layout_gate.py`）：三档各自可跑通/必红；
   变异验证：故意篡改一个附件字节 → 门必须红。

### C. 构建与双装态

10. `py -3.12 -m build` → `dist/`；**wheel 与 sdist 的判定行为必须一致**：两态各装一次，
    各跑一条**真命令**（不要只跑 `--version`），例如
    `crsscope geojson data/fixtures/geojson_struct/out/case-001_ring_cw.geojson --strict-ring`
    与 `crsscope tiles data/fixtures/tile_flip/out/tile_flip.json`。
11. 干净 venv 装 sdist 的 build isolation 需要 `setuptools>=77`（离线会卡）。可行通道：
    带网络 `pip install <sdist>`，或装 wheel（`--no-index --find-links dist crsscope`）。
12. **断网跑通**（`docker run --network none` 或 `--offline` 冒烟）；零网络守门已有
    `tests/test_no_network.py`（AST 扫 import），M6 要补的是**运行时**断网实跑。

### D. 发布与留档

13. **交付面定稿**（`src/` + `data/fixtures/**/gen.py` + `pyproject.toml` + README）→ 重生成样例
    → 全量测试 → 构建（**构建必须晚于定稿**）。
14. `SHA256SUMS` → commit → **annotated tag** → `push main` + `push tag`。
15. `gh release create <tag> <附件> --notes-file <正文>`；**附件与 tag 树共有文件逐字节相等**。
16. **真下载回本地** → `sha256sum -c` + 逐字节 `cmp`。
17. `plan/RELEASE-M6.md`：`## 一、tag 前事实` / `## 二、tag 后追加` / 覆盖对账表
    （三态行 ≥ 3；**tag 树内不写字面值**——包 sha256 / tag 对象 OID 只能写进 tag 之后的提交或 Release 正文）。
18. **CI 首推验证**：首推后记录 run id；`gh run list` 全绿后才能把 `plan/05` §四的"CI 实跑"翻 ✅。

### E. 收尾

19. `plan/05` §一 M6 翻 ✅；`plan/00` 里程碑表同步翻 ✅；台账对应行翻 ✅；
    `plan/06` 缺口表删/改行（缺口列不得出现 M6）；`plan/05` §四"已知未验证项"如实更新。
20. **M6 是最后一个里程碑**：不需要 `HANDOFF-M7.md`（门的交接单判据只要求已 ✅ 的里程碑各一份，
    `plan/HANDOFF-M6.md` 即本文件）；但 `plan/RELEASE-M6.md` **必须**存在（门会断言两栏 + 覆盖对账）。
21. commit（发布提交与 tag 分开：先提交留档，再 tag）。

**M6 出口判据**（`plan/05` §三）：`report` 可用；`tools/check-release.py` 三档各跑通；
干净环境按 README 跑通；断网跑通；tag + GitHub Release 附产物；`plan/RELEASE-M6.md` 两栏 +
覆盖对账表；CI 首推全绿。

---

## 四、既定口径清单（K 编号，动了会打挂测试）

| 编号 | 约定 | 谁在守 |
|---|---|---|
| K01 | 退出码优先级 `2→3→4→5→1→0`，只在 `errors.py` 一处定义 | `tests/test_cli.py` + `tests/test_unimplemented_contract.py` |
| K02 | 版本单点 = `__init__.__version__`，pyproject 用 `dynamic` | `tests/test_version.py` |
| K03 | `DECLARED_CRS_CHOICES = ("4326","3857","4490","crs84")`，GCJ-02/BD-09 不是合法声明值 | `tests/test_cli.py::test_parser_exposes_all_declared_crs_choices` |
| K04 | `algorithms.KRASOVSKY_A == 6378245.0`、`EE == 0.006693421622965823`、`INVERSE_TOLERANCE_DEG == 1e-6` | `tests/test_core.py::test_krasovsky_constants_are_verbatim` |
| K05 | 两库边界：`CT_PY_BBOX` 开区间、`GCOORD_BBOX` 闭区间 | `tests/test_core.py` + `tests/test_fixtures.py` 独立复算 |
| K06 | 距离只走 `geodesy.haversine_m`，`R = 6371008.8` | `tests/test_core.py` |
| K07 | `MaskStats.water_ratio` 无分母时返回 `None`（不许返回 0.0） | `tests/test_core.py::test_water_ratio_is_none_when_nothing_evaluable` |
| K08 | `mask.MAX_RESOLUTION_DEG = 1.0`，超限抛 `EnvironmentMissing`（exit 3） | `tests/test_core.py::test_mask_rejects_resolution_above_cap` |
| K09 | `report.TIMESTAMP_FIELD == "generated_at"` 且报告里只能有一个时间戳字段 | `tests/test_determinism.py::test_only_one_timestamp_field_in_payload` |
| K10 | 未实现子命令必须 exit 3 + 含 `not implemented` | `tests/test_unimplemented_contract.py`（M6 后表为空，守门形态要改） |
| K11 | `crs` 措辞只准 "no longer used"，读者面不得出现断言式禁用表述 | `tests/test_wording.py` |
| K12 | `io` 层拒绝含 `<!DOCTYPE` / `<!ENTITY` 的 XML（GPX 安全） | `tests/test_io.py::test_xml_with_dtd_or_entity_is_rejected` |
| K13 | `--check` 对生成物**允许缺席**，对 `expect.json` **缺件即 FAIL** | `data/_genlib.FixtureRun._check` + `tests/test_fixtures.py` |
| K14 | `expect.json` 顶层键 = `{fixture, generator_version, cases}` ∪ 白名单 | `tests/test_fixtures.py::test_expect_json_has_required_keys` |
| K15 | 「命中」= `conflict`/`error`（默认），`--fail-on` 收窄；灰区优先 → `undecidable` 即 5 | `errors.outcome_code` + `tests/test_decl.py::test_outcome_code_default_states` |
| K16 | `warning` 默认不算命中；升级只能 `--strict-ring` / `--fail-on` 点名 | `tests/test_decl.py::test_fail_on_narrows_the_hit_set` |
| K17 | `decl` 的检查项一项一责：`extent` 读 `axis` 的 orientation | `tests/test_decl.py::test_swapped_axis_hits_axis_conflict_only` |
| K18 | `detect` 六环节固定顺序、四项 findings 一项一责 | `tests/test_detect.py::test_findings_follow_fixed_check_order` |
| K19 | `distance_to_bbox_deg` = 到矩形边的真距离（框内非 0） | `tests/test_detect.py` + `plan/05` §二之三 实测结论 2 |
| K20 | 默认 1° 掩膜复现不了 D2；D2 必须用 `water_track` 自带细网格 | `tests/test_detect.py::test_default_mask_rejects_gcj_offset_only_undecidable` |
| K21 | `xdiff` 差分方向 = 输入读作 target、输出转 WGS84；适用实现按 target 分档 | `tests/test_xdiff.py` + `plan/00` 决策 ⑫ |
| K22 | `xdiff` 的 `not_converged` 归 `undecidable`（非 `conflict`），且必须出现在 payload 里 | `tests/test_xdiff.py::test_not_converged_is_reported_not_swallowed` |
| K23 | `xdiff` 的 `boundary_table` 用输入坐标直接代入两库边界框（不复用 WGS84 输出） | `tests/test_xdiff.py::test_boundary_table_matches_gold_row_by_row` |
| K24 | `geojson.CHECKS` 七项顺序固定；`CHECK_GEOJSON_GAPS` 三项必须都查；`CRS_REMOVED_WORDING` 含 `no longer used` 且不含 `MUST NOT` | `tests/test_wording.py` + `tests/test_geojson.py` |
| **K25** | **`ring_order` 的级别由 R2 推导**：`R2_TOLERANCE_MARKER in RFC_R2` 决定 `warning`，否则 `error`；`--strict-ring` 是另一条升级路径 | `tests/test_geojson.py::test_ring_level_is_derived_from_r2` |
| **K26** | **`geojson` 结构性问题逐条记 `structure/error`，再整体抛 `InvalidInput` → exit 4**（不靠 `error` 状态折算 1） | `tests/test_geojson.py::test_malformed_coordinate_exits_4_without_writing_reports` |
| **K27** | **`tiles.axis_flip` 需要"同一 bbox"可证**：组级/单枚 bbox 相同，或 `scheme` 明写 `xyz`/`tms` | `tests/test_tiles.py::test_axis_flip_needs_shared_bbox_or_scheme_labels` |
| **K28** | **`tiles.wrap` 触发**：同 `z` 下 `x=0` 与 `2^z-1` 并存 / `x` 越界 / 组级 bbox `west > east`；缺 `wrap: true` → conflict 并列出具体 `z/x/y` | `tests/test_tiles.py::test_wrap_missing_is_conflict_with_specific_tiles` |
| **K29** | **`geojson` 精度用 `Decimal` 指数**（`parse_float=Decimal`），阈值 `> 9` 位 | `tests/test_geojson.py::test_precision_threshold_is_nine_fraction_digits` |
| **K30** | **`data/fixtures/geojson_struct/gen.py` 的 `_feature()` 用哨兵默认值**：`properties=None` 是合法 JSON null，不得被默认 dict 吞掉 | `data/fixtures/geojson_struct/gen.py --check` + `tests/test_geojson.py::test_null_geometry_and_properties_are_info_only` |

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
- **`data/fixtures/*/out/` 与 `*.geojson` 不入仓**；干净 clone 靠 `tests/conftest.py` 补齐。
  改了生成器就必须 `--out` 重生成再 `--check`。
- **Node v24.15.0 存在**，但本仓库的门**故意用 Python 写**（`tools/*.py`），不引入 Node 依赖。
- `gh` 2.93.0 可用；git 身份 `yuluo554 <282769740+yuluo554@users.noreply.github.com>`。

---

## 六、DoD 逐项 checklist（M6）

- [ ] `report` 子命令落位：多份 `report.json` 聚合 + `--fail-on` 门禁；坏 JSON → exit 4、缺文件 → 3
- [ ] `UNIMPLEMENTED` 删掉 `report`；CI 里"未实现命令 exit 3"步骤同步删除/改写
- [ ] `tools/check-release.py` 三档落位（`--pre-tag` / 离线默认 / `--online`）；变异验证可红
- [ ] 布局门 `PENDING_TOOLS` 删除 `tools/check-release.py`；`AGENTS.md` §六同步
- [ ] `python -m build` 成功；干净 venv 装 wheel 与 sdist 后各跑一条**真命令**，行为一致
- [ ] 断网实跑通过（`--offline` 冒烟或 `docker run --network none`）
- [ ] `SHA256SUMS` + annotated tag + GitHub Release 附产物；真下载回本地 `sha256sum -c` + `cmp`
- [ ] `plan/RELEASE-M6.md` 两栏 + 覆盖对账表（三态行 ≥ 3；tag 树内不写字面值）
- [ ] CI 首推后 `gh run list` 全绿并记录 run id
- [ ] `plan/00` / `plan/05` 的 M6 状态同提交翻 ✅（台账里别留"模块 M6"字样）
- [ ] 布局门全绿、变异 10/10、pytest 全绿（计数从 273 起涨）

---

## 七、关键命令速查

```bash
py -3.12 tools/check-sprint-layout.py            # 布局门：0 全绿 / 1 FAIL / 2 用法
py -3.12 tools/mutate-layout-gate.py             # 门变异：10 组必须全红
py -3.12 -m pytest -o addopts=""                 # 全量（要汇总行别加 -q）
py -3.12 -m pytest tests/test_geojson.py tests/test_tiles.py -q   # 本轮判定守门
py -3.12 -m crsscope --help                      # CLI 面
py -3.12 -m crsscope geojson data/fixtures/geojson_struct/out/case-001_ring_cw.geojson \
    --strict-ring --json --out-dir /tmp/o
py -3.12 -m crsscope tiles data/fixtures/tile_flip/out/tile_flip.json --json --out-dir /tmp/o
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
